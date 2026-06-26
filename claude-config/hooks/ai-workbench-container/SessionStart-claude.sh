#!/bin/bash

if [[ ! -f /project/.project/spec.yaml ]]; then
  exit 0
fi

cache_config_path="/home/workbench/cache-config"
audit_log="$cache_config_path/logs/agent-audit.txt"
current_working_dir="$(pwd)"
current_script="${BASH_SOURCE[0]}"
issues=()

add_issue() {
  issues+=("$1")
}

resolved_script="$current_script"
if command -v readlink >/dev/null 2>&1; then
  resolved_script="$(readlink -f "$current_script" 2>/dev/null || echo "$current_script")"
fi

hook_hash="unavailable"
if command -v sha256sum >/dev/null 2>&1 && [[ -f "$resolved_script" ]]; then
  hook_hash="$(sha256sum "$resolved_script" | awk '{print $1}')"
fi

if [[ ! -f "$audit_log" ]]; then
  add_issue "WARNING: audit log is missing at $audit_log. onStart.bash may not have completed cache setup."
elif ! echo "$(date '+[%Y-%m-%d %H:%M:%S]')_____Claude Code started in $current_working_dir hook_path=$resolved_script hook_sha256=$hook_hash" >> "$audit_log"; then
  add_issue "WARNING: failed to append Claude Code start event to $audit_log."
fi

skill_path="$HOME/.claude/skills/ai-workbench-container"
if [[ ! -d "$skill_path" ]]; then
  skill_path="not found"
fi

gpu_context="This container does not have an NVIDIA GPU mounted."
if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi >/dev/null 2>&1; then
  smi_output="$(nvidia-smi --query-gpu=index,name,memory.total --format=csv,noheader)"
  gpu_context="This container has mounted NVIDIA GPUs. 'nvidia-smi' shows: $smi_output"
fi

context="$(cat <<EOF
===================Claude Workbench Context===========================
This is an AI Workbench project container.
The project Git repository is located at \`/project\`.
The project structure is described in \`/project/.project/spec.yaml\`.
Use the Workbench container skill when touching Workbench structure, runtime config, build scripts, compose files, mounts, or GPU/container behavior.
Resolved Workbench skill path: \`$skill_path\`.
$gpu_context
EOF
)"

if ((${#issues[@]})); then
  diagnostics="$(printf '\n\nWorkbench setup diagnostics:\n'; printf '%s\n' "${issues[@]}")"
  context="${context}${diagnostics}"
fi

jq -n --arg context "$context" '
{
  hookSpecificOutput: {
    hookEventName: "SessionStart",
    additionalContext: $context
  }
}'
