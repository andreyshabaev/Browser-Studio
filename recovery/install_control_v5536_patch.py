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

CONTROL_DEFAULT = Path('/usr/local/lib/tapein-control-v4/tapein_control_v4.py')
BACKUP_ROOT = Path('/var/backups/tapein-control-v4/manual-breakglass')
SERVICE = 'tapein-control-v4.service'
TIMER = 'tapein-control-v4.timer'
OLD_SHA = '42b73cb43d45bab7fa69070e0ad60f9351fd3d44d9314c5af359c1d805a3657f'
NEW_SHA = '9193b574cb0c1df4e5d161dbef05cdf828c72c300b7af4ba41336b923422b3ef'
OLD_BUILD = 'v5-534-browser-studio-checkpoint-scope-fix-v5533'
NEW_BUILD = 'v5-536-queuev2-bounded-tail-resync-v5535'
NEW_SIZE = 1860616
BOOTSTRAP_URL = 'https://tapein.ru/agent-results/system-bootstrap.json'
PATCHES = [(209, 210, "CONTROL_BUILD='v5-534-browser-studio-checkpoint-scope-fix-v5533'\n", "CONTROL_BUILD='v5-536-queuev2-bounded-tail-resync-v5535'\n"), (22156, 22164, "def _queue_v2_full_reconcile(c,cursor_before=0,boundary_before='',reason='seed'):\n\traw=fetch_text(QUEUE_V2_CSV_URL+f'&cb={time.time_ns()}',max_bytes=8*1024*1024)\n\tboundary_index=cursor_before-1 if cursor_before>0 else None\n\ttotal,last,boundary_actual=_queue_v2_scan_meta(raw,boundary_index)\n\tif cursor_before>0 and boundary_actual!=boundary_before:\n\t\traise ControlError('QUEUE_V2_APPEND_ONLY_VIOLATION',f'cursor={cursor_before}|expected={boundary_before}|actual={boundary_actual}')\n\ttasks=parse_queue_v2_csv(raw)\n\treturn tasks,{'mode':'full_reconcile','reason':reason,'cursor_before':cursor_before,'cursor_after':total,'boundary_before':boundary_before,'boundary_after':last,'rows_fetched':total,'new_rows':max(0,total-cursor_before),'reconcile':True,'degraded':False}\n", "def _queue_v2_query_csv(tq,timeout=20,max_bytes=1024*1024):\n\turl=QUEUE_V2_GVIZ_CSV_URL+'&tq='+urllib.parse.quote(str(tq),safe='')+f'&cb={time.time_ns()}'\n\treturn fetch_text(url,timeout=timeout,max_bytes=max_bytes)\n\ndef _queue_v2_count_rows():\n\traw=_queue_v2_query_csv('select count(A) where A is not null',max_bytes=128*1024)\n\trows=list(csv.reader(io.StringIO(raw)))\n\tfor row in rows[1:]:\n\t\tfor cell in row:\n\t\t\ts=str(cell or '').strip().replace(',','')\n\t\t\tif s.isdigit():return int(s)\n\traise ControlError('QUEUE_V2_COUNT_UNAVAILABLE')\n\ndef _queue_v2_raw_task_ids(raw):\n\trows=list(csv.reader(io.StringIO(raw)))\n\tif len(rows)<=1:return[]\n\treturn[str(r[0]).strip() for r in rows[1:] if r and str(r[0]).strip()]\n"), (22169, 22177, "\t\ttry:\n\t\t\tstate=json.loads(raw_state)\n\t\texcept Exception:\n\t\t\tstate={}\n\ttry:\n\t\tcursor=int(state.get('cursor',0)or 0)if isinstance(state,dict)else 0\n\texcept Exception:\n\t\tcursor=0\n", "\t\ttry:state=json.loads(raw_state)\n\t\texcept Exception:state={}\n\ttry:cursor=int(state.get('cursor',0)or 0)if isinstance(state,dict)else 0\n\texcept Exception:cursor=0\n"), (22178, 22183, "\tif cursor<0 or(cursor>0 and not boundary):\n\t\tcursor=0\n\t\tboundary=''\n\tif cursor==0:\n\t\treturn _queue_v2_full_reconcile(c,0,'','initial_seed')\n", "\tif cursor<0 or(cursor>0 and not boundary):cursor=0;boundary=''\n"), (22185, 22189, "\tstart=cursor-1\n\tlimit=QUEUE_V2_INCREMENTAL_BATCH+1\n\ttq=f'select * where A is not null limit {limit} offset {start}'\n\turl=QUEUE_V2_GVIZ_CSV_URL+'&tq='+urllib.parse.quote(tq,safe='')+f'&cb={time.time_ns()}'\n", "\t# First seed is bounded: count remotely, then inspect only a small tail. Existing task DB dedupes overlap.\n\tif cursor==0:\n\t\ttry:\n\t\t\ttotal=_queue_v2_count_rows()\n\t\t\twindow=max(QUEUE_V2_INCREMENTAL_BATCH*2,100)\n\t\t\tstart=max(0,total-window)\n\t\t\traw=_queue_v2_query_csv(f'select * where A is not null limit {window} offset {start}')\n\t\t\tids=_queue_v2_raw_task_ids(raw);tasks=parse_queue_v2_csv(raw)\n\t\t\tlast=ids[-1] if ids else''\n\t\t\treturn tasks,{'mode':'bounded_tail_seed','reason':'initial_seed','cursor_before':0,'cursor_after':total,'boundary_before':'','boundary_after':last,'rows_fetched':len(ids),'new_rows':len(ids),'reconcile':True,'degraded':False}\n\t\texcept Exception as e:\n\t\t\traise ControlError('QUEUE_V2_BOUNDED_SEED_FAILED',f'{type(e).__name__}:{str(e)[:300]}')\n\tstart=cursor-1;limit=QUEUE_V2_INCREMENTAL_BATCH+1\n"), (22190, 22203, "\t\traw=fetch_text(url,timeout=20,max_bytes=8*1024*1024)\n\t\tseen,last,boundary_actual=_queue_v2_scan_meta(raw,0)\n\t\tif seen<1 or boundary_actual!=boundary:\n\t\t\treturn hold('incremental_boundary_mismatch')\n\t\tnew_raw=max(0,seen-1)\n\t\ttasks=parse_queue_v2_csv(raw,skip_nonblank=1)\n\t\treturn tasks,{'mode':'incremental_gviz','reason':'cursor_match','cursor_before':cursor,'cursor_after':cursor+new_raw,'boundary_before':boundary,'boundary_after':last or boundary,'rows_fetched':seen,'new_rows':new_raw,'reconcile':False,'degraded':False}\n\texcept Exception as e:\n\t\treturn hold(f'incremental_exception:{type(e).__name__}')\n", "\t\traw=_queue_v2_query_csv(f'select * where A is not null limit {limit} offset {start}')\n\t\tids=_queue_v2_raw_task_ids(raw)\n\t\tif ids and ids[0]==boundary:\n\t\t\tnew_ids=ids[1:];tasks=parse_queue_v2_csv(raw,skip_nonblank=1)\n\t\t\treturn tasks,{'mode':'incremental_gviz','reason':'cursor_match','cursor_before':cursor,'cursor_after':cursor+len(new_ids),'boundary_before':boundary,'boundary_after':(new_ids[-1] if new_ids else boundary),'rows_fetched':len(ids),'new_rows':len(new_ids),'reconcile':False,'degraded':False}\n\t\t# Cursor boundary disappeared. One bounded resync only; never scan full history.\n\t\ttotal=_queue_v2_count_rows();window=max(QUEUE_V2_INCREMENTAL_BATCH*2,100);tail_start=max(0,total-window)\n\t\ttail_raw=_queue_v2_query_csv(f'select * where A is not null limit {window} offset {tail_start}')\n\t\ttail_ids=_queue_v2_raw_task_ids(tail_raw)\n\t\tif not tail_ids:return hold('bounded_tail_empty')\n\t\tif boundary in tail_ids:\n\t\t\tidx=tail_ids.index(boundary);tasks=parse_queue_v2_csv(tail_raw,skip_nonblank=idx+1);new_ids=tail_ids[idx+1:]\n\t\t\treturn tasks,{'mode':'bounded_tail_resync','reason':'boundary_recovered','cursor_before':cursor,'cursor_after':cursor+len(new_ids),'boundary_before':boundary,'boundary_after':(new_ids[-1] if new_ids else boundary),'rows_fetched':len(tail_ids),'new_rows':len(new_ids),'reconcile':True,'degraded':False}\n\t\t# Boundary fell outside bounded tail: safely move to remote tail and rely on local task-id dedupe.\n\t\ttasks=parse_queue_v2_csv(tail_raw)\n\t\treturn tasks,{'mode':'bounded_tail_resync','reason':'boundary_missing_tail_reseed','cursor_before':cursor,'cursor_after':total,'boundary_before':boundary,'boundary_after':tail_ids[-1],'rows_fetched':len(tail_ids),'new_rows':len(tail_ids),'reconcile':True,'degraded':False}\n\texcept ControlError:\n\t\traise\n\texcept Exception as e:\n\t\treturn hold(f'incremental_exception:{type(e).__name__}')\n")]

