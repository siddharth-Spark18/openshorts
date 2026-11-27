#!/bin/sh
# Pause new jobs and wait for running work before building on a small host.
set -eu

compose() { docker compose -f docker-compose.private.yml "$@"; }
paused=0
cleanup() {
  if [ "$paused" = 1 ]; then
    compose exec -T backend python -c 'import os; p="/app/output/.deploy-pause"; os.path.exists(p) and os.unlink(p)' || true
  fi
}
trap cleanup EXIT
trap 'exit 130' HUP INT TERM

if compose exec -T backend python -c 'import urllib.request; urllib.request.urlopen("http://127.0.0.1:8000/health/deployment", timeout=3)' >/dev/null 2>&1; then
  compose exec -T backend python -c 'from pathlib import Path; Path("/app/output/.deploy-pause").touch()'
  paused=1
  echo "Waiting for active processing jobs to finish."
  # The backend returns its in-memory running count after dispatch is paused.
  deadline=$(( $(date +%s) + 4500 ))
  while :; do
    running=$(compose exec -T backend python -c 'import json,urllib.request; print(json.load(urllib.request.urlopen("http://127.0.0.1:8000/health/deployment",timeout=5))["running_jobs"])')
    [ "$running" = 0 ] && break
    if [ "$(date +%s)" -ge "$deadline" ]; then
      echo "Timed out waiting for active jobs; deployment stopped." >&2
      exit 1
    fi
    sleep 15
  done
elif compose ps --status running --services | grep -qx backend; then
  # Older versions cannot pause dispatch. Do not build while a job is active.
  running=$(compose exec -T backend python -c 'import sqlite3; c=sqlite3.connect("/app/output/jobs.db"); print(c.execute("SELECT COUNT(*) FROM jobs WHERE status = ?", ("processing",)).fetchone()[0])')
  if [ "$running" != 0 ]; then
    echo "An active job is running. Retry deployment after it finishes." >&2
    exit 1
  fi
  echo "Existing backend has no deployment pause. Checking jobs again before build."
fi

compose up --build -d
