---
name: ai-workbench-container
description: Use when working in a Linux environment that has `/project/.project/spec.yaml`. This skill covers NVIDIA AI Workbench project/container structure, runtime configuration, build/restart requirements, mounts, compose files, and GPU/container constraints.
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

## What To Do

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

## When Informing The User

After editing a build-time or runtime file, always state the required host-side
action. Examples:

> I updated `requirements.txt` to add `transformers`. You need to rebuild the container before that package is available.

> I added `CUDA_VISIBLE_DEVICES=0` to `variables.env`. Restart the container for the runtime environment change to take effect.

> I updated the active Compose file to add a database service. Restart the Compose application from Workbench for the service graph to update.

## References

Read `references/config-files.md` before editing Workbench configuration files.