def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):
            h.update(chunk)
    return h.hexdigest()

def run(args, timeout=60, check=True):
    p=subprocess.run(args,text=True,capture_output=True,timeout=timeout)
    if check and p.returncode!=0:
        raise RuntimeError(f"command failed rc={p.returncode}: {' '.join(args)}\n{(p.stdout+p.stderr)[-1600:]}")
    return p

def build_from_file(path: Path)->str:
    text=path.read_text(encoding='utf-8',errors='strict')
    m=re.search(r"^CONTROL_BUILD=['\"]([^'\"]+)['\"]$",text,re.M)
    if not m:
        raise RuntimeError('CONTROL_BUILD not found')
    return m.group(1)

def build_candidate(base: Path, dst: Path):
    if sha256(base)!=OLD_SHA:
        raise RuntimeError('base sha mismatch before patch')
    text=base.read_text(encoding='utf-8',errors='strict')
    lines=text.splitlines(keepends=True)
    for i1,i2,old,new in reversed(PATCHES):
        actual=''.join(lines[i1:i2])
        if actual!=old:
            raise RuntimeError(f'patch context mismatch at lines {i1+1}-{i2}')
        lines[i1:i2]=new.splitlines(keepends=True)
    dst.write_text(''.join(lines),encoding='utf-8',newline='')
    if dst.stat().st_size!=NEW_SIZE:
        raise RuntimeError(f'patched size mismatch: {dst.stat().st_size} != {NEW_SIZE}')
    got=sha256(dst)
    if got!=NEW_SHA:
        raise RuntimeError(f'patched sha mismatch: {got}')
    if build_from_file(dst)!=NEW_BUILD:
        raise RuntimeError('patched build mismatch')
    run(['/usr/bin/python3','-m','py_compile',str(dst)],timeout=30)
    st=run(['/usr/bin/python3',str(dst),'selftest'],timeout=45)
    if '"ok":true' not in st.stdout.replace(' ','').lower():
        raise RuntimeError('patched candidate selftest missing ok:true')

