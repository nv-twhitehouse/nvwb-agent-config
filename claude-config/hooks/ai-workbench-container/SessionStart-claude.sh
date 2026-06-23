#!/bin/bash


project_context=""
smi_output=""
context_output=""

# Check if Claude is in a project container; 
if [[ -f /project/.project/spec.yaml ]]; then
  project_context="$(cat <<'EOF'
This is an AI Workbench project container. The project repo is located at /project/ in the container. 
Use the relevant skills in ~/.claude/skills/ai-workbench-container.
EOF
  )"
else 
  exit 0
fi

# Check if we are in a container with mounted GPUs.
if command -v nvidia-smi &>/dev/null && nvidia-smi &> /dev/null; then
  nvidia_smi_output="$(nvidia-smi --query-gpu=index,name,memory.total --format=csv,noheader)"
  smi_output="This container has mounted NVIDIA GPUs. 'nvidia-smi' shows: $nvidia_smi_output"
else
  smi_output="This container does not have an NVIDIA GPU mounted."
fi

context_output="$(printf '%s\n\n%s' "$project_context" "$smi_output")"

jq -n --arg context "$context_output" '
{
   hookSpecificOutput: {
      hookEventName: "SessionStart",
      additionalContext: $context}
}'







