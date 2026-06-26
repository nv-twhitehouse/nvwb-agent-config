# Agent Config Startup

Read this before editing `/project/onStart.bash`, startup symlinks, seed files,
cache initialization, sanitized launch aliases, or managed-settings install.

## Responsibilities

- `onStart.bash` owns runtime setup and repair.
- SessionStart hooks should not recreate symlinks, render policy, seed files, or
  patch config drift.
- Development may happen in `/tmp/dev-nvwb-agent-config`; runtime uses
  `/home/workbench/nvwb-agent-config`.

## Startup Flow

1. Set `agent_config_path=/home/workbench/nvwb-agent-config` and
   `cache_config_path=/home/workbench/cache-config`.
2. Create or append to `cache-config/logs/agent-audit.txt`.
3. Clone the config repo from `$nvwb_agent_config` if the config volume is empty.
4. Link Claude hooks/skills into `~/.claude/`.
5. Seed `/project/CLAUDE.md`, `/project/.claude/`, and
   `/project/agentPolicyConfig.yaml` if missing.
6. Link Codex hooks/skills into `~/.codex/`.
7. Add aliases that launch `claude` and `codex` through
   `scripts/sanitizedHarnessLauncher.sh`.
8. Run `renderPolicy.py /project/agentPolicyConfig.yaml`.
9. Install the selected managed-settings file under
   `/etc/claude-code/managed-settings.d/`.

## Checks

- Do not use `sudo`, package installers, `docker`, `podman`, or `nvwb` from the
  running container.
- Keep startup path spelling exact: `cache-config`, `agent-audit.txt`,
  `nvwb-agent-config`.
- Tell the user when a host-side restart or rebuild is required.
