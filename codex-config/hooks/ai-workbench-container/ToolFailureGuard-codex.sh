#!/usr/bin/env bash
set -u

config_path="/home/workbench/.codex/config.toml"
source_path="$config_path"

reference_skill="/home/workbench/.codex/skills/ai-workbench-container/SKILL.md"
if [[ ! -f "$reference_skill" ]]; then
  reference_skill="unavailable"
fi

payload="$(cat)"

if ! printf '%s' "$payload" | jq -e . >/dev/null 2>&1; then
  exit 0
fi

if [[ ! -r "$config_path" ]]; then
  printf 'WORKBENCH_TOOL_GUARD_ERROR source=%s reason=config_unreadable reference_skill=%s\n' "$source_path" "$reference_skill"
  exit 0
fi

lookup_mode() {
  local key="$1"
  awk -v key="$key" '
    {
      line = $0
      sub(/#.*/, "", line)
      if (match(line, /^[ \t]*"[^"]+"[ \t]*=[ \t]*"(read|deny|write)"/)) {
        split(line, parts, "\"")
        if (parts[2] == key) {
          print parts[4]
          exit
        }
      }
    }
  ' "$config_path"
}

emit_if_blocked() {
  local path="$1"
  local mode=""
  local tilde_path=""

  mode="$(lookup_mode "$path")"
  if [[ -z "$mode" && "$path" == /home/workbench/* ]]; then
    tilde_path="~/${path#/home/workbench/}"
    mode="$(lookup_mode "$tilde_path")"
  fi

  case "$mode" in
    read)
      printf 'WORKBENCH_TOOL_GUARD_BLOCKED path=%s reason=read_only source=%s reference_skill=%s\n' "$path" "$source_path" "$reference_skill"
      return 0
      ;;
    deny)
      printf 'WORKBENCH_TOOL_GUARD_BLOCKED path=%s reason=protected source=%s reference_skill=%s\n' "$path" "$source_path" "$reference_skill"
      return 0
      ;;
  esac

  return 1
}

paths="$(
  printf '%s\n' "$payload" |
    jq -r '.. | strings' |
    grep -Eo '(/project|/home/workbench)(/[A-Za-z0-9._+@%=-]+)+' 2>/dev/null |
    sed 's/[).,:;]*$//' |
    awk '!seen[$0]++'
)"

if [[ -z "$paths" ]]; then
  exit 0
fi

while IFS= read -r path; do
  if [[ -n "$path" ]] && emit_if_blocked "$path"; then
    exit 0
  fi
done <<< "$paths"

exit 0
