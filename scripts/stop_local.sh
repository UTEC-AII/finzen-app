#!/usr/bin/env bash
# Detiene los microservicios levantados con start_local.sh.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

for pid_file in logs/*.pid; do
  [ -f "$pid_file" ] || continue
  pid="$(cat "$pid_file")"
  if kill "$pid" 2>/dev/null; then
    echo "Detenido PID $pid ($pid_file)"
  fi
  rm -f "$pid_file"
done
