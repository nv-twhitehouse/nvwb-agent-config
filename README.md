# Agent Configuration for AI Workbench Projects

This repository contains reusable agent configuration for NVIDIA AI Workbench
project containers. It is intended to be cloned into a specific volume mount
within the project container, and then have files and subfolders copied or 
symlinked into the locations expected by Claude Code and the Codex CLI runtime.

The goal is to keep agent behavior configurable and predictable across projects
while preserving the distinction between Claude Code and Codex configuration models.

## Who This Is For

Use this repository if you want a repeatable baseline for coding agents inside
AI Workbench project containers.

This is most useful when you want agents to consistently understand:

- The project lives at `/project`.
- Workbench project metadata lives under `/project/.project`.
- Some file edits require a container rebuild, restart, or Compose restart.
- Runtime containers should not be mutated with ad hoc `sudo` or package installs.
- Agent auth and local state should stay out of project repos and logs.

## Repository Layout

```text
claude-config/
  CLAUDE.md
  settings.json
  hooks/
  skills/

codex-config/
  config.toml
  AGENTS.md
  hooks.json
  hooks/
  rules/
  skills/
```

Claude and Codex use similar concepts, but they do not use the same file paths
or the same configuration format.

## Claude vs Codex

### Claude Code

Claude Code primarily uses `~/.claude`.

Typical runtime targets:

```text
claude-config/settings.json -> ~/.claude/settings.json
claude-config/hooks/        -> ~/.claude/hooks/
claude-config/skills/       -> ~/.claude/skills/
```

Claude project guidance commonly lives in:

```text
/project/CLAUDE.md
/project/.claude/
```

### Codex

Codex splits configuration and skills across two locations.

Typical runtime targets:

```text
codex-config/config.toml -> ~/.codex/config.toml
codex-config/AGENTS.md   -> ~/.codex/AGENTS.md
codex-config/hooks.json  -> ~/.codex/hooks.json
codex-config/hooks/      -> ~/.codex/hooks/
codex-config/rules/      -> ~/.codex/rules/
```

Codex user skills are discovered from:

```text
codex-config/skills/<skill>/ -> ~/.agents/skills/<skill>/
```

Codex project guidance commonly lives in:

```text
/project/AGENTS.md
/project/.codex/
/project/.agents/skills/
```

## Setup Model

There are two common ways to use this repository.

### Option 1: Symlink

Use symlinks when you want changes in this repository to take effect immediately
after restarting the agent.

This is convenient for developing the configuration itself.

### Option 2: Copy

Use copies when you want each container or project to receive a stable snapshot.

This is safer when experimenting with hooks, rules, or agent behavior that could
interrupt normal work.

## Basic Setup

Clone or mount this repository somewhere inside the container, then create the
agent configuration directories:

```bash
mkdir -p "$HOME/.claude" "$HOME/.codex" "$HOME/.agents/skills"
```

Install the Claude configuration by copying or symlinking the contents of
`claude-config/` into `~/.claude/`.

Install the Codex configuration by copying or symlinking the Codex control files
into `~/.codex/`, and Codex skills into `~/.agents/skills/`.

Restart the agent after changing configuration, hooks, rules, or skills.

## Project-Level Files

User-level configuration sets the baseline. Project-level files should describe
what is specific to the project repository.

For Claude:

```text
/project/CLAUDE.md
/project/.claude/
```

For Codex:

```text
/project/AGENTS.md
/project/.codex/
/project/.agents/skills/
```

Prefer project-level files for build commands, test commands, repo conventions,
and project-specific constraints.

## Hooks, Rules, and Skills

This repository separates three concerns:

- Skills provide reusable workflow knowledge.
- Hooks automate context injection, auditing, and policy checks.
- Rules define command approval or blocking behavior where the agent supports it.

Keep hooks small and deterministic. Keep rules narrow. Put longer explanatory
material in skills or project guidance instead of hook scripts.

## Authentication and Local State

Do not commit agent credentials, local histories, transcripts, or generated
state into this repository.

Use persistent private volumes for agent auth files when containers need login
state across restarts.

## Customizing for a Project

Start with the global defaults from this repository, then add project-specific
guidance inside `/project`.

Project-specific guidance should answer:

- How do I build and test this project?
- Which files are generated?
- Which commands are safe to run automatically?
- Which changes require a Workbench rebuild or restart?
- Which files contain secrets or environment-specific state?

## Status

This repository is a configuration scaffold. Review hook behavior, command
rules, and permission boundaries before using it as an enforced policy layer.
