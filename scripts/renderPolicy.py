#!/usr/bin/env python3
"""Render agentPolicyTemplate.yaml into Claude settings.json and Codex config.toml."""

import datetime
import json
import os
import shutil
import sys
from pathlib import Path

import yaml
import tomli
import tomlkit

HOME_DIR = "/home/workbench"

# Repo + cache locations. Default to the in-home layout created by onStart.bash
# (agent_config_path / cache_config_path); override via env vars if the container
# places them elsewhere.
AGENT_CONFIG_DIR = Path(os.environ.get("NVWB_AGENT_CONFIG_DIR", "/home/workbench/nvwb-agent-config"))
CACHE_DIR = Path(os.environ.get("NVWB_CACHE_DIR", "/home/workbench/cache-config"))

DEFAULT_POLICY = str(AGENT_CONFIG_DIR / "agentPolicyTemplate.yaml")

CLAUDE_BASE = AGENT_CONFIG_DIR / "claude-config" / "settings.json"
CLAUDE_HOOKS_DIR = AGENT_CONFIG_DIR / "claude-config" / "hooks"
CLAUDE_OUT = Path(HOME_DIR) / ".claude" / "settings.json"

CODEX_BASE = AGENT_CONFIG_DIR / "codex-config" / "config.toml"
CODEX_OUT = Path(HOME_DIR) / ".codex" / "config.toml"

CODEX_HOOKS_BASE = AGENT_CONFIG_DIR / "codex-config" / "hooks.json"
CODEX_HOOKS_DIR = AGENT_CONFIG_DIR / "codex-config" / "hooks"
CODEX_HOOKS_OUT = Path(HOME_DIR) / ".codex" / "hooks.json"

CACHED_POLICY = CACHE_DIR / "agentPolicyConfig.yaml"
CACHED_CLAUDE = CACHE_DIR / "claude-settings.json"
CACHED_CODEX = CACHE_DIR / "codex-config.toml"
CACHED_CODEX_HOOKS = CACHE_DIR / "codex-hooks.json"

# Staged managed-settings variants. renderPolicy stages BOTH here (unprivileged);
# onStart.bash selects one per `managed_settings_controls` and installs it
# root-owned to /etc/claude-code/managed-settings.d/.
MANAGED_BLOCKED = CACHE_DIR / "bypassBlocked.json"
MANAGED_ALLOWED = CACHE_DIR / "bypassAllowed.json"

# onStart.bash creates this append-only, root-owned-dir log; audit() appends to it.
AUDIT_LOG = CACHE_DIR / "logs" / "agent-audit.txt"


def _clear_dangling_symlink(path: Path):
    if path.is_symlink() and not path.exists():
        path.unlink()


def audit(message: str):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] renderPolicy: {message}\n"
    print(line, end="")
    try:
        with open(AUDIT_LOG, "a") as f:
            f.write(line)
    except OSError:
        pass


def to_tilde(path: str) -> str:
    if path.startswith(HOME_DIR):
        return "~" + path[len(HOME_DIR):]
    return path


def union(a: list, b: list) -> list:
    seen = set()
    result = []
    for item in a + b:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def deep_merge(base: dict, overlay: dict) -> dict:
    """Overlay wins for scalars; dicts merge recursively; lists replaced."""
    merged = dict(base)
    for key, val in overlay.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(val, dict):
            merged[key] = deep_merge(merged[key], val)
        else:
            merged[key] = val
    return merged


