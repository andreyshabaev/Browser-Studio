#!/usr/bin/env python3
from pathlib import Path
import datetime as dt, hashlib, json, os, re, shutil, subprocess, sys, tempfile, time, urllib.request

CONTROL_DEFAULT=Path('/usr/local/lib/tapein-control-v4/tapein_control_v4.py')
BACKUP_ROOT=Path('/var/backups/tapein-control-v4/manual-breakglass')
SERVICE='tapein-control-v4.service'
TIMER='tapein-control-v4.timer'
OLD_SHA='42b73cb43d45bab7fa69070e0ad60f9351fd3d44d9314c5af359c1d805a3657f'
NEW_SHA='9193b574cb0c1df4e5d161dbef05cdf828c72c300b7af4ba41336b923422b3ef'
OLD_BUILD='v5-534-browser-studio-checkpoint-scope-fix-v5533'
NEW_BUILD='v5-536-queuev2-bounded-tail-resync-v5535'
NEW_SIZE=1860616
PATCH_SIZE=11439
PATCH_SHA='cf3093b6e4a82ae357f2262ed397b6515b9b87b60ca631cbe1901d2a1074c9cd'
BOOTSTRAP_URL='https://tapein.ru/agent-results/system-bootstrap.json'
PATCH_TEXT="--- tapein_control_v4.py\n+++ tapein_control_v4.py\n@@ -207,7 +207,7 @@\n ALLOWED_ACTIONS |= {'inspect_music_notebook_print_vendor_permissions_v1','repair_music_notebook_print_vendor_permissions_v1'}\n ALLOWED_ACTIONS.add('inspect_music_notebook_retired_take_metadata_v1')\n ALLOWED_ACTIONS.add('install_control_persistent_loop_v1')\n-CONTROL_BUILD='v5-534-browser-studio-checkpoint-scope-fix-v5533'\n+CONTROL_BUILD='v5-536-queuev2-bounded-tail-resync-v5535'\n LEGAL_LAUNCH_081_PAGES={'en': [('acceptable-use', 'disclosure', None, '/legal/acceptable-use', 'edcda3a2d7501f18de52367537ec5965140187d98aacd3d84b7d4cee28aef4cd', False), ('cookies', 'disclosure', None, '/legal/cookies', '8267c199e35d328d6b68efadc6a741720f8dcc5e10ee0aff767bb885c5c4b2e6', False), ('copyright', 'disclosure', None, '/legal/copyright', '7cb0336f187e17c84c947b4568a98ad92185b24b9801e13ac936d41ff5d3c7bc', False), ('data-rights', 'disclosure', None, '/legal/data-rights', 'f3ac36b73de67a20c4027bf7e9da38bcc2a48ba027e29ffaf5a2aac9efe58fbc', False), ('imprint', 'disclosure', None, '/legal/imprint', '4a64aa3fabb8fb53444ae0003ebc5e41d4e8835d64b56ca19616d44c9567cc6d', False), ('index', 'disclosure', None, '/legal/', '1d2f5b47c03e48193bcfcebdf98e0e5d66a2c3166b4248091fad1d8e3482f9c4', False), ('marketing', 'disclosure', None, '/legal/marketing', '60d2f13d4e7501190531bea4c8cb3b27506b637b17888aed4f9807da04a7a526', False), ('privacy', 'disclosure', None, '/legal/privacy', 'c6b059dee2b30c1444cd7b9aea6a05d7c8b198e7e51f47aa263dc48fbd6281db', False), ('providers', 'disclosure', None, '/legal/providers', '47312c948e0864e23a930664d0d5eb03a6d3e49435bb2f06ca6d695c231ee153', False), ('security', 'disclosure', None, '/legal/security', 'ced0d33790a0c092204db81690852ad9d066c4320c24d2581bacb4d0e65d56b4', False), ('setlist', 'product_addendum', 'setlist', '/legal/setlist', '2c141b47de8ec846b769a04ab015ea84e30d6393af197a22d50090085e100d0b', True), ('terms', 'core_terms', None, '/legal/terms', '0d4ab39caa34e8b322a350b9959494d889ebd83fde0818a4146735eae644c8f8', True)], 'ru': [('acceptable-use', 'disclosure', None, '/ru/legal/acceptable-use', 'c6cad4fe675f6f991ee11be104bd66ea8dd9827ad014a920037227b0bb724320', False), ('cookies', 'disclosure', None, '/ru/legal/cookies', '87c99e5a52baf9ff933a1728f2400f4334bc2b3ecfd35f4ba73907b8477e4ce8', False), ('copyright', 'disclosure', None, '/ru/legal/copyright', '0244e6bcbc61cf6f815e0ec7a056b3013c4d0d94b60c70f88bcf048f955fc099', False), ('data-rights', 'disclosure', None, '/ru/legal/data-rights', 'cec55633da2312f3d01cdf21f1822a11f39f21ea841585c1ae907f047e2b6126', False), ('imprint', 'disclosure', None, '/ru/legal/imprint', '5bdd4f470295d62586ba9dc118bc437ad2154db9afca7147f04b563ff04b8311', False), ('index', 'disclosure', None, '/ru/legal/', '2259dd2c57ff19c102671f1ebfeb8018e254691e63bf705755a00009d2c5872c', False), ('marketing', 'disclosure', None, '/ru/legal/marketing', '63713d332f59ecf333cb4e87f44e227c982ef0d73512d1af9becff8258c99487', False), ('privacy', 'disclosure', None, '/ru/legal/privacy', '389fe2b05bc0d2a90c9659c48217daba3c42733bc4df3b9e5121de132cdb9ff4', False), ('providers', 'disclosure', None, '/ru/legal/providers', '55506e0f77b68ac0bcca21ee5c0b8aa7727c56028218d614fbcbc57e37323d0e', False), ('security', 'disclosure', None, '/ru/legal/security', '52e49529b2a431ef926d8e1d95051def33337625674aed31bd4fde1d81bcb678', False), ('setlist', 'product_addendum', 'setlist', '/ru/legal/setlist', '6f858ec00fe390e69c1e5fa5813444242b84a5b89f3540e4c888bbb55636a1ce', True), ('terms', 'core_terms', None, '/ru/legal/terms', '5252d8195ae7c5146e8e5624923305414ba331ac61826ca173f468f365739110', True)]}\n \n class ControlError(RuntimeError):\n@@ -22154,53 +22154,86 @@\n def _control_meta_set(c,key,value):\n \tc.execute('INSERT INTO control_meta(key,value,updated_at) VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at',(key,str(value),now()))\n \n-def _queue_v2_full_reconcile(c,cursor_before=0,boundary_before='',reason='seed'):\n-\traw=fetch_text(QUEUE_V2_CSV_URL+f'&cb={time.time_ns()}',max_bytes=8*1024*1024)\n-\tboundary_index=cursor_before-1 if cursor_before>0 else None\n-\ttotal,last,boundary_actual=_queue_v2_scan_meta(raw,boundary_index)\n-\tif cursor_before>0 and(total<cursor_before or boundary_actual!=boundary_before):\n-\t\traise ControlError('QUEUE_V2_APPEND_ONLY_VIOLATION',jdump({'cursor_before':cursor_before,'total_rows':total,'expected_boundary':boundary_before,'actual_boundary':boundary_actual}))\n-\ttasks=parse_queue_v2_csv(raw,skip_nonblank=cursor_before)\n-\treturn tasks,{'mode':'full_reconcile','reason':reason,'cursor_before':cursor_before,'cursor_after':total,'boundary_after':last,'new_raw_rows':max(0,total-cursor_before),'has_more':False}\n+def _queue_v2_query_csv(tq,timeout=20,max_bytes=1024*1024):\n+\turl=QUEUE_V2_GVIZ_CSV_URL+'&tq='+urllib.parse.quote(str(tq),safe='')+f'&cb={time.time_ns()}'\n+\treturn fetch_text(url,timeout=timeout,max_bytes=max_bytes)\n+\n+def _queue_v2_count_rows():\n+\traw=_queue_v2_query_csv('select count(A) where A is not null',timeout=20,max_bytes=65536)\n+\trows=list(csv.reader(io.StringIO(raw.lstrip('\\ufeff'))))\n+\tfor row in reversed(rows):\n+\t\tfor cell in reversed(row):\n+\t\t\tm=re.search(r'\\d+',str(cell or '').replace(',',''))\n+\t\t\tif m:\n+\t\t\t\treturn int(m.group(0))\n+\traise ControlError('QUEUE_V2_COUNT_INVALID')\n+\n+def _queue_v2_raw_task_ids(raw):\n+\ttry:r=csv.DictReader(io.StringIO(raw.lstrip('\\ufeff')))\n+\texcept Exception as e:raise ControlError('QUEUE_V2_CSV_INVALID',type(e).__name__)\n+\tif not r.fieldnames or 'task_id' not in {str(x or '').strip() for x in r.fieldnames}:\n+\t\traise ControlError('QUEUE_V2_HEADER_INVALID')\n+\treturn [str(row.get('task_id')or '').strip() for row in r if isinstance(row,dict) and any(str(v or '').strip() for v in row.values())]\n \n def fetch_queue_v2_incremental(c):\n \traw_state=_control_meta_get(c,QUEUE_V2_CURSOR_KEY)\n \tstate={}\n \tif raw_state:\n-\t\ttry:\n-\t\t\tstate=json.loads(raw_state)\n-\t\texcept Exception:\n-\t\t\tstate={}\n-\ttry:\n-\t\tcursor=int(state.get('cursor',0)or 0)if isinstance(state,dict)else 0\n-\texcept Exception:\n-\t\tcursor=0\n+\t\ttry:state=json.loads(raw_state)\n+\t\texcept Exception:state={}\n+\ttry:cursor=int(state.get('cursor',0)or 0)if isinstance(state,dict)else 0\n+\texcept Exception:cursor=0\n \tboundary=str(state.get('boundary_task_id')or '')if isinstance(state,dict)else ''\n-\tif cursor<0 or(cursor>0 and not boundary):\n-\t\tcursor=0\n-\t\tboundary=''\n-\tif cursor==0:\n-\t\treturn _queue_v2_full_reconcile(c,0,'','initial_seed')\n+\tif cursor<0 or(cursor>0 and not boundary):cursor=0;boundary=''\n \tdef hold(reason):\n \t\treturn [],{'mode':'incremental_hold','reason':str(reason)[:240],'cursor_before':cursor,'cursor_after':cursor,'boundary_after':boundary,'new_raw_rows':0,'has_more':False,'degraded':True}\n-\tstart=cursor-1\n-\tlimit=QUEUE_V2_INCREMENTAL_BATCH+1\n-\ttq=f'select * where A is not null limit {limit} offset {start}'\n-\turl=QUEUE_V2_GVIZ_CSV_URL+'&tq='+urllib.parse.quote(tq,safe='')+f'&cb={time.time_ns()}'\n-\ttry:\n-\t\traw=fetch_text(url,timeout=20,max_bytes=8*1024*1024)\n-\t\tseen,last,boundary_actual=_queue_v2_scan_meta(raw,0)\n-\t\tif seen<1 or boundary_actual!=boundary:\n-\t\t\treturn hold('incremental_boundary_mismatch')\n-\t\tnew_raw=max(0,seen-1)\n-\t\ttasks=parse_queue_v2_csv(raw,skip_nonblank=1)\n-\t\treturn tasks,{'mode':'incremental_gviz','reason':'cursor_match','cursor_before':cursor,'cursor_after':cursor+new_raw,'boundary_after':last if new_raw else boundary,'new_raw_rows':new_raw,'has_more':new_raw>=QUEUE_V2_INCREMENTAL_BATCH,'degraded':False}\n-\texcept ControlError as e:\n-\t\tif e.code=='QUEUE_V2_APPEND_ONLY_VIOLATION':\n-\t\t\traise\n-\t\treturn hold(f'incremental_error:{e.code}')\n-\texcept Exception as e:\n-\t\treturn hold(f'incremental_error:{type(e).__name__}')\n+\t# First seed is bounded: count remotely, then inspect only a small tail. Existing task DB dedupes overlap.\n+\tif cursor==0:\n+\t\ttry:\n+\t\t\ttotal=_queue_v2_count_rows()\n+\t\t\twindow=max(QUEUE_V2_INCREMENTAL_BATCH*2,100)\n+\t\t\tstart=max(0,total-window)\n+\t\t\traw=_queue_v2_query_csv(f'select * where A is not null limit {window} offset {start}')\n+\t\t\tids=_queue_v2_raw_task_ids(raw);seen=len(ids)\n+\t\t\tlast=ids[-1] if ids else ''\n+\t\t\ttasks=parse_queue_v2_csv(raw)\n+\t\t\treturn tasks,{'mode':'bounded_tail_seed','reason':'initial_seed','cursor_before':0,'cursor_after':start+seen,'boundary_after':last,'new_raw_rows':seen,'has_more':start+seen<total,'degraded':False,'remote_total':total}\n+\t\texcept Exception as e:\n+\t\t\treturn hold(f'bounded_seed_error:{e.code if isinstance(e,ControlError) else type(e).__name__}')\n+\tstart=cursor-1;limit=QUEUE_V2_INCREMENTAL_BATCH+1\n+\ttry:\n+\t\traw=_queue_v2_query_csv(f'select * where A is not null limit {limit} offset {start}')\n+\t\tids=_queue_v2_raw_task_ids(raw)\n+\t\tif ids and ids[0]==boundary:\n+\t\t\tnew_ids=ids[1:];tasks=parse_queue_v2_csv(raw,skip_nonblank=1)\n+\t\t\treturn tasks,{'mode':'incremental_gviz','reason':'cursor_match','cursor_before':cursor,'cursor_after':cursor+len(new_ids),'boundary_after':new_ids[-1] if new_ids else boundary,'new_raw_rows':len(new_ids),'has_more':len(new_ids)>=QUEUE_V2_INCREMENTAL_BATCH,'degraded':False}\n+\t\t# One bounded self-heal window around the durable cursor; never scan full history.\n+\t\trecovery_back=8;recovery_start=max(0,cursor-recovery_back)\n+\t\traw2=_queue_v2_query_csv(f'select * where A is not null limit {QUEUE_V2_INCREMENTAL_BATCH+recovery_back+1} offset {recovery_start}')\n+\t\tids2=_queue_v2_raw_task_ids(raw2)\n+\t\tif boundary in ids2:\n+\t\t\ti=ids2.index(boundary);new_ids=ids2[i+1:i+1+QUEUE_V2_INCREMENTAL_BATCH]\n+\t\t\t# Rebuild a tiny CSV containing header plus only rows after the recovered boundary.\n+\t\t\trows=list(csv.reader(io.StringIO(raw2.lstrip('\\ufeff'))));header=rows[0] if rows else []\n+\t\t\tbody=rows[1+i+1:1+i+1+len(new_ids)]\n+\t\t\tbuf=io.StringIO();w=csv.writer(buf,lineterminator='\\n');w.writerow(header);w.writerows(body)\n+\t\t\ttasks=parse_queue_v2_csv(buf.getvalue())\n+\t\t\treturn tasks,{'mode':'bounded_cursor_recovery','reason':'boundary_recovered','cursor_before':cursor,'cursor_after':cursor+len(new_ids),'boundary_after':new_ids[-1] if new_ids else boundary,'new_raw_rows':len(new_ids),'has_more':len(new_ids)>=QUEUE_V2_INCREMENTAL_BATCH,'degraded':False}\n+\t\t# Boundary disappeared (for example after a one-off sheet repair). Recover without a full-history scan:\n+\t\t# count remotely, inspect only a bounded tail, and rely on the local task DB for idempotent dedupe.\n+\t\ttry:\n+\t\t\ttotal=_queue_v2_count_rows()\n+\t\t\twindow=max(QUEUE_V2_INCREMENTAL_BATCH*2,100)\n+\t\t\ttail_start=max(0,total-window)\n+\t\t\traw3=_queue_v2_query_csv(f'select * where A is not null limit {window} offset {tail_start}')\n+\t\t\tids3=_queue_v2_raw_task_ids(raw3);seen3=len(ids3)\n+\t\t\tlast3=ids3[-1] if ids3 else ''\n+\t\t\ttasks3=parse_queue_v2_csv(raw3)\n+\t\t\treturn tasks3,{'mode':'bounded_tail_resync','reason':'boundary_missing_resynced','cursor_before':cursor,'cursor_after':tail_start+seen3,'boundary_after':last3,'new_raw_rows':seen3,'has_more':tail_start+seen3<total,'degraded':False,'remote_total':total}\n+\t\texcept Exception as e:\n+\t\t\treturn hold(f'incremental_boundary_mismatch:{e.code if isinstance(e,ControlError) else type(e).__name__}')\n+\texcept ControlError as e:return hold(f'incremental_error:{e.code}')\n+\texcept Exception as e:return hold(f'incremental_error:{type(e).__name__}')\n \n def store_queue_v2_cursor(c,state):\n \tpayload={'schema':'tapein.queuev2-cursor/1','cursor':int(state.get('cursor_after',0)or 0),'boundary_task_id':str(state.get('boundary_after')or ''),'updated_at':now()}\n"

