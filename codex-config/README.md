# Codex Configuration

This folder contains source-controlled defaults for Codex in AI Workbench
containers. Copy or symlink these files into the local agent locations.

## Target Layout

| Repository path | Runtime target |
| --- | --- |
| `codex-config/config.toml` | `~/.codex/config.toml` |
| `codex-config/AGENTS.md` | `~/.codex/AGENTS.md` |
| `codex-config/hooks.json` | `~/.codex/hooks.json` |
| `codex-config/hooks/` | `~/.codex/hooks/` |
| `codex-config/rules/` | `~/.codex/rules/` |
| `codex-config/skills/ai-workbench-container/` | `~/.agents/skills/ai-workbench-container/` |

Codex stores user configuration under `~/.codex`. User-authored global skills
are discovered from `$HOME/.agents/skills`; keep the skill source here and
symlink or copy it into that target.

## Install Sketch

From the repository root:

```bash
mkdir -p "$HOME/.codex" "$HOME/.agents/skills"
ln -sfn "$PWD/codex-config/config.toml" "$HOME/.codex/config.toml"
ln -sfn "$PWD/codex-config/AGENTS.md" "$HOME/.codex/AGENTS.md"
ln -sfn "$PWD/codex-config/hooks.json" "$HOME/.codex/hooks.json"
ln -sfn "$PWD/codex-config/hooks" "$HOME/.codex/hooks"
ln -sfn "$PWD/codex-config/rules" "$HOME/.codex/rules"
ln -sfn "$PWD/codex-config/skills/ai-workbench-container" \
  "$HOME/.agents/skills/ai-workbench-container"
chmod +x "$PWD"/codex-config/hooks/*.sh
```

Restart Codex after changing config, hooks, rules, or skills.
