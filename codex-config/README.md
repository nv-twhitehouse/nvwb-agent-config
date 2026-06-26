# Codex Configuration

This folder contains source-controlled defaults for Codex in AI Workbench
containers. Runtime setup links stable directories such as hooks, rules, and
skills, and seeds user-owned files such as `hooks.json` when they are missing.

## Target Layout

| Repository path | Runtime target |
| --- | --- |
| `codex-config/config.toml` | `~/.codex/config.toml` |
| `codex-config/AGENTS.md` | `~/.codex/AGENTS.md` |
| `codex-config/hooks.json` | Seed to `~/.codex/hooks.json` if missing |
| `codex-config/hooks/` | `~/.codex/hooks/` |
| `codex-config/rules/` | `~/.codex/rules/` |
| `codex-config/skills/ai-workbench-container/` | `~/.codex/skills/ai-workbench-container/` |

Codex stores user configuration and Workbench-managed skills under `~/.codex`.
Keep the skill source here and symlink or copy it into that target. Treat
`~/.codex/hooks.json` as user-owned after bootstrap; use
`renderPolicy.py --force-hooks` only when intentionally replacing it with the
repository default.

## Install Sketch

From the repository root:

```bash
mkdir -p "$HOME/.codex/skills"
ln -sfn "$PWD/codex-config/config.toml" "$HOME/.codex/config.toml"
ln -sfn "$PWD/codex-config/AGENTS.md" "$HOME/.codex/AGENTS.md"
if [ ! -e "$HOME/.codex/hooks.json" ]; then
  cp "$PWD/codex-config/hooks.json" "$HOME/.codex/hooks.json"
fi
ln -sfn "$PWD/codex-config/hooks" "$HOME/.codex/hooks"
ln -sfn "$PWD/codex-config/rules" "$HOME/.codex/rules"
ln -sfn "$PWD/codex-config/skills/ai-workbench-container" \
  "$HOME/.codex/skills/ai-workbench-container"
find "$PWD/codex-config/hooks" -type f -name '*.sh' -exec chmod +x {} +
```

Restart Codex after changing config, hooks, rules, or skills.
