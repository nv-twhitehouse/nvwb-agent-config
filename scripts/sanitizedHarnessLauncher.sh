#!/bin/bash

set -euo pipefail

spec_file="${WORKBENCH_SPEC_FILE:-/project/.project/spec.yaml}"

usage() {
  echo "Usage: $0 <command> [args...]" >&2
}

env_unset_args=()

add_unset_name() {
  local name="$1"

  if [[ -n "$name" && "$name" != *"="* ]]; then
    env_unset_args+=("-u" "$name")
  fi
}

list_workbench_secret_names() {
  if [[ ! -r "$spec_file" ]]; then
    return 0
  fi

  if ! command -v yq >/dev/null 2>&1; then
    echo "yq is required to read Workbench secrets from $spec_file" >&2
    exit 1
  fi

  yq -r '
    .execution.secrets[]?
    | if type == "object" then (.variable // .name // .key // empty) else . end
    | select(type == "string" and length > 0)
  ' "$spec_file"
}

add_secret_like_environment() {
  local entry
  local name

  while IFS= read -r -d '' entry; do
    name="${entry%%=*}"

    case "$name" in
      AWS_*|AZURE_*|GCP_*|GOOGLE_*|NVIDIA_API_KEY|OPENAI_API_KEY|GITHUB_TOKEN|*_TOKEN|*_SECRET|*_KEY|*-TOKEN|*-SECRET|*-KEY|*PASSWORD*)
        add_unset_name "$name"
        ;;
    esac
  done < <(env -0)
}

add_workbench_secrets() {
  local name

  while IFS= read -r name; do
    add_unset_name "$name"
  done < <(list_workbench_secret_names | sort -u)
}

if [[ "$#" -eq 0 ]]; then
  usage
  exit 64
fi

add_secret_like_environment
add_workbench_secrets

exec env "${env_unset_args[@]}" "$@"
