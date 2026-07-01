#!/usr/bin/env bash
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SUMMARY="/home/workbench/cache-config/logs/bwrap-summary.txt"

fail=0
pass_count=0
fail_count=0
declare -a results=()

check() {
  local name="$1" desc="$2"
  shift 2

  if "$@" >/dev/null 2>&1; then
    results+=("PASS  $desc")
    ((pass_count++))
  else
    results+=("FAIL  $desc")
    ((fail_count++))
    fail=1
  fi
}

check "basic_bwrap" \
  "Can launch a sandbox" \
  bwrap --ro-bind / / true

check "filesystem_construction" \
  "Can build a custom filesystem layout" \
  bwrap \
    --ro-bind /usr /usr \
    --ro-bind /lib /lib \
    --ro-bind /lib64 /lib64 \
    --proc /proc \
    --dev /dev \
    /usr/bin/true

check "readonly_root_blocks_write" \
  "Read-only root prevents writes" \
  bwrap --ro-bind / / sh -c '! touch /etc/bwrap-write-test'

check "private_tmp_writable" \
  "Private /tmp is writable" \
  bwrap --ro-bind / / --tmpfs /tmp sh -c 'touch /tmp/bwrap-tmp-test'

check "minimal_runtime" \
  "Minimal runtime works (no full root)" \
  bwrap \
    --ro-bind /usr /usr \
    --ro-bind /lib /lib \
    --ro-bind /lib64 /lib64 \
    --dir /tmp \
    /usr/bin/env true

check "proc_mount" \
  "Can mount /proc inside sandbox" \
  bwrap --ro-bind / / --proc /proc sh -c 'test -r /proc/self/status'

check "user_namespace" \
  "User namespace isolation" \
  bwrap --unshare-user --uid 0 --gid 0 --ro-bind / / id -u

check "pid_namespace" \
  "PID namespace isolation" \
  bwrap --unshare-pid --as-pid-1 --ro-bind / / sh -c 'test "$$" = 1'

check "network_namespace_loopback_setup" \
  "Network namespace isolation" \
  bwrap --unshare-net --ro-bind / / --proc /proc sh -c 'test -e /proc/self/ns/net'

check "ipc_namespace" \
  "IPC namespace isolation" \
  bwrap --unshare-ipc --ro-bind / / true

check "uts_hostname_change" \
  "Can change hostname in sandbox" \
  bwrap --unshare-uts --hostname test-bwrap --ro-bind / / hostname

check "synthetic_dev" \
  "Synthetic /dev mount works" \
  bwrap --dev /dev --ro-bind / / true

check "synthetic_dev_nodes" \
  "Device nodes (/dev/null, /dev/zero) available" \
  bwrap --ro-bind / / --dev /dev sh -c 'test -c /dev/null && test -c /dev/zero'

check "clearenv" \
  "Can clear and set environment variables" \
  bwrap --ro-bind / / --clearenv --setenv EXPECTED ok sh -c 'test "$EXPECTED" = ok && test -z "${HOME:-}"'

check "unshare_all_share_net" \
  "Full isolation with shared network" \
  bwrap --unshare-all --share-net --ro-bind / / true

total=$((pass_count + fail_count))

{
  printf '=== bwrap sandbox readiness ===\n'
  printf 'WARNING: bwrap is a lightweight sandbox, not a security boundary.\n'
  printf 'These checks confirm bwrap functionality only. Passing does NOT mean\n'
  printf 'the environment is secure or that sandboxed code cannot cause harm.\n'
  printf 'Do not rely on bwrap as a substitute for proper security controls.\n\n'
  if [ "$fail" -eq 0 ]; then
    printf 'Result: ALL %d CHECKS PASSED\n\n' "$total"
  else
    printf 'Result: %d/%d PASSED, %d FAILED\n\n' "$pass_count" "$total" "$fail_count"
  fi
  printf '%s  %s\n' "bwrap" "$(bwrap --version 2>/dev/null || echo 'not found')"
  printf '\n'
  for r in "${results[@]}"; do
    printf '  %s\n' "$r"
  done
  if [ "$fail" -ne 0 ]; then
    printf '\nFailed checks may prevent the agent sandbox from working correctly.\n'
  fi
} | tee "$SUMMARY"

exit "$fail"