def load_policy(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Claude Code — settings.json
# ---------------------------------------------------------------------------

def build_claude_overlay(policy: dict) -> dict:
    paths = policy.get("paths", {})
    commands = policy.get("commands", {})

    write = paths.get("write", [])
    read_only = paths.get("read_only", [])
    private = paths.get("private", [])
    ask = commands.get("ask", [])
    deny = commands.get("deny", [])

    return {
        "permissions": {
            "additionalDirectories": sorted(set(
                [p + "/" for p in write] + ["~/"]
            )),
            "ask": [f"Bash({cmd} *)" for cmd in ask],
            "deny": [f"Bash({cmd} *)" for cmd in deny],
        },
        "sandbox": {
            "filesystem": {
                "denyWrite": sorted(set(
                    to_tilde(p) for p in read_only + private
                )),
                "denyRead": sorted(set(
                    to_tilde(p) for p in private
                )),
            }
        }
    }


def render_claude(policy: dict):
    overlay = build_claude_overlay(policy)

    base_path = CLAUDE_OUT if CLAUDE_OUT.exists() else CLAUDE_BASE
    with open(base_path) as f:
        base = json.load(f)

    merged = deep_merge(base, overlay)

    bp = base.get("permissions", {})
    op = overlay.get("permissions", {})
    merged["permissions"]["additionalDirectories"] = union(
        bp.get("additionalDirectories", []), op.get("additionalDirectories", [])
    )
    merged["permissions"]["deny"] = union(
        bp.get("deny", []), op.get("deny", [])
    )
    merged["permissions"]["ask"] = union(
        bp.get("ask", []), op.get("ask", [])
    )

    bsf = base.get("sandbox", {}).get("filesystem", {})
    osf = overlay.get("sandbox", {}).get("filesystem", {})
    merged["sandbox"]["filesystem"]["denyWrite"] = union(
        bsf.get("denyWrite", []), osf.get("denyWrite", [])
    )
    merged["sandbox"]["filesystem"]["denyRead"] = union(
        bsf.get("denyRead", []), osf.get("denyRead", [])
    )

    merged, hook_rewrites = _rewrite_hooks_json(
        merged,
        _hook_relative_paths(CLAUDE_HOOKS_DIR),
        CLAUDE_HOOKS_DIR,
        ".claude",
    )

    CLAUDE_OUT.parent.mkdir(parents=True, exist_ok=True)
    _clear_dangling_symlink(CLAUDE_OUT)
    with open(CLAUDE_OUT, "w") as f:
        json.dump(merged, f, indent=2)
        f.write("\n")

    audit(f"Rendered Claude settings -> {CLAUDE_OUT} ({hook_rewrites} hook command path rewrite(s))")


# ---------------------------------------------------------------------------
# Codex — config.toml
# ---------------------------------------------------------------------------

def build_codex_overlay(policy: dict) -> dict:
    paths = policy.get("paths", {})
    wb = policy.get("workbench", {})
    env = policy.get("environment", {})

    write = paths.get("write", [])
    read_only = paths.get("read_only", [])
    private = paths.get("private", [])
    proj_patterns = paths.get("private_project_patterns", [])
    env_names = env.get("private_names", [])
    env_patterns = env.get("private_patterns", [])

    # Only the project directory is a workspace root.  Other writable
    # paths become absolute filesystem entries so that workspace-root-
    # relative patterns (.project, .codex, …) don't expand into /tmp
    # or $HOME where those directories don't exist.
    project_root = wb.get("project", "/project")
    workspace_roots = {project_root: True}

    filesystem = {}
    for p in write:
        if p != project_root:
            filesystem[to_tilde(p)] = "write"
    for p in read_only:
        filesystem[to_tilde(p)] = "read"

    # Prune deny entries whose parent is already read-only.  Bwrap
    # mounts the parent read-only first, then tries to create a deny
    # tombstone inside it — which fails because the parent is already
    # read-only, crashing every sandboxed command.  The read-only
    # parent already blocks writes; read-deny is covered by managed-
    # settings permission rules outside the bwrap sandbox.
    read_dirs = {to_tilde(p).rstrip("/") for p in read_only}
    for p in private:
        tp = to_tilde(p)
        if any(tp.startswith(rd + "/") for rd in read_dirs):
            continue
        filesystem[tp] = "deny"

    ws_root_rules = {".": "write"}
    for pat in proj_patterns:
        ws_root_rules[pat] = "deny"
    filesystem[":workspace_roots"] = ws_root_rules

    exclude = list(dict.fromkeys(env_names + env_patterns))

    return {
        "permissions": {
            "nvwb_workspace": {
                "workspace_roots": workspace_roots,
                "filesystem": filesystem,
            }
        },
        "shell_environment_policy": {
            "exclude": exclude,
        }
    }


def render_codex(policy: dict):
    overlay = build_codex_overlay(policy)

    base_path = CODEX_OUT if CODEX_OUT.exists() else CODEX_BASE
    with open(base_path, "rb") as f:
        base = tomli.loads(f.read().decode())

    merged = deep_merge(base, overlay)

    base_exclude = base.get("shell_environment_policy", {}).get("exclude", [])
    overlay_exclude = overlay.get("shell_environment_policy", {}).get("exclude", [])
    merged["shell_environment_policy"]["exclude"] = union(base_exclude, overlay_exclude)

    doc = tomlkit.dumps(merged)

    CODEX_OUT.parent.mkdir(parents=True, exist_ok=True)
    _clear_dangling_symlink(CODEX_OUT)
    with open(CODEX_OUT, "w") as f:
        f.write(doc)

    audit(f"Rendered Codex config   -> {CODEX_OUT}")


# ---------------------------------------------------------------------------
# Codex — hooks.json
# ---------------------------------------------------------------------------

def _hook_command_prefixes(config_dir: str) -> tuple:
    return (
        f"$HOME/{config_dir}/hooks/",
        f"~/{config_dir}/hooks/",
        f"{HOME_DIR}/{config_dir}/hooks/",
    )


def _hook_relative_paths(hooks_dir: Path) -> dict:
    """Map hook script basenames to their unique relative paths."""
    paths = {}
    duplicates = set()

    if not hooks_dir.exists():
        return paths

    for hook_path in hooks_dir.rglob("*"):
        if not hook_path.is_file():
            continue

        rel = hook_path.relative_to(hooks_dir).as_posix()
        name = hook_path.name
        if name in paths and paths[name] != rel:
            duplicates.add(name)
        else:
            paths[name] = rel

    for name in duplicates:
        paths.pop(name, None)

    return paths


def _rewrite_hook_command(command: str, hook_paths: dict, hooks_dir: Path, config_dir: str) -> tuple:
    for prefix in _hook_command_prefixes(config_dir):
        if not command.startswith(prefix):
            continue

        remainder = command[len(prefix):]
        script_ref, separator, args = remainder.partition(" ")
        if not script_ref:
            return command, False

        if (hooks_dir / script_ref).is_file():
            return command, False

        resolved = hook_paths.get(Path(script_ref).name)
        if not resolved:
            return command, False

        return f"{prefix}{resolved}{separator}{args}", True

    return command, False


def _rewrite_hooks_json(value, hook_paths: dict, hooks_dir: Path, config_dir: str) -> tuple:
    if isinstance(value, dict):
        rewritten = {}
        changed = 0
        for key, item in value.items():
            if key == "command" and isinstance(item, str):
                rewritten[key], did_change = _rewrite_hook_command(item, hook_paths, hooks_dir, config_dir)
                changed += int(did_change)
            else:
                rewritten[key], child_changed = _rewrite_hooks_json(item, hook_paths, hooks_dir, config_dir)
                changed += child_changed
        return rewritten, changed

    if isinstance(value, list):
        rewritten = []
        changed = 0
        for item in value:
            child, child_changed = _rewrite_hooks_json(item, hook_paths, hooks_dir, config_dir)
            rewritten.append(child)
            changed += child_changed
        return rewritten, changed

    return value, 0


def render_codex_hooks(policy: dict):
    if not CODEX_HOOKS_BASE.exists():
        audit(f"WARNING: codex hooks base missing: {CODEX_HOOKS_BASE}")
        return

    with open(CODEX_HOOKS_BASE) as f:
        hooks = json.load(f)

    hooks, changed = _rewrite_hooks_json(
        hooks,
        _hook_relative_paths(CODEX_HOOKS_DIR),
        CODEX_HOOKS_DIR,
        ".codex",
    )

    CODEX_HOOKS_OUT.parent.mkdir(parents=True, exist_ok=True)
    _clear_dangling_symlink(CODEX_HOOKS_OUT)
    with open(CODEX_HOOKS_OUT, "w") as f:
        json.dump(hooks, f, indent=2)
        f.write("\n")

    audit(f"Rendered Codex hooks    -> {CODEX_HOOKS_OUT} ({changed} command path rewrite(s))")


# ---------------------------------------------------------------------------
# Managed settings — the tamper-proof lock (permissions only; sandbox stays in
# user settings for now). Deny rules derive from paths; mode keys from the
# policy's `managed_settings_controls`. Staged for onStart.bash to install root-owned.
# ---------------------------------------------------------------------------

def _deny_rules(path: str, tools) -> list:
    """gitignore-style permission rules for `tools` on one policy path.
    `//` = filesystem-absolute. Emit the bare path and a `/**` form so one
    policy entry covers a file or a directory; skip `/**` for glob entries."""
    p = "//" + path.lstrip("/")
    is_glob = any(c in path for c in "*?[")
    rules = []
    for tool in tools:
        rules.append(f"{tool}({p})")
        if not is_glob:
            rules.append(f"{tool}({p}/**)")
    return rules


def build_managed_overlay(policy: dict, bypass_blocked: bool) -> dict:
    paths = policy.get("paths", {})
    read_only = paths.get("read_only", [])
    private = paths.get("private", [])
    deny_cmds = policy.get("commands", {}).get("deny", [])

    deny = []
    for p in read_only:
        deny += _deny_rules(p, ("Edit", "Write"))
    for p in private:
        deny += _deny_rules(p, ("Read", "Edit", "Write"))
    deny += [f"Bash({cmd} *)" for cmd in deny_cmds]
    deny = union(deny, [])  # de-dup, preserve order

    permissions = {"defaultMode": "default", "deny": deny}
    if bypass_blocked:
        permissions["disableBypassPermissionsMode"] = "disable"
        permissions["disableAutoMode"] = "disable"

    return {"permissions": permissions}


def _write_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    _clear_dangling_symlink(path)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def render_managed(policy: dict):
    """Stage BOTH managed-settings variants; onStart selects one to install."""
    _write_json(MANAGED_BLOCKED, build_managed_overlay(policy, bypass_blocked=True))
    _write_json(MANAGED_ALLOWED, build_managed_overlay(policy, bypass_blocked=False))
    n = len(build_managed_overlay(policy, bypass_blocked=True)["permissions"]["deny"])
    audit(f"Staged managed settings -> {MANAGED_BLOCKED.name} / {MANAGED_ALLOWED.name} ({n} deny rules)")


# ---------------------------------------------------------------------------
# Deny-path placeholders — bwrap needs mount targets to exist
# ---------------------------------------------------------------------------

def ensure_deny_placeholders(policy: dict):
    """Create placeholders for private paths under read-only parents.

    Codex's bwrap sandbox bind-mounts over deny paths.  If the target doesn't
    exist and its parent is already read-only, bwrap can't create the mount
    point and fails globally — blocking all shell commands.
    """
    paths = policy.get("paths", {})
    read_only = paths.get("read_only", [])
    private = paths.get("private", [])

    created = 0
    for p in private:
        if any(c in p for c in "*?["):
            continue

        target = Path(p)
        if target.is_symlink() and not target.exists():
            _clear_dangling_symlink(target)
        if target.exists():
            continue
        if not target.parent.exists():
            continue

        under_read_only = any(
            p.startswith(ro.rstrip("/") + "/") for ro in read_only
        )
        if not under_read_only:
            continue

        if "." in target.name:
            target.touch()
        else:
            target.mkdir(exist_ok=True)
        created += 1

    if created:
        audit(f"Created {created} deny-path placeholder(s) for bwrap")


# ---------------------------------------------------------------------------
# Cache — skip rendering when the policy hasn't changed
# ---------------------------------------------------------------------------

def policy_changed(policy_path: str) -> bool:
    if not CACHED_POLICY.exists():
        return True
    return Path(policy_path).read_text() != CACHED_POLICY.read_text()


def needs_render(policy_path: str) -> bool:
    """Render is required if the policy changed OR a rendered output is missing.

    Checking only the policy is unsafe: the cache and the outputs can drift out
    of sync (e.g. a cold start restores the cache but the $HOME outputs were
    wiped), leaving a stale "unchanged" marker pointing at files that no longer
    exist. Always confirm the outputs are actually present before skipping.
    """
    if policy_changed(policy_path):
        return True
    return not (CLAUDE_OUT.exists() and CODEX_OUT.exists()
                and CODEX_HOOKS_OUT.exists()
                and MANAGED_BLOCKED.exists() and MANAGED_ALLOWED.exists())


def save_cache(policy_path: str):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(policy_path, CACHED_POLICY)
    if CLAUDE_OUT.exists():
        shutil.copy2(CLAUDE_OUT, CACHED_CLAUDE)
    if CODEX_OUT.exists():
        shutil.copy2(CODEX_OUT, CACHED_CODEX)
    if CODEX_HOOKS_OUT.exists():
        shutil.copy2(CODEX_HOOKS_OUT, CACHED_CODEX_HOOKS)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    policy_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_POLICY
    force = "--force" in sys.argv

    if not Path(policy_path).exists():
        print(f"ERROR: Policy file not found: {policy_path}", file=sys.stderr)
        sys.exit(1)

    policy = load_policy(policy_path)

    # Always ensure placeholders — bwrap needs deny-path mount targets
    # to exist even when rendering is skipped (cache hit).  Placeholders
    # can disappear between restarts while the cache stays intact.
    ensure_deny_placeholders(policy)

    if not force and not needs_render(policy_path):
        audit("Policy unchanged and outputs present, skipping.")
        return

    if force:
        audit(f"Force render from {policy_path}")
    else:
        audit(f"Policy changed, rendering from {policy_path}")

    render_claude(policy)
    render_codex(policy)
    render_codex_hooks(policy)
    render_managed(policy)
    save_cache(policy_path)
    audit("Cache updated.")


if __name__ == "__main__":
    main()
