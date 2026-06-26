# Agent Policy Rendering

Read this before editing `/project/agentPolicyConfig.yaml`,
`agentPolicyTemplate.yaml`, or `scripts/renderPolicy.py`.

## Ownership

- `agentPolicyConfig.yaml` is the project-owned policy input.
- `agentPolicyTemplate.yaml` only seeds new projects.
- Keep policy tool-agnostic. Put Claude/Codex-specific mapping in
  `renderPolicy.py`.

## Renderer Outputs

- `~/.claude/settings.json`
- `~/.codex/config.toml`
- `cache-config/bypassBlocked.json`
- `cache-config/bypassAllowed.json`
- cached policy/rendered files under `cache-config/`

`renderPolicy.py` also seeds `~/.codex/hooks.json` if it is missing. Existing
Codex hooks are preserved unless `--force-hooks` is used.

## Policy Sections

- `managed_settings_controls`: selects `bypassBlocked` or `bypassAllowed`.
- `workbench`: expected home, project, config repo, and cache paths.
- `paths.write`: paths agents may read and modify.
- `paths.read_only`: paths agents may read but should not modify.
- `paths.private`: paths agents should neither read nor modify.
- `paths.private_project_patterns`: project-relative sensitive globs.
- `commands.ask`: command prefixes requiring confirmation.
- `commands.deny`: commands blocked in the running container.
- `environment`: private env names and patterns to strip or redact.

## Checks

- Run targeted renderer tests after editing `renderPolicy.py`.
- Verify both Claude and Codex outputs when changing policy schema or mappings.
- Never print, log, or summarize secret values.
