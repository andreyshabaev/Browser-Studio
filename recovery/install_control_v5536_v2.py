#!/usr/bin/env python3
from pathlib import Path
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

CONTROL = Path('/usr/local/lib/tapein-control-v4/tapein_control_v4.py')
BACKUP_ROOT = Path('/var/backups/tapein-control-v4/manual-breakglass')
SERVICE = 'tapein-control-v4.service'
TIMER = 'tapein-control-v4.timer'
OLD_SHA = '42b73cb43d45bab7fa69070e0ad60f9351fd3d44d9314c5af359c1d805a3657f'
NEW_SHA = '9193b574cb0c1df4e5d161dbef05cdf828c72c300b7af4ba41336b923422b3ef'
OLD_BUILD = 'v5-534-browser-studio-checkpoint-scope-fix-v5533'
NEW_BUILD = 'v5-536-queuev2-bounded-tail-resync-v5535'
NEW_SIZE = 1860616
CANDIDATE_URL = 'https://drive.usercontent.google.com/download?id=1M3vWTGK41puVmxuEjueFDwFPPRBWX9nY&export=download&confirm=t'
BOOTSTRAP_URL = 'https://tapein.ru/agent-results/system-bootstrap.json'


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def run(args, timeout=60, check=True):
    p = subprocess.run(args, text=True, capture_output=True, timeout=timeout)
    if check and p.returncode != 0:
        raise RuntimeError(f"command failed rc={p.returncode}: {' '.join(args)}\n{(p.stdout + p.stderr)[-1600:]}")
    return p


def build_from_file(path: Path) -> str:
    text = path.read_text(encoding='utf-8', errors='strict')
    m = re.search(r"^CONTROL_BUILD=['\"]([^'\"]+)['\"]$", text, re.M)
    if not m:
        raise RuntimeError('CONTROL_BUILD not found')
    return m.group(1)


def download_candidate(dst: Path):
    req = urllib.request.Request(CANDIDATE_URL, headers={
        'User-Agent': 'TapeInBreakglassRecovery/2.0',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache',
    })
    with urllib.request.urlopen(req, timeout=90) as r, dst.open('wb') as f:
        if getattr(r, 'status', 200) < 200 or getattr(r, 'status', 200) >= 300:
            raise RuntimeError(f'candidate HTTP status {getattr(r, "status", "?")}')
        shutil.copyfileobj(r, f, 1024 * 1024)


def verify_candidate(path: Path):
    if path.stat().st_size != NEW_SIZE:
        raise RuntimeError(f'candidate size mismatch: {path.stat().st_size} != {NEW_SIZE}')
    got = sha256(path)
    if got != NEW_SHA:
        raise RuntimeError(f'candidate sha mismatch: {got}')
    build = build_from_file(path)
    if build != NEW_BUILD:
        raise RuntimeError(f'candidate build mismatch: {build}')
    run(['/usr/bin/python3', '-m', 'py_compile', str(path)], timeout=30)
    st = run(['/usr/bin/python3', str(path), 'selftest'], timeout=45)
    if '"ok":true' not in st.stdout.replace(' ', '').lower():
        raise RuntimeError('candidate selftest missing ok:true')


