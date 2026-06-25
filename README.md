# Agent Configuration for AI Workbench Projects

This repository provides policy-driven agent configuration for NVIDIA AI
Workbench project containers. It targets Claude Code and the Codex CLI.

A single policy file (`agentPolicyConfig.yaml`) in each project controls
what agents can read, write, execute, and access. The `renderPolicy.py`
script translates that policy into the native configuration files each
harness expects. The container's `onStart.bash` script orchestrates the
full pipeline on every container start.

## Who This Is For

Use this repository if you want a repeatable, auditable baseline for
coding agents inside AI Workbench project containers.

This is most useful when you want agents to consistently understand:

- The project lives at `/project`.
- Workbench project metadata lives under `/project/.project`.
- Some file edits require a container rebuild, restart, or Compose restart.
- Runtime containers should not be mutated with ad hoc `sudo` or package installs.
- Agent auth and local state should stay out of project repos and logs.

## Repository Layout

```text
agentPolicyTemplate.yaml          # Template seeded into projects as agentPolicyConfig.yaml

scripts/
  renderPolicy.py                 # Renders policy YAML into harness-native configs
  sanitizedHarnessLauncher.sh     # Wrapper that strips secrets from agent process env

claude-config/
  CLAUDE.md                       # Default project guidance (seeded to /project/CLAUDE.md)
  settings.json                   # Base settings (overlay target for renderPolicy.py)
  hooks/ai-workbench-container/   # Session hooks (symlinked into ~/.claude/hooks/)
  skills/ai-workbench-container/  # Skills (symlinked into ~/.claude/skills/)

codex-config/
  config.toml                     # Base config (overlay target for renderPolicy.py)
  AGENTS.md                       # Default project guidance
  hooks.json                      # Base hooks definition (rendered by renderPolicy.py)
  hooks/ai-workbench-container/   # Session hooks (symlinked into ~/.codex/hooks/)
  skills/ai-workbench-container/  # Skills (symlinked into ~/.codex/skills/)
  rules/                          # Command approval/blocking rules

config-cache/                     # Runtime cache (not committed)

tests/                            # Unit tests for renderPolicy.py (59 tests, stdlib unittest)
```

## How It Works

### Pipeline (onStart.bash)

Every container start runs this sequence:

1. **Audit log** — creates an append-only log at `cache-config/logs/agent-audit.txt`
   (root-owned, `chattr +a`).
2. **Clone** — if the config repo volume is empty, clones from the
   `$nvwb_agent_config` environment variable.
3. **Symlink hooks and skills** — links hook and skill directories from
   this repo into `~/.claude/` and `~/.codex/`.
4. **Seed project files** — copies `CLAUDE.md` and `agentPolicyTemplate.yaml`
   into `/project/` if they don't already exist.
5. **Render policy** — runs `renderPolicy.py /project/agentPolicyConfig.yaml`,
   which reads the project's policy and overlays it onto the base configs
   to produce:
   - `~/.claude/settings.json`
   - `~/.codex/config.toml`
   - `~/.codex/hooks.json`
   - Staged managed-settings variants in `cache-config/`
6. **Install managed settings** — copies the selected variant
   (`bypassBlocked` or `bypassAllowed`) to
   `/etc/claude-code/managed-settings.d/workbench.json` as root, making
   it unstrippable by agents.
7. **Shell aliases** — appends aliases to `~/.bashrc` that launch `claude`
   and `codex` through `sanitizedHarnessLauncher.sh`.

### renderPolicy.py

Reads a tool-agnostic policy YAML and produces harness-native configs by
overlaying policy-derived rules onto the base templates in `claude-config/`
and `codex-config/`.

Policy sections map to outputs as follows:

