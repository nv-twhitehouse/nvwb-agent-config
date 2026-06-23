# AI Workbench Configuration Files Reference

## `spec.yaml`

- **Location:** `/project/.project/spec.yaml` 
- **Format:** YAML (specVersion v2)
- **Edit Constraints:** 
  - Do NOT enter comments
  - ONLY edit the following fields
    - `environment.base.apps` (Configures applications that are installed in the base image)
    - `execution.apps` (Configures applications that installed during the container build or by the user)
- **Effect of changes:** Container restart required
- **Validation:** Tell the user to run `nvwb validate project-spec` after any edits


## `apt.txt`

- **Location:** `/project/apt.txt` 
- **Format:** One apt package name per line
- **Edit Constraints:** Do NOT enter inline comments - they will break package installation. Comments on their own line are allowed but not recommended.
- **Runs:** After `preBuild.bash` script and before `requirements.txt` and `postBuild.bash` script
- **Effect of changes:** Container rebuild required
- **Example:**
```
poppler-utils
python3-pil
tesseract-ocr
libtesseract-dev
```

## `requirements.txt`

- **Location:** `/project/requirements.txt` 
- **Format:** Standard pip requirements format (supports version pinning, extras)
- **Edit Constraints:**
  - Do NOT enter inline comments - they will break package installation. Comments on their own line are allowed but not recommended.
  - Do NOT use `--index-url` or `--extra-index-url` — if a package requires a custom index (e.g. PyTorch with a specific CUDA wheel), install it in `preBuild.bash` instead so it is available before requirements.txt is processed
- **Runs:** After `preBuild.bash` script and before `postBuild.bash` script
- **Effect of changes:** Container rebuild required
- **Example:**
```
jupyterlab>3.0
langchain==0.3.15
fastapi==0.111.0
gradio
torch>=2.0
```

## `preBuild.bash`

- **Location:** `/project/preBuild.bash`
- **Format:** Bash script (must be executable)
- **Edit Constraints:** Do NOT reference any files in `/project/` - the project directory is not mounted during build
- **Sudo:** Is available 
- **Runs:** Before `apt.txt` and `requirements.txt` and `postBuild.bash`
- **Effect of changes:** Container rebuild required
- **Example:**
```bash
#!/bin/bash
# Runs before package install
pip install --upgrade pip
```

## `postBuild.bash`

- **Location:** `/project/postBuild.bash`
- **Format:** Bash script (must be executable)
- **Edit Constraints:** Do NOT reference any files in `/project/` - the project directory is not mounted during build
- **Runs:** After `preBuild.bash` and `apt.txt` and `requirements.txt` but before container run
- **Sudo:** Is available
- **Effect of changes:** Requires container rebuild
- **Available variables:** `$NVWB_UID`, `$NVWB_GID` for file ownership
- **Example:**
```bash
#!/bin/bash
# Runs after package install
# Can use sudo for extra system installs
sudo apt-get update && sudo apt-get install -y some-package
# Fix ownership for directories created during build
chown -R $NVWB_UID:$NVWB_GID /some/path
```

## `variables.env`

- **Location:** `/project/variables.env`
- **Format:** `KEY=VALUE` (one per line)
- **Edit Constraints:**
  - Do NOT edit existing comments in the file
  - Do NOT add comments
- **Runs:** Sourced at runtime
- **Effect of changes:** Requires container restart 
- **Example:**
```
# Runtime environment variables
TENSORBOARD_LOGS_DIRECTORY=/data/tensorboard/logs/
MAX_CONCURRENT_REQUESTS=1
API_SERVICE_URL=http://pdf-to-podcast-api-service-1:8002
AI_WORKBENCH_FLAG=true
```

## `compose.yaml` / `docker-compose.yaml`

- **Location:** Defined in `environment.compose_file_path` in `/project/.project/spec.yaml`. Always check this field before editing any compose file.
- **Edit Constraints:**
  - Do NOT edit any other compose files in the repository — there may be several
  - Do NOT change `external: true` on network definitions — this joins a network managed by another compose deployment
  - Do NOT hardcode or replace Workbench-injected variables: `${USERID}`, `${MODEL_DIRECTORY}`
  - Do NOT set `NVWB_TRIM_PREFIX: true` on backend, database, or internal services — only set it on browser-facing frontend services
  - Preserve YAML anchors (`&name`) and aliases (`<<: *name`) when editing services that use them
- **Effect of changes:** Compose restart required
- **Profiles:** Services without a profile always start. Services with a profile only start when that profile is selected. Profiles can represent optional services, deployment variants, or mutually exclusive configurations (e.g. `aira-gpu` vs `aira-no-gpu`). Always understand the existing profile structure before adding a service.
- **Workbench-injected variables:**
  - `${USERID}` — injected by Workbench, used for NIM service user context
  - `${MODEL_DIRECTORY}` — path to NIM model cache, typically set by the user
  - `${NVWB_TRIM_PREFIX}` — set to `true` only on browser-facing services to enable proxy routing through the Workbench Desktop App
- **Build contexts:** If the compose file is in a subdirectory (e.g. `deploy/workbench/`), build contexts use relative paths like `../../` to reach the project root
- **NIM services pattern:**
  - Use `runtime: nvidia` and `deploy.resources.reservations.devices` for GPU access
  - Use `device_ids` to assign specific GPUs, avoiding conflicts with other services
  - Mount model cache to `/opt/nim/.cache` using `${MODEL_DIRECTORY:-/tmp}`
  - Set `user: "${USERID}"`

## `/project/README.md`

- **Location:** Project root
- **Special behavior:** The `## Get Started` section is rendered in the Workbench UI when a user opens the project — keep it as a short bulleted quick-start guide (e.g. "Start JupyterLab → open this notebook → run all cells"). Removing the section entirely removes the widget from the UI.

## Runtime vs Build Privileges

| Context | `sudo` available? |
|---|---|
| Running container (terminal, app) | No — runs as `workbench` user |
| `preBuild.bash` / `postBuild.bash` | Yes — passwordless sudo during build |

System-level changes must go in the build scripts — `sudo` is not available in a running container.

## Summary: What Triggers What

| File | Change Requires 
|---|---|
| `apt.txt` | Rebuild 
| `requirements.txt` | Rebuild 
| `preBuild.bash` | Rebuild 
| `postBuild.bash` | Rebuild
| `variables.env` | Restart 
| `spec.yaml` (apps) | Restart 
| `spec.yaml` (packages) | Rebuild
| `spec.yaml` (mounts) | Restart
| `compose.yaml` | Recompose 