def fsync_dir(path: Path):
    fd=os.open(str(path),os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)

def verify_runtime_postinstall(control: Path):
    if sha256(control)!=NEW_SHA:
        raise RuntimeError('installed sha changed after service start')
    if build_from_file(control)!=NEW_BUILD:
        raise RuntimeError('installed build changed after service start')
    timer=run(['systemctl','is-active',TIMER],timeout=15,check=False)
    if timer.returncode!=0 or timer.stdout.strip()!='active':
        raise RuntimeError(f'timer not active: rc={timer.returncode} out={timer.stdout.strip()} err={timer.stderr.strip()}')
    result=run(['systemctl','show',SERVICE,'--property=Result','--value','--no-pager'],timeout=15,check=False)
    if result.returncode!=0 or result.stdout.strip() not in ('success',''):
        raise RuntimeError(f'service result not success: {result.stdout.strip()} {result.stderr.strip()}')
    last_err=None
    for _ in range(8):
        try:
            req=urllib.request.Request(BOOTSTRAP_URL+f'?cb={time.time_ns()}',headers={'Cache-Control':'no-cache','Pragma':'no-cache','User-Agent':'TapeInPatchRecovery/1.0'})
            with urllib.request.urlopen(req,timeout=15) as r:
                payload=json.loads(r.read(1024*1024).decode('utf-8'))
            if payload.get('control_build')==NEW_BUILD and payload.get('control_sha256')==NEW_SHA:
                return
            last_err=f"bootstrap stale build={payload.get('control_build')} sha={payload.get('control_sha256')}"
        except Exception as e:
            last_err=f'{type(e).__name__}:{e}'
        time.sleep(2)
    raise RuntimeError('bootstrap verification failed: '+str(last_err))