| Policy section | Claude settings.json | Codex config.toml | Managed settings |
|---|---|---|---|
| `paths.write` | `sandbox.filesystem.denyWrite` (inverted) | `permissions.filesystem` | `permissions.deny` |
| `paths.read_only` | `sandbox.filesystem.denyWrite` | `permissions.filesystem` | `permissions.deny` (read_only) |
| `paths.private` | `sandbox.filesystem.denyRead/denyWrite` | `permissions.filesystem` | `permissions.deny` (private) |
| `paths.private_project_patterns` | — | `permissions.filesystem.:workspace_roots` | — |
| `commands.ask` | `permissions.allow` (ask) | — | — |
| `commands.deny` | `permissions.deny` | — | `permissions.deny` |
| `environment.*` | — | `shell_environment_policy.exclude` | — |

Supports `--force` to skip cache checks. Caches policy and rendered
outputs in `config-cache/` to avoid unnecessary rewrites on restart.

### sanitizedHarnessLauncher.sh

Wraps `claude` and `codex` invocations with `env -u` to strip
secret-like environment variables before they reach the agent process.
Sources secret names from:

- Pattern matching against the current environment (e.g. `*_TOKEN`, `*_KEY`)
- Workbench secrets declared in `/project/.project/spec.yaml`

### Managed Settings

Claude Code supports a managed-settings tier at `/etc/claude-code/` that
outranks user and project settings. `onStart.bash` installs a root-owned
file there to enforce permission mode restrictions that agents cannot
override.

Two variants are staged by `renderPolicy.py`:

- **`bypassBlocked`** (default) — disables `bypassPermissions` and `auto`
  modes so agents always prompt for confirmation on controlled actions.
- **`bypassAllowed`** — permits all permission modes.

The `managed_settings_controls` field in the policy YAML selects which
variant is installed.

**Caveat:** If the user authenticates with a work account that pushes
server-managed settings, those take priority and the endpoint-tier file
at `/etc/claude-code/` is ignored entirely.

## The Policy File

Each project gets its own `agentPolicyConfig.yaml` (seeded from
`agentPolicyTemplate.yaml` on first start). This is the single file
project owners edit to tune agent behavior.

Key sections:

- **`paths.write/read_only/private`** — filesystem access tiers
- **`paths.private_project_patterns`** — workspace-root-relative globs
  for sensitive files (e.g. `**/*.pem`). Keep patterns precise — broad
  globs like `**/*token*` will block legitimate code files.
- **`commands.ask/deny`** — command approval and blocking rules
- **`environment`** — env var exclusion patterns and Workbench secret handling
- **`managed_settings_controls`** — `bypassBlocked` or `bypassAllowed`

After editing the policy file, restart the container to re-run the
pipeline, or run `renderPolicy.py` manually:

```bash
python3 ~/nvwb-agent-config/scripts/renderPolicy.py /project/agentPolicyConfig.yaml
```

## Claude vs Codex

Claude Code and Codex use similar concepts but different file paths and
configuration formats.

### Claude Code

Runtime config lives in `~/.claude/`:

```text
~/.claude/settings.json           # Rendered by renderPolicy.py
~/.claude/hooks/<name>/           # Symlinked from this repo
~/.claude/skills/<name>/          # Symlinked from this repo
```

Project-level guidance:

```text
/project/CLAUDE.md
/project/.claude/
```

### Codex CLI

Runtime config lives in `~/.codex/`:

```text
~/.codex/config.toml              # Rendered by renderPolicy.py
~/.codex/hooks.json               # Rendered by renderPolicy.py
~/.codex/hooks/<name>/            # Symlinked from this repo
~/.codex/skills/<name>/           # Symlinked from this repo
```

Project-level guidance:

```text
/project/AGENTS.md
/project/.codex/
/project/.agents/skills/
```

## Tests

The `tests/` directory contains a unittest suite covering the overlay
builders, render pipeline, cache logic, and edge cases (dangling
symlinks, bwrap deny-path placeholders).

```bash
cd tests && bash run_tests.sh
```

## Authentication and Local State

Do not commit agent credentials, local histories, transcripts, or
generated state into this repository.

Use persistent private volumes for agent auth files when containers need
login state across restarts.

## Status

Active development. The policy rendering pipeline and managed settings
installation are functional. Review the policy file and rendered outputs
before relying on them as an enforced security boundary.
