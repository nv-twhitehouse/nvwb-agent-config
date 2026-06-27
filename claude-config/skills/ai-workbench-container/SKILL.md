---
name: nvwb-project
description: Apply when working in a Linux environment that has a `/project/.project/spec.yaml` file. This skill enforces rules about AI Workbench project and container structure, environment configuration, rebuild/restart requirements, and the nvwb-agent-config startup/policy pipeline including `/project/onStart.bash`, `/project/agentPolicyConfig.yaml`, `agentPolicyTemplate.yaml`, `scripts/renderPolicy.py`, hooks, skills, cache, audit, and managed settings.
user-invocable: false
---

# NVIDIA AI Workbench — In-Container Project Awareness

This skill activates when Claude is executing a task inside an AI Workbench project container. 

## What NOT to Do

- Do NOT use `sudo`
- Do NOT install packages
- Do NOT edit `/project/.project/*` without consulting the user
- Do NOT run `nvwb` commands (Workbench CLI not available here)
- Do NOT print or log any secret environment variables listed in the `execution.secrets` section of `/project/.project/spec.yaml`
- Do NOT make SessionStart hooks a second implementation of `onStart.bash`;
  startup setup and repair belong in `onStart.bash` or a shared helper. The
  narrow exception is lazy seeding of the agent-specific project guidance file
  on first agent launch.

## What To Do

- Tell the user to rebuild the container after doing any of the following:
  - Editing `/project/requirements.txt`
  - Editing `/project/apt.txt`
  - Editing `/project/postBuild.bash`
  - Editing `/project/preBuild.bash`
- Tell the user to restart the container after doing any of the following:
  - Editing `/project/variables.env`
  - Editing a bind mount configuration field in `/project/.project/spec.yaml`
  - Editing an application configuration field in `/project/.project/spec.yaml`
- Tell the user to restart the Compose application after doing any of the following:
  - Editing `compose.yaml` or `docker-compose.yml` in the `/project/` folder
- For persistent storage, tell the user to add a mount (Claude cannot configure mounts from within the container).
  - Tell the user if a volume mount or a bind mount is needed
  - Provide the target path to the user
  - For bind mounts, tell the user they will need to add a source path on the host
- When editing the nvwb-agent-config pipeline, keep the policy input, renderer, startup script, hooks, and harness defaults in their separate roles.

## When Informing the User

After editing a build-time or runtime file, always tell the user what action is needed. Examples:

> I've updated `requirements.txt` to add the `transformers` package. You'll need to rebuild the container to effectuate this change.

> I've added `CUDA_VISIBLE_DEVICES=0` to `variables.env`. This will take effect after a container restart — restart the container to effectuate them.

> I've updated `compose.yaml` to add a vector database service. You'll need to stop and restart the compose environment in the Desktop App for this to take effect.

## References

See `references/ai-workbench-project-config-files.md` for detailed information about each configuration file.
See `references/agent-config-startup.md` before editing `onStart.bash`, startup symlinks, policy seed files, sanitized launch aliases, or managed-settings install behavior.
See `references/agent-policy-rendering.md` before editing `agentPolicyConfig.yaml`, `agentPolicyTemplate.yaml`, `scripts/renderPolicy.py`, or Claude/Codex rendered config mappings.
See `references/agent-hooks-audit.md` before editing Claude/Codex hooks, skills, cache/audit behavior, or sanitized launch behavior.
