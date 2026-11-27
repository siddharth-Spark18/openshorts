import os
from pathlib import Path
import subprocess


def test_deploy_pauses_before_build_and_releases_afterward(tmp_path):
    fake = tmp_path / "docker"
    log = tmp_path / "calls.log"
    fake.write_text("""#!/bin/sh
printf '%s\\n' "$*" >> "$DEPLOY_TEST_LOG"
case "$*" in
  *'["running_jobs"]'*) printf '0\\n' ;;
esac
""")
    fake.chmod(0o755)
    env = dict(os.environ, PATH=f"{tmp_path}:{os.environ['PATH']}", DEPLOY_TEST_LOG=str(log))
    script = Path(__file__).resolve().parents[1] / "ops" / "deploy-private.sh"
    subprocess.run(["sh", str(script)], env=env, check=True, timeout=10)
    calls = log.read_text()
    assert calls.index('Path("/app/output/.deploy-pause").touch()') < calls.index("up --build -d")
    assert calls.index("up --build -d") < calls.index('os.unlink(p)')


def test_old_backend_with_active_job_does_not_build(tmp_path):
    fake = tmp_path / "docker"
    log = tmp_path / "calls.log"
    fake.write_text("""#!/bin/sh
printf '%s\\n' "$*" >> "$DEPLOY_TEST_LOG"
case "$*" in
  *'/health/deployment'*) exit 1 ;;
  *'ps --status running --services'*) printf 'backend\\n' ;;
  *'SELECT COUNT(*)'*) printf '1\\n' ;;
esac
""")
    fake.chmod(0o755)
    env = dict(os.environ, PATH=f"{tmp_path}:{os.environ['PATH']}", DEPLOY_TEST_LOG=str(log))
    script = Path(__file__).resolve().parents[1] / "ops" / "deploy-private.sh"
    result = subprocess.run(["sh", str(script)], env=env, capture_output=True, text=True, timeout=10)
    assert result.returncode != 0
    assert "active job" in result.stderr
    assert "up --build -d" not in log.read_text()
