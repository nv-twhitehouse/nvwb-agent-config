#!/bin/bash

set -u

echo "$(pwd)" > /tmp/codex_start_dir 2>/dev/null || true

if [ ! -f /project/.project/spec.yaml ]; then
  exit 0
fi

skill_path="$HOME/.agents/skills/ai-workbench-container"
if [ ! -d "$skill_path" ] && [ -d "$HOME/.codex/skills/ai-workbench-container" ]; then
  skill_path="$HOME/.codex/skills/ai-workbench-container"
fi

mkdir -p /project/.codex 2>/dev/null || true

if [ ! -f /project/AGENTS.md ]; then
  cat <<'EOF' > /project/AGENTS.md
# Context for this project

## This is an AI Workbench Project

- This is a container.
- The project repository is at `/project`.
- The Workbench project specification is `/project/.project/spec.yaml`.
- Use the `ai-workbench-container` skill for Workbench project structure, runtime config, build scripts, compose files, mounts, and GPU/container behavior.

EOF
fi

redact_workbench_spec() {
  awk '
    function leading_spaces(s) {
      match(s, /^[ ]*/)
      return RLENGTH
    }
    /^[[:space:]]*secrets:[[:space:]]*$/ {
      line = $0
      sub(/secrets:.*/, "secrets: <redacted>", line)
      print line
      redacting = 1
      secret_indent = leading_spaces($0)
      next
    }
    redacting {
      indent = leading_spaces($0)
      if ($0 ~ /^[[:space:]]*$/ || indent > secret_indent) {
        next
      }
      redacting = 0
    }
    { print }
  ' /project/.project/spec.yaml
}

redact_toml_secrets() {
  sed -E 's/^([[:space:]]*[^#[:space:]]*(token|secret|password|api_key|apikey|bearer)[^=]*=).*/\1 "<redacted>"/I'
}

cat <<EOF
==============Codex Workbench Context===============
This is an AI Workbench project container.

The project Git repository is located at \`/project\`.
The project structure is described in \`/project/.project/spec.yaml\`.
Use the Workbench container skill at \`$skill_path\` when applicable.

EOF

echo "This is the project spec.yaml file with secrets redacted."
echo
redact_workbench_spec

if [ -f "$HOME/.codex/config.toml" ]; then
  echo
  echo "These are the current settings from ~/.codex/config.toml with secret-like values redacted."
  echo
  redact_toml_secrets < "$HOME/.codex/config.toml"
fi

if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi >/dev/null 2>&1; then
  echo
  echo "GPUs are available in this container. nvidia-smi summary:"
  nvidia-smi --query-gpu=index,name,memory.total --format=csv,noheader
fi