def sha_bytes(data): return hashlib.sha256(data).hexdigest()
def sha_file(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()
def build_from_file(path):
    m=re.search(r"^CONTROL_BUILD=['\"]([^'\"]+)['\"]$",path.read_text(encoding='utf-8',errors='strict'),re.M)
    if not m: raise RuntimeError('CONTROL_BUILD not found')
    return m.group(1)
def run(args,timeout=60,check=True,stdin=None):
    p=subprocess.run(args,text=True,capture_output=True,timeout=timeout,stdin=stdin)
    if check and p.returncode!=0:
        raise RuntimeError('command failed rc=%d: %s\n%s'%(p.returncode,' '.join(args),(p.stdout+p.stderr)[-2000:]))
    return p
def verify_patch_bytes():
    b=PATCH_TEXT.encode('utf-8')
    if len(b)!=PATCH_SIZE: raise RuntimeError(f'embedded patch size mismatch: {len(b)} != {PATCH_SIZE}')
    got=sha_bytes(b)
    if got!=PATCH_SHA: raise RuntimeError(f'embedded patch sha mismatch: {got}')
def build_candidate(src,dst):
    patch_exe=shutil.which('patch')
    if not patch_exe: raise RuntimeError('patch utility missing')
    shutil.copy2(src,dst)
    with tempfile.NamedTemporaryFile('w+',encoding='utf-8',delete=False,prefix='tapein-v5536-',suffix='.patch') as pf:
        pf.write(PATCH_TEXT);pf.flush();patch_path=Path(pf.name)
    try:
        with patch_path.open('r',encoding='utf-8') as inp:
            p=run([patch_exe,'--batch','--fuzz=0',str(dst)],timeout=30,check=False,stdin=inp)
        if p.returncode!=0: raise RuntimeError('patch apply failed: '+(p.stdout+p.stderr)[-1800:])
    finally:
        try: patch_path.unlink()
        except OSError: pass
    if dst.stat().st_size!=NEW_SIZE: raise RuntimeError(f'candidate size mismatch: {dst.stat().st_size} != {NEW_SIZE}')
    got=sha_file(dst)
    if got!=NEW_SHA: raise RuntimeError(f'candidate sha mismatch: {got}')
    if build_from_file(dst)!=NEW_BUILD: raise RuntimeError('candidate build mismatch')
    run(['/usr/bin/python3','-m','py_compile',str(dst)],timeout=30)
    st=run(['/usr/bin/python3',str(dst),'selftest'],timeout=90)
    if '"ok":true' not in st.stdout.replace(' ','').lower(): raise RuntimeError('candidate selftest missing ok:true')
def fsync_dir(path):
    fd=os.open(str(path),os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)
def verify_runtime(control):
    if sha_file(control)!=NEW_SHA or build_from_file(control)!=NEW_BUILD: raise RuntimeError('installed identity mismatch')
    t=run(['systemctl','is-active',TIMER],timeout=15,check=False)
    if t.returncode!=0 or t.stdout.strip()!='active': raise RuntimeError('timer not active: '+t.stdout.strip()+' '+t.stderr.strip())
    r=run(['systemctl','show',SERVICE,'--property=Result','--value','--no-pager'],timeout=15,check=False)
    if r.returncode!=0 or r.stdout.strip() not in ('success',''): raise RuntimeError('service result not success: '+r.stdout.strip()+' '+r.stderr.strip())
    last='no bootstrap response'
    for _ in range(20):
        try:
            req=urllib.request.Request(BOOTSTRAP_URL+f'?cb={time.time_ns()}',headers={'Cache-Control':'no-cache','Pragma':'no-cache','User-Agent':'TapeInBreakglassRecovery/4.0'})
            with urllib.request.urlopen(req,timeout=15) as resp: payload=json.loads(resp.read(1024*1024).decode('utf-8'))
            if payload.get('control_build')==NEW_BUILD and payload.get('control_sha256')==NEW_SHA: return
            last=f"stale build={payload.get('control_build')} sha={payload.get('control_sha256')}"
        except Exception as e: last=f'{type(e).__name__}:{e}'
        time.sleep(2)
    raise RuntimeError('bootstrap verification failed: '+last)
def main():
    dry=os.environ.get('TAPEIN_RECOVERY_DRY_RUN')=='1'
    control=Path(os.environ.get('TAPEIN_CONTROL_PATH',str(CONTROL_DEFAULT)))
    if not dry and os.geteuid()!=0: raise RuntimeError('must run as root')
    if not control.is_file() or control.is_symlink(): raise RuntimeError(f'control path invalid: {control}')
    verify_patch_bytes()
    current_sha=sha_file(control); current_build=build_from_file(control)
    print(f'CURRENT_BUILD={current_build}');print(f'CURRENT_SHA={current_sha}')
    if current_sha==NEW_SHA and current_build==NEW_BUILD:
        if dry: print('DRY_RUN_PASS_ALREADY_NEW');return 0
        run(['systemctl','restart',TIMER],timeout=30);run(['systemctl','start',SERVICE],timeout=180);verify_runtime(control);print('RECOVERY_PASS_ALREADY_INSTALLED');return 0
    if current_sha!=OLD_SHA or current_build!=OLD_BUILD: raise RuntimeError(f'base guard failed; expected {OLD_BUILD}/{OLD_SHA}, got {current_build}/{current_sha}; no mutation performed')
    with tempfile.TemporaryDirectory(prefix='tapein-v5536-recovery-') as td:
        candidate=Path(td)/'candidate.py';build_candidate(control,candidate);print('CANDIDATE_VERIFIED')
        if dry: print('DRY_RUN_PASS');return 0
        BACKUP_ROOT.mkdir(parents=True,exist_ok=True)
        stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        backup=BACKUP_ROOT/f'tapein_control_v4.py.v5-534.{stamp}.rollback'
        shutil.copy2(control,backup)
        if sha_file(backup)!=OLD_SHA: raise RuntimeError('rollback backup sha mismatch; installation aborted')
        print(f'ROLLBACK={backup}')
        st=control.stat();tmp=control.with_name('.tapein_control_v4.py.recovery-v5536.tmp');installed=False
        try:
            shutil.copyfile(candidate,tmp);os.chmod(tmp,st.st_mode & 0o7777);os.chown(tmp,st.st_uid,st.st_gid)
            with tmp.open('rb') as f: os.fsync(f.fileno())
            if sha_file(tmp)!=NEW_SHA: raise RuntimeError('pre-replace temp sha mismatch')
            os.replace(tmp,control);fsync_dir(control.parent);installed=True
            if sha_file(control)!=NEW_SHA or build_from_file(control)!=NEW_BUILD: raise RuntimeError('atomic replace verification failed')
            run(['systemctl','restart',TIMER],timeout=30)
            run(['systemctl','start',SERVICE],timeout=180)
            verify_runtime(control)
            print('RECOVERY_PASS');return 0
        except Exception:
            if installed:
                try:
                    shutil.copyfile(backup,tmp);os.chmod(tmp,st.st_mode & 0o7777);os.chown(tmp,st.st_uid,st.st_gid)
                    with tmp.open('rb') as f: os.fsync(f.fileno())
                    os.replace(tmp,control);fsync_dir(control.parent)
                    run(['systemctl','restart',TIMER],timeout=30,check=False);run(['systemctl','start',SERVICE],timeout=180,check=False)
                    print('ROLLBACK_PASS',file=sys.stderr)
                except Exception as rb: print(f'ROLLBACK_FAILED: {type(rb).__name__}: {rb}',file=sys.stderr)
            raise
        finally:
            try:
                if tmp.exists(): tmp.unlink()
            except OSError: pass
if __name__=='__main__':
    try: raise SystemExit(main())
    except Exception as e:
        print(f'RECOVERY_FAIL: {type(e).__name__}: {e}',file=sys.stderr);raise SystemExit(1)