def main():
    dry=os.environ.get('TAPEIN_RECOVERY_DRYRUN')=='1'
    control=Path(os.environ.get('TAPEIN_RECOVERY_CONTROL',str(CONTROL_DEFAULT)))
    if not dry and os.geteuid()!=0:
        raise RuntimeError('must run as root')
    if not control.is_file() or control.is_symlink():
        raise RuntimeError(f'control path invalid: {control}')

    current_sha=sha256(control)
    current_build=build_from_file(control)
    print(f'CURRENT_BUILD={current_build}')
    print(f'CURRENT_SHA={current_sha}')

    if current_sha==NEW_SHA and current_build==NEW_BUILD:
        if dry:
            print('PATCH_VERIFY_ALREADY_NEW')
            return 0
        run(['systemctl','restart',TIMER],timeout=30)
        run(['systemctl','start',SERVICE],timeout=120)
        verify_runtime_postinstall(control)
        print('RECOVERY_PASS_ALREADY_INSTALLED')
        return 0

    if current_sha!=OLD_SHA or current_build!=OLD_BUILD:
        raise RuntimeError(f'base guard failed; expected {OLD_BUILD}/{OLD_SHA}, got {current_build}/{current_sha}; no mutation performed')

    with tempfile.TemporaryDirectory(prefix='tapein-patch-recovery-v5536-') as td:
        candidate=Path(td)/'candidate.py'
        build_candidate(control,candidate)
        print('PATCH_CANDIDATE_VERIFIED')
        if dry:
            print('PATCH_VERIFY_PASS')
            return 0

        BACKUP_ROOT.mkdir(parents=True,exist_ok=True)
        stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        backup=BACKUP_ROOT/f'tapein_control_v4.py.v5-534.{stamp}.rollback'
        shutil.copy2(control,backup)
        if sha256(backup)!=OLD_SHA:
            raise RuntimeError('rollback backup sha mismatch; installation aborted')
        print(f'ROLLBACK={backup}')

        st=control.stat()
        tmp=control.with_name('.tapein_control_v4.py.recovery-v5536.tmp')
        installed=False
        try:
            shutil.copyfile(candidate,tmp)
            os.chmod(tmp,st.st_mode & 0o7777)
            os.chown(tmp,st.st_uid,st.st_gid)
            with tmp.open('rb') as f: os.fsync(f.fileno())
            if sha256(tmp)!=NEW_SHA:
                raise RuntimeError('pre-replace temp sha mismatch')
            os.replace(tmp,control)
            fsync_dir(control.parent)
            installed=True
            if sha256(control)!=NEW_SHA or build_from_file(control)!=NEW_BUILD:
                raise RuntimeError('atomic replace verification failed')
            run(['systemctl','restart',TIMER],timeout=30)
            run(['systemctl','start',SERVICE],timeout=120)
            verify_runtime_postinstall(control)
            print('RECOVERY_PASS')
            return 0
        except Exception:
            if installed:
                try:
                    shutil.copyfile(backup,tmp)
                    os.chmod(tmp,st.st_mode & 0o7777)
                    os.chown(tmp,st.st_uid,st.st_gid)
                    with tmp.open('rb') as f: os.fsync(f.fileno())
                    os.replace(tmp,control)
                    fsync_dir(control.parent)
                    run(['systemctl','restart',TIMER],timeout=30,check=False)
                    run(['systemctl','start',SERVICE],timeout=120,check=False)
                    print('ROLLBACK_PASS',file=sys.stderr)
                except Exception as rb:
                    print(f'ROLLBACK_FAILED: {type(rb).__name__}: {rb}',file=sys.stderr)
            raise
        finally:
            try:
                if tmp.exists(): tmp.unlink()
            except Exception:
                pass

if __name__=='__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        print(f'RECOVERY_FAIL: {type(e).__name__}: {e}',file=sys.stderr)
        raise SystemExit(1)