def fsync_dir(path: Path):
    fd = os.open(str(path), os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def verify_runtime_postinstall():
    if sha256(CONTROL) != NEW_SHA:
        raise RuntimeError('installed sha changed after service start')
    if build_from_file(CONTROL) != NEW_BUILD:
        raise RuntimeError('installed build changed after service start')
    timer = run(['systemctl', 'is-active', TIMER], timeout=15, check=False)
    if timer.returncode != 0 or timer.stdout.strip() != 'active':
        raise RuntimeError(f'timer not active: rc={timer.returncode} out={timer.stdout.strip()} err={timer.stderr.strip()}')
    result = run(['systemctl', 'show', SERVICE, '--property=Result', '--value', '--no-pager'], timeout=15, check=False)
    if result.returncode != 0 or result.stdout.strip() not in ('success', ''):
        raise RuntimeError(f'service result not success: {result.stdout.strip()} {result.stderr.strip()}')
    last_err = None
    for _ in range(6):
        try:
            req = urllib.request.Request(BOOTSTRAP_URL + f'?cb={time.time_ns()}', headers={'Cache-Control':'no-cache','Pragma':'no-cache','User-Agent':'TapeInBreakglassRecovery/2.0'})
            with urllib.request.urlopen(req, timeout=15) as r:
                payload = json.loads(r.read(1024 * 1024).decode('utf-8'))
            if payload.get('control_build') == NEW_BUILD and payload.get('control_sha256') == NEW_SHA:
                return
            last_err = f"bootstrap stale build={payload.get('control_build')} sha={payload.get('control_sha256')}"
        except Exception as e:
            last_err = f'{type(e).__name__}:{e}'
        time.sleep(2)
    raise RuntimeError('bootstrap verification failed: ' + str(last_err))


def main():
    if os.geteuid() != 0:
        raise RuntimeError('must run as root')
    if not CONTROL.is_file() or CONTROL.is_symlink():
        raise RuntimeError(f'control path invalid: {CONTROL}')

    current_sha = sha256(CONTROL)
    current_build = build_from_file(CONTROL)
    print(f'CURRENT_BUILD={current_build}')
    print(f'CURRENT_SHA={current_sha}')

    if current_sha == NEW_SHA and current_build == NEW_BUILD:
        run(['systemctl', 'restart', TIMER], timeout=30)
        run(['systemctl', 'start', SERVICE], timeout=120)
        verify_runtime_postinstall()
        print('RECOVERY_PASS_ALREADY_INSTALLED')
        return 0

    if current_sha != OLD_SHA or current_build != OLD_BUILD:
        raise RuntimeError(f'base guard failed; expected {OLD_BUILD}/{OLD_SHA}, got {current_build}/{current_sha}; no mutation performed')

    with tempfile.TemporaryDirectory(prefix='tapein-recovery-v5536-') as td:
        candidate = Path(td) / 'candidate.py'
        download_candidate(candidate)
        verify_candidate(candidate)
        print('CANDIDATE_VERIFIED')

        BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
        stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        backup = BACKUP_ROOT / f'tapein_control_v4.py.v5-534.{stamp}.rollback'
        shutil.copy2(CONTROL, backup)
        if sha256(backup) != OLD_SHA:
            raise RuntimeError('rollback backup sha mismatch; installation aborted')
        print(f'ROLLBACK={backup}')

        st = CONTROL.stat()
        tmp = CONTROL.with_name('.tapein_control_v4.py.recovery-v5536.tmp')
        installed = False
        try:
            shutil.copyfile(candidate, tmp)
            os.chmod(tmp, st.st_mode & 0o7777)
            os.chown(tmp, st.st_uid, st.st_gid)
            with tmp.open('rb') as f:
                os.fsync(f.fileno())
            if sha256(tmp) != NEW_SHA:
                raise RuntimeError('pre-replace temp sha mismatch')
            os.replace(tmp, CONTROL)
            fsync_dir(CONTROL.parent)
            installed = True

            if sha256(CONTROL) != NEW_SHA or build_from_file(CONTROL) != NEW_BUILD:
                raise RuntimeError('atomic replace verification failed')

            run(['systemctl', 'restart', TIMER], timeout=30)
            run(['systemctl', 'start', SERVICE], timeout=120)
            verify_runtime_postinstall()
            print('RECOVERY_PASS')
            return 0
        except Exception:
            if installed:
                try:
                    shutil.copyfile(backup, tmp)
                    os.chmod(tmp, st.st_mode & 0o7777)
                    os.chown(tmp, st.st_uid, st.st_gid)
                    with tmp.open('rb') as f:
                        os.fsync(f.fileno())
                    os.replace(tmp, CONTROL)
                    fsync_dir(CONTROL.parent)
                    run(['systemctl', 'restart', TIMER], timeout=30, check=False)
                    run(['systemctl', 'start', SERVICE], timeout=120, check=False)
                    print('ROLLBACK_PASS', file=sys.stderr)
                except Exception as rb:
                    print(f'ROLLBACK_FAILED: {type(rb).__name__}: {rb}', file=sys.stderr)
            raise
        finally:
            try:
                if tmp.exists():
                    tmp.unlink()
            except Exception:
                pass


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f'RECOVERY_FAIL: {type(e).__name__}: {e}', file=sys.stderr)
        raise SystemExit(1)
