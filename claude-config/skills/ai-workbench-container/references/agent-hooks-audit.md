# Agent Hooks And Audit

Read this before editing Claude/Codex hooks, skills, cache/audit behavior, or
sanitized launch behavior.

## Hook Contracts

- Codex `SessionStart`: plain stdout can be model-visible context.
- Claude `SessionStart`: emit JSON with
  `hookSpecificOutput.hookEventName = "SessionStart"` and
  `hookSpecificOutput.additionalContext`.
- Hooks should report compact context and append audit entries only.
- Hooks should not recreate symlinks, render policy, seed files, or repair drift.

## Audit

- Audit entries go to `/home/workbench/cache-config/logs/agent-audit.txt`.
- Logging resolved hook path and SHA-256 is useful traceability, not
  tamper-proofing.
- If audit logging fails, surface a compact diagnostic in the hook context.

## Runtime Links

Source:

```text
claude-config/hooks/
claude-config/skills/
codex-config/hooks/
codex-config/skills/
```

Runtime:

```text
~/.claude/hooks/
~/.claude/skills/
~/.codex/hooks/
~/.codex/skills/
```

## Checks

- Run `bash -n` for edited shell hooks or launch scripts.
- Execute edited hooks once and inspect their output contract.
- Search for stale reference paths after moving or renaming skill files.
