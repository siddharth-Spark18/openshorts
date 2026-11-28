"""Exercise cleanup ordering without touching a real Docker daemon."""
import os
from pathlib import Path
import subprocess


SCRIPT = Path(__file__).resolve().parents[1] / 'ops' / 'deploy-private.sh'


def run_deploy(tmp_path, fail_build=False):
    docker = tmp_path / 'docker'
    docker.write_text('''#!/bin/sh
printf '%s\\n' "$*" >> "$DOCKER_LOG"
case "$*" in
  *'exec -T backend python'*) exit 1 ;;
  *'up --build -d'*) [ "${FAIL_BUILD:-0}" = 1 ] && exit 1 ;;
esac
exit 0
''')
    docker.chmod(0o755)
    log = tmp_path / 'docker.log'
    env = {**os.environ, 'PATH': f"{tmp_path}:{os.environ['PATH']}",
           'DOCKER_LOG': str(log), 'FAIL_BUILD': '1' if fail_build else '0'}
    result = subprocess.run(['sh', str(SCRIPT)], env=env, capture_output=True, text=True)
    return result, log.read_text().splitlines()


def test_cleanup_keeps_recent_cache_and_runs_image_cleanup_after_success(tmp_path):
    result, calls = run_deploy(tmp_path)
    assert result.returncode == 0
    cache = calls.index('builder prune --force --filter until=168h')
    build = calls.index('compose -f docker-compose.private.yml up --build -d')
    images = calls.index('image prune --force --filter until=168h')
    assert cache < build < images
    assert not any('volume prune' in call or 'system prune' in call for call in calls)


def test_failed_build_does_not_remove_old_images(tmp_path):
    result, calls = run_deploy(tmp_path, fail_build=True)
    assert result.returncode != 0
    assert not any(call.startswith('image prune ') for call in calls)
