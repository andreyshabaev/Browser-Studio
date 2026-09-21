#!/usr/bin/env python3
from pathlib import Path
import base64,datetime as dt,hashlib,json,os,re,shutil,subprocess,sys,tempfile,time,urllib.request,zlib
C=Path('/usr/local/lib/tapein-control-v4/tapein_control_v4.py'); B=Path('/var/backups/tapein-control-v4/manual-breakglass')
S='tapein-control-v4.service'; T='tapein-control-v4.timer'
OSHA='42b73cb43d45bab7fa69070e0ad60f9351fd3d44d9314c5af359c1d805a3657f'; NSHA='9193b574cb0c1df4e5d161dbef05cdf828c72c300b7af4ba41336b923422b3ef'
OB='v5-534-browser-studio-checkpoint-scope-fix-v5533'; NB='v5-536-queuev2-bounded-tail-resync-v5535'; NSZ=1860616
BOOT='https://tapein.ru/agent-results/system-bootstrap.json'
P=zlib.decompress(base64.b64decode('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')).decode()
def shab(b):return hashlib.sha256(b).hexdigest()
def shaf(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for x in iter(lambda:f.read(1048576),b''):h.update(x)
 return h.hexdigest()
def run(a,to=60,ck=True):
 p=subprocess.run(a,text=True,capture_output=True,timeout=to)
 if ck and p.returncode:raise RuntimeError(f"cmd rc={p.returncode}: {' '.join(a)}\n{(p.stdout+p.stderr)[-1200:]}")
 return p
def build(t):
 m=re.search(r"^CONTROL_BUILD=['\"]([^'\"]+)['\"]$",t,re.M)
 if not m:raise RuntimeError('CONTROL_BUILD missing')
 return m.group(1)
def apply(old,patch):
 src=old.splitlines(keepends=True);out=[];pos=0;ls=patch.splitlines(keepends=True);i=0
 while i<len(ls) and not ls[i].startswith('@@ '):i+=1
 while i<len(ls):
  m=re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@',ls[i])
  if not m:raise RuntimeError('bad hunk')
  st=int(m.group(1))-1
  if st<pos:raise RuntimeError('overlap')
  out+=src[pos:st];pos=st;i+=1
  while i<len(ls) and not ls[i].startswith('@@ '):
   q=ls[i]
   if q.startswith('\\ No newline at end of file'):i+=1;continue
   tag=q[:1];x=q[1:]
   if tag==' ':
    if pos>=len(src) or src[pos]!=x:raise RuntimeError('context mismatch')
    out.append(src[pos]);pos+=1
   elif tag=='-':
    if pos>=len(src) or src[pos]!=x:raise RuntimeError('delete mismatch')
    pos+=1
   elif tag=='+':out.append(x)
   else:raise RuntimeError('bad patch tag')
   i+=1
 out+=src[pos:];return ''.join(out)
def fsyncd(p):
 fd=os.open(str(p),os.O_DIRECTORY)
 try:os.fsync(fd)
 finally:os.close(fd)
def post():
 if shaf(C)!=NSHA or build(C.read_text())!=NB:raise RuntimeError('installed identity mismatch')
 if run(['systemctl','is-active',T],15,False).stdout.strip()!='active':raise RuntimeError('timer inactive')
 r=run(['systemctl','show',S,'--property=Result','--value','--no-pager'],15,False)
 if r.returncode or r.stdout.strip() not in ('success',''):raise RuntimeError('service failed')
 last=''
 for _ in range(8):
  try:
   rq=urllib.request.Request(BOOT+f'?cb={time.time_ns()}',headers={'Cache-Control':'no-cache','Pragma':'no-cache','User-Agent':'TapeInRecovery/3'})
   with urllib.request.urlopen(rq,timeout=15) as z:d=json.loads(z.read(1048576).decode())
   if d.get('control_build')==NB and d.get('control_sha256')==NSHA:return
   last=f"stale {d.get('control_build')} {d.get('control_sha256')}"
  except Exception as e:last=f'{type(e).__name__}:{e}'
  time.sleep(2)
 raise RuntimeError('bootstrap verify: '+last)
def main():
 if os.geteuid()!=0 or not C.is_file() or C.is_symlink():raise RuntimeError('bad control/root')
 cs=shaf(C);ct=C.read_text();cb=build(ct);print('CURRENT_BUILD='+cb);print('CURRENT_SHA='+cs)
 if cs==NSHA and cb==NB:
  run(['systemctl','restart',T],30);run(['systemctl','start',S],180);post();print('RECOVERY_PASS_ALREADY_INSTALLED');return
 if cs!=OSHA or cb!=OB:raise RuntimeError('base guard failed; no mutation')
 nb=apply(ct,P).encode()
 if len(nb)!=NSZ or shab(nb)!=NSHA or build(nb.decode())!=NB:raise RuntimeError('patch identity mismatch')
 print('PATCH_VERIFIED_EXACT')
 with tempfile.TemporaryDirectory(prefix='tapein-v5536-') as td:
  cand=Path(td)/'c.py';cand.write_bytes(nb);run(['/usr/bin/python3','-m','py_compile',str(cand)],30);st=run(['/usr/bin/python3',str(cand),'selftest'],60)
  if '"ok":true' not in st.stdout.replace(' ','').lower():raise RuntimeError('selftest failed')
  print('SELFTEST_PASS');B.mkdir(parents=True,exist_ok=True);bk=B/f"tapein_control_v4.py.v5-534.{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.rollback";shutil.copy2(C,bk)
  if shaf(bk)!=OSHA:raise RuntimeError('backup mismatch')
  print('ROLLBACK='+str(bk));st0=C.stat();tmp=C.with_name('.tapein_control_v4.py.v5536.tmp');installed=False
  try:
   tmp.write_bytes(nb);os.chmod(tmp,st0.st_mode&0o7777);os.chown(tmp,st0.st_uid,st0.st_gid)
   with tmp.open('rb') as f:os.fsync(f.fileno())
   if shaf(tmp)!=NSHA:raise RuntimeError('temp mismatch')
   os.replace(tmp,C);fsyncd(C.parent);installed=True;run(['systemctl','restart',T],30);run(['systemctl','start',S],180);post();print('RECOVERY_PASS')
  except Exception:
   if installed:
    try:
     shutil.copyfile(bk,tmp);os.chmod(tmp,st0.st_mode&0o7777);os.chown(tmp,st0.st_uid,st0.st_gid)
     with tmp.open('rb') as f:os.fsync(f.fileno())
     os.replace(tmp,C);fsyncd(C.parent);run(['systemctl','restart',T],30,False);run(['systemctl','start',S],180,False);print('ROLLBACK_PASS',file=sys.stderr)
    except Exception as e:print('ROLLBACK_FAILED:'+str(e),file=sys.stderr)
   raise
  finally:
   try:
    if tmp.exists():tmp.unlink()
   except Exception:pass
if __name__=='__main__':
 try:main()
 except Exception as e:print(f'RECOVERY_FAIL:{type(e).__name__}:{e}',file=sys.stderr);sys.exit(1)
