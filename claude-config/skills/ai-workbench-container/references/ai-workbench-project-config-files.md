# AI Workbench Configuration Files Reference

## `spec.yaml`

- **Location:** `/project/.project/spec.yaml`
- **Format:** YAML, `specVersion` v2
- **Edit constraints:**
  - Do not add comments.
  - Only edit fields you understand and have explained to the user.
  - Treat `execution.secrets` as sensitive metadata; never print or log secret values.
- **Common editable fields:**
  - `environment.base.apps`
  - `execution.apps`
- **Effect of changes:** Container restart is usually required; package/base image changes may require rebuild.
- **Validation:** Tell the user to run host-side `nvwb validate project-spec` after edits.

## `apt.txt`

- **Location:** `/project/apt.txt`
- **Format:** One apt package name per line.
- **Edit constraints:** Avoid inline comments. Comments on their own line are accepted by apt processing in many projects but are best avoided for generated edits.
- **Runs:** After `preBuild.bash`, before `requirements.txt` and `postBuild.bash`.
- **Effect of changes:** Container rebuild required.

Example:

```text
poppler-utils
python3-pil
tesseract-ocr
libtesseract-dev
```

## `requirements.txt`

- **Location:** `/project/requirements.txt`
- **Format:** Standard pip requirements format.
- **Edit constraints:**
  - Avoid inline comments.
  - Do not add `--index-url` or `--extra-index-url`; packages requiring custom indexes should be installed in `preBuild.bash` before requirements processing.
- **Runs:** After `preBuild.bash`, before `postBuild.bash`.
- **Effect of changes:** Container rebuild required.

Example:

```text
jupyterlab>3.0
langchain==0.3.15
fastapi==0.111.0
gradio
torch>=2.0
```

## `preBuild.bash`

- **Location:** `/project/preBuild.bash`
- **Format:** Bash script, executable.
- **Edit constraints:** Do not reference files in `/project`; the project directory is not mounted during build.
- **Privileges:** Passwordless `sudo` is available during build.
- **Runs:** Before `apt.txt`, `requirements.txt`, and `postBuild.bash`.
- **Effect of changes:** Container rebuild required.

## `postBuild.bash`

- **Location:** `/project/postBuild.bash`
- **Format:** Bash script, executable.
- **Edit constraints:** Do not reference files in `/project`; the project directory is not mounted during build.
- **Privileges:** Passwordless `sudo` is available during build.
- **Runs:** After `preBuild.bash`, `apt.txt`, and `requirements.txt`, before container run.
- **Effect of changes:** Container rebuild required.
- **Available variables:** `$NVWB_UID` and `$NVWB_GID` for file ownership.

## `variables.env`

- **Location:** `/project/variables.env`
- **Format:** `KEY=VALUE`, one per line.
- **Edit constraints:**
  - Preserve existing comments.
  - Do not add new comments.
  - Do not print or log secret values.
- **Runs:** Sourced at runtime.
- **Effect of changes:** Container restart required.

## Compose Files

- **Location:** Defined by `environment.compose_file_path` in `/project/.project/spec.yaml`; check that field before editing.
- **Common names:** `compose.yaml`, `docker-compose.yaml`, `docker-compose.yml`.
- **Edit constraints:**
  - Do not edit unrelated compose files in the repository.
  - Do not change `external: true` on Workbench-managed networks.
  - Do not hardcode or replace Workbench-injected variables such as `${USERID}`, `${MODEL_DIRECTORY}`, and `${NVWB_TRIM_PREFIX}`.
  - Set `NVWB_TRIM_PREFIX: true` only on browser-facing frontend services.
  - Preserve YAML anchors and aliases.
- **Effect of changes:** Compose restart required.
- **Profiles:** Services without a profile always start. Services with a profile start only when that profile is selected; understand existing profiles before adding services.

### NIM Service Pattern

- Use `runtime: nvidia` and `deploy.resources.reservations.devices` for GPU access.
- Use `device_ids` to avoid GPU conflicts between services.
- Mount model cache to `/opt/nim/.cache` using `${MODEL_DIRECTORY:-/tmp}`.
- Set `user: "${USERID}"`.

## `/project/README.md`

- **Special behavior:** The `## Get Started` section renders in the Workbench UI.
- Keep that section as a short quick-start guide.
- Removing the section removes the Workbench UI widget.

## Runtime vs Build Privileges

| Context | `sudo` available? |
| --- | --- |
| Running container | No; it runs as the `workbench` user. |
| `preBuild.bash` / `postBuild.bash` | Yes; passwordless sudo is available during build. |

System-level changes belong in build scripts or `apt.txt`, not in the running container.

## Summary: What Triggers What

| File | Change requires |
| --- | --- |
| `apt.txt` | Rebuild |
| `requirements.txt` | Rebuild |
| `preBuild.bash` | Rebuild |
| `postBuild.bash` | Rebuild |
| `variables.env` | Restart |
| `spec.yaml` application or mount fields | Restart |
| `spec.yaml` package/base image fields | Rebuild |
| Active compose file | Compose restart |
