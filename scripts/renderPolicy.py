#!/usr/bin/env python3
"""Render agentPolicyTemplate.yaml into Claude settings.json and Codex config.toml."""

import json
import sys
from pathlib import Path

import yaml
import tomli
import tomlkit

HOME_DIR = "/home/workbench"

DEFAULT_POLICY = "/nvwb-agent-config/agentPolicyTemplate.yaml"

CLAUDE_BASE = Path("/nvwb-agent-config/claude-config/settings.json")
CLAUDE_OUT = Path(HOME_DIR) / ".claude" / "settings.json"

CODEX_BASE = Path("/nvwb-agent-config/codex-config/config.toml")
CODEX_OUT = Path(HOME_DIR) / ".codex" / "config.toml"


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

    CLAUDE_OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(CLAUDE_OUT, "w") as f:
        json.dump(merged, f, indent=2)
        f.write("\n")

    print(f"Rendered Claude settings -> {CLAUDE_OUT}")


# ---------------------------------------------------------------------------
# Codex — config.toml
# ---------------------------------------------------------------------------

def build_codex_overlay(policy: dict) -> dict:
    paths = policy.get("paths", {})
    env = policy.get("environment", {})

    write = paths.get("write", [])
    read_only = paths.get("read_only", [])
    private = paths.get("private", [])
    proj_patterns = paths.get("private_project_patterns", [])
    env_names = env.get("private_names", [])
    env_patterns = env.get("private_patterns", [])

    workspace_roots = {p: True for p in write}

    filesystem = {}
    for p in read_only:
        filesystem[to_tilde(p)] = "read"
    for p in private:
        filesystem[to_tilde(p)] = "deny"

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
    with open(CODEX_OUT, "w") as f:
        f.write(doc)

    print(f"Rendered Codex config   -> {CODEX_OUT}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    policy_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_POLICY

    if not Path(policy_path).exists():
        print(f"ERROR: Policy file not found: {policy_path}", file=sys.stderr)
        sys.exit(1)

    policy = load_policy(policy_path)
    render_claude(policy)
    render_codex(policy)


if __name__ == "__main__":
    main()