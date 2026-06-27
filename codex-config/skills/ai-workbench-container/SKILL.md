---
name: ai-workbench-container
description: Use when working in a Linux environment that has `/project/.project/spec.yaml`. This skill covers NVIDIA AI Workbench project/container structure, runtime configuration, build/restart requirements, mounts, compose files, GPU/container constraints, and the nvwb-agent-config startup/policy pipeline including `/project/onStart.bash`, `/project/agentPolicyConfig.yaml`, `agentPolicyTemplate.yaml`, `scripts/renderPolicy.py`, hooks, skills, cache, audit, and managed settings.
---

# NVIDIA AI Workbench In-Container Project Awareness

Use this skill when Codex is executing inside an AI Workbench project container
or when the user asks about Workbench project files under `/project`.

## What Not To Do

- Do not use `sudo` in the running container.
- Do not install packages into the running container with `pip install`, `pip3 install`, `python -m pip install`, or similar package managers unless the user explicitly overrides this rule.
- Do not edit `/project/.project/*` without consulting the user first.
- Do not run `nvwb` commands; the Workbench CLI is host-side and is not available here.
- Do not print or log secret values from environment variables, credentials files, or any variables listed in `execution.secrets` in `/project/.project/spec.yaml`.
- Do not make SessionStart hooks a second implementation of `onStart.bash`;
  startup setup and repair belong in `onStart.bash` or a shared helper. The
  narrow exception is lazy seeding of the agent-specific project guidance file
  on first agent launch.

## What To Do

- When a user request would hit a Workbench guardrail, explain the managed
  container constraint and offer the supported path instead of first attempting
  the blocked command.
- For Python packages, guide the user to the AI Workbench Desktop App package
  installer. It updates `requirements.txt`, installs the package into the
  running container, and includes it in the image on the next build. Offer to
  edit `requirements.txt` directly only when the user wants the dependency
  recorded without immediate in-container installation by Workbench.
- For system packages or `apt-get`, edit `apt.txt`, `preBuild.bash`, or
  `postBuild.bash` and tell the user a container rebuild is required.
- For `sudo`, explain that runtime escalation is unavailable and use a
  build-time file instead.
- For `docker`, `podman`, or `nvwb`, explain that those are host-side Workbench
  actions and ask the user to run them outside the container.
- Tell the user to rebuild the container after editing:
  - `/project/requirements.txt`
  - `/project/apt.txt`
  - `/project/postBuild.bash`
  - `/project/preBuild.bash`
- Tell the user to restart the container after editing:
  - `/project/variables.env`
  - A bind mount configuration field in `/project/.project/spec.yaml`
  - An application configuration field in `/project/.project/spec.yaml`
- Tell the user to restart the Compose application after editing:
  - `compose.yaml`, `docker-compose.yaml`, or `docker-compose.yml` in the active Workbench compose path
- For persistent storage, tell the user to add a Workbench mount because Codex cannot configure host mounts from inside the container.
  - Tell the user whether a volume mount or bind mount is needed.
  - Provide the target path.
  - For bind mounts, tell the user they must choose the host source path.
- When editing the nvwb-agent-config pipeline, keep the policy input, renderer, startup script, hooks, and harness defaults in their separate roles.

## When Informing The User

After editing a build-time or runtime file, always state the required host-side
action. Examples:

> I updated `requirements.txt` to add `transformers`. To install it into the running container now, use the AI Workbench Desktop App package installer; otherwise it will be included after the next container rebuild.

> I added `CUDA_VISIBLE_DEVICES=0` to `variables.env`. Restart the container for the runtime environment change to take effect.

> I updated the active Compose file to add a database service. Restart the Compose application from Workbench for the service graph to update.

## References

Read `references/ai-workbench-project-config-files.md` before editing Workbench configuration files.
Read `references/agent-config-startup.md` before editing `onStart.bash`, startup symlinks, policy seed files, sanitized launch aliases, or managed-settings install behavior.
Read `references/agent-policy-rendering.md` before editing `agentPolicyConfig.yaml`, `agentPolicyTemplate.yaml`, `scripts/renderPolicy.py`, or Claude/Codex rendered config mappings.
Read `references/agent-hooks-audit.md` before editing Claude/Codex hooks, skills, cache/audit behavior, or sanitized launch behavior.
