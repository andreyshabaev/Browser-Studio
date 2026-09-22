#!/usr/bin/env bash
set -euo pipefail

if [ "${EUID}" -ne 0 ]; then
  echo "Tape In Rescue installer must run as root" >&2
  exit 1
fi

install -d -m 0755 /usr/local/lib/tapein-rescue /etc/tapein-rescue /var/www/__tapein-rescue
install -d -m 0700 /var/lib/tapein-rescue /var/backups/tapein-rescue

cat > /usr/local/lib/tapein-rescue/agent.py <<'PY_AGENT'
#!/usr/bin/env python3
import base64, datetime as dt, hashlib, json, os, pathlib, shutil, subprocess, tempfile, time, urllib.request

SCHEMA='tapein.rescue.command/1'
COMMAND_URL='https://raw.githubusercontent.com/andreyshabaev/Browser-Studio/tapein-rescue-control/rescue/command.json'
SIG_URL='https://raw.githubusercontent.com/andreyshabaev/Browser-Studio/tapein-rescue-control/rescue/command.sig'
PUBKEY=pathlib.Path('/etc/tapein-rescue/public.pem')
STATE_DIR=pathlib.Path('/var/lib/tapein-rescue')
STATE_FILE=STATE_DIR/'state.json'
RESULT_DIR=pathlib.Path('/var/www/__tapein-rescue')
RESULT_FILE=RESULT_DIR/'status.json'
NGINX_CONF=pathlib.Path('/etc/nginx/conf.d/00-tapein-authoritative.conf')
CONTROL_PATH=pathlib.Path('/usr/local/lib/tapein-control-v4/tapein_control_v4.py')
BACKUP_ROOT=pathlib.Path('/var/backups/tapein-rescue')
CONTROL_SERVICE='tapein-control-v4.service'
CONTROL_TIMER='tapein-control-v4.timer'
RESCUE_SERVICE='tapein-rescue.service'
RESCUE_TIMER='tapein-rescue.timer'
RESCUE_MARKER_BEGIN='# TAPEIN_RESCUE_STATUS_ROUTE_V3_BEGIN'
RESCUE_MARKER_END='# TAPEIN_RESCUE_STATUS_ROUTE_V3_END'
GENERIC_ANCHOR='    location / {\n        auth_request /_studio_release;'
RESCUE_BLOCK=(
    '    '+RESCUE_MARKER_BEGIN+'\n'
    '    # Independent break-glass readback; never route through Browser Studio release selection.\n'
    '    location ^~ /__tapein-rescue/ {\n'
    '        root /var/www;\n'
    '        default_type application/json;\n'
    '        add_header Cache-Control "no-store, max-age=0" always;\n'
    '        add_header Pragma "no-cache" always;\n'
    '        try_files $uri =404;\n'
    '    }\n'
    '    '+RESCUE_MARKER_END+'\n\n'
)
AGENT_RESULTS_MARKER_BEGIN='# TAPEIN_AGENT_RESULTS_STATIC_ROUTE_V1_BEGIN'
AGENT_RESULTS_MARKER_END='# TAPEIN_AGENT_RESULTS_STATIC_ROUTE_V1_END'
AGENT_RESULTS_BLOCK=(
    '    '+AGENT_RESULTS_MARKER_BEGIN+'\n'
    '    # Machine-readable Control results must never depend on Browser Studio release selection.\n'
    '    location ^~ /agent-results/ {\n'
    '        root /var/www/browser-studio-cloud/studio;\n'
    '        default_type application/json;\n'
    '        add_header Cache-Control "no-store, max-age=0" always;\n'
    '        add_header Pragma "no-cache" always;\n'
    '        try_files $uri =404;\n'
    '    }\n'
    '    '+AGENT_RESULTS_MARKER_END+'\n\n'
)

def run(cmd,timeout=20,check=True):
    p=subprocess.run(cmd,text=True,capture_output=True,timeout=timeout)
    if check and p.returncode!=0:
        raise RuntimeError(f"command failed ({p.returncode}): {' '.join(cmd)} :: {(p.stderr or p.stdout)[-2000:]}")
    return p

def sha(path):
    try:return hashlib.sha256(path.read_bytes()).hexdigest()
    except Exception:return None

def service_state(name):
    p=run(['systemctl','is-active',name],timeout=8,check=False)
    return p.stdout.strip() or p.stderr.strip() or f'rc={p.returncode}'

def service_enabled(name):
    p=run(['systemctl','is-enabled',name],timeout=8,check=False)
    return p.stdout.strip() or p.stderr.strip() or f'rc={p.returncode}'

def snapshot(extra=None):
    out={
        'control_service':service_state(CONTROL_SERVICE),
        'control_timer':service_state(CONTROL_TIMER),
        'control_timer_enabled':service_enabled(CONTROL_TIMER),
        'rescue_service':service_state(RESCUE_SERVICE),
        'rescue_timer':service_state(RESCUE_TIMER),
        'rescue_timer_enabled':service_enabled(RESCUE_TIMER),
        'nginx_service':service_state('nginx.service'),
        'control_sha256':sha(CONTROL_PATH),
        'nginx_sha256':sha(NGINX_CONF),
        'nginx_test':None,
        'agent_results_route_present':False,
        'rescue_route_present':False,
    }
    p=run(['nginx','-t'],timeout=10,check=False)
    out['nginx_test']={'ok':p.returncode==0,'stderr':p.stderr[-1200:]}
    try:
        txt=NGINX_CONF.read_text(encoding='utf-8')
        out['agent_results_route_present']='location ^~ /agent-results/' in txt
        out['rescue_route_present']='location ^~ /__tapein-rescue/' in txt
    except Exception:pass
    if extra:out.update(extra)
    return out

def atomic_json(path,obj,mode):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmpname=tempfile.mkstemp(prefix='.'+path.name+'.',suffix='.tmp',dir=str(path.parent))
    os.close(fd);tmp=pathlib.Path(tmpname)
    try:
        tmp.write_text(json.dumps(obj,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
        os.chmod(tmp,mode)
        os.replace(tmp,path)
        os.chmod(path,mode)
    finally:
        try:tmp.unlink(missing_ok=True)
        except Exception:pass

def backup_file(path,tag):
    BACKUP_ROOT.mkdir(parents=True,exist_ok=True)
    stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    d=BACKUP_ROOT/f'{stamp}-{tag}'
    d.mkdir(mode=0o700)
    if path.is_file():shutil.copy2(path,d/path.name)
    return d

def _replace_marker_block(raw,begin,end,new_block):
    if begin in raw or end in raw:
        if raw.count(begin)!=1 or raw.count(end)!=1:raise RuntimeError('nginx marker count invalid')
        a=raw.index(begin);line_start=raw.rfind('\n',0,a)+1
        b=raw.index(end,a)+len(end);line_end=raw.find('\n',b)
        if line_end<0:line_end=len(raw)
        else:line_end+=1
        return raw[:line_start]+new_block+raw[line_end:]
    if GENERIC_ANCHOR not in raw:raise RuntimeError('generic Browser Studio location anchor not found')
    if raw.count(GENERIC_ANCHOR)!=1:raise RuntimeError('generic Browser Studio location anchor is not unique')
    return raw.replace(GENERIC_ANCHOR,new_block+GENERIC_ANCHOR,1)

def _apply_nginx(raw,new,tag):
    if raw==new:return {'changed':False,'backup':None,'nginx_sha256':sha(NGINX_CONF)}
    backup=backup_file(NGINX_CONF,tag)
    fd,tmpname=tempfile.mkstemp(prefix='.'+NGINX_CONF.name+'.',suffix='.tmp',dir=str(NGINX_CONF.parent))
    os.close(fd);tmp=pathlib.Path(tmpname)
    try:
        tmp.write_text(new,encoding='utf-8');os.chmod(tmp,0o644);os.replace(tmp,NGINX_CONF)
        run(['nginx','-t'],timeout=10);run(['systemctl','reload','nginx.service'],timeout=15)
    except Exception:
        saved=backup/NGINX_CONF.name
        if saved.is_file():shutil.copy2(saved,NGINX_CONF)
        run(['nginx','-t'],timeout=10,check=False);run(['systemctl','reload','nginx.service'],timeout=15,check=False)
        raise
    return {'changed':True,'backup':str(backup),'nginx_sha256':sha(NGINX_CONF)}

def ensure_rescue_route():
    raw=NGINX_CONF.read_text(encoding='utf-8')
    if 'location ^~ /__tapein-rescue/' in raw and RESCUE_MARKER_BEGIN not in raw:
        raise RuntimeError('unmanaged rescue route already exists')
    new=_replace_marker_block(raw,RESCUE_MARKER_BEGIN,RESCUE_MARKER_END,RESCUE_BLOCK)
    return _apply_nginx(raw,new,'before-rescue-status-route')

def repair_agent_results_route():
    raw=NGINX_CONF.read_text(encoding='utf-8')
    if 'location ^~ /agent-results/' in raw and AGENT_RESULTS_MARKER_BEGIN not in raw:
        raise RuntimeError('unmanaged agent-results route already exists')
    new=_replace_marker_block(raw,AGENT_RESULTS_MARKER_BEGIN,AGENT_RESULTS_MARKER_END,AGENT_RESULTS_BLOCK)
    return _apply_nginx(raw,new,'before-agent-results-route-repair')

def restart_control():
    before={'service':service_state(CONTROL_SERVICE),'timer':service_state(CONTROL_TIMER),'timer_enabled':service_enabled(CONTROL_TIMER)}
    run(['systemctl','restart',CONTROL_SERVICE],timeout=25)
    after={'service':service_state(CONTROL_SERVICE),'timer':service_state(CONTROL_TIMER),'timer_enabled':service_enabled(CONTROL_TIMER)}
    if after['service']!='active':raise RuntimeError('Control did not return active')
    return {'before':before,'after':after}

def exercise_control_recovery():
    before={'service':service_state(CONTROL_SERVICE),'timer':service_state(CONTROL_TIMER),'timer_enabled':service_enabled(CONTROL_TIMER),'control_sha256':sha(CONTROL_PATH)}
    if before['service']!='active':raise RuntimeError('Control must be active before isolated recovery exercise')
    unit='tapein-rescue-failsafe-'+dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d%H%M%S')
    fs=run(['systemd-run','--quiet','--unit',unit,'--on-active=20s','--collect','/bin/systemctl','restart',CONTROL_SERVICE],timeout=10,check=False)
    if fs.returncode!=0:raise RuntimeError('could not arm Control fail-safe restart')
    timer_was_active=(before['timer']=='active')
    if timer_was_active:run(['systemctl','stop',CONTROL_TIMER],timeout=10)
    run(['systemctl','stop',CONTROL_SERVICE],timeout=15)
    down_service=service_state(CONTROL_SERVICE);down_timer=service_state(CONTROL_TIMER)
    if down_service=='active':raise RuntimeError('Control service did not stop for recovery exercise')
    probe={'observed_control_service':down_service,'observed_control_timer':down_timer,'rescue_pid':os.getpid(),'rescue_still_executing':True}
    run(['systemctl','start',CONTROL_SERVICE],timeout=25)
    if timer_was_active:run(['systemctl','start',CONTROL_TIMER],timeout=10)
    time.sleep(1)
    after={'service':service_state(CONTROL_SERVICE),'timer':service_state(CONTROL_TIMER),'timer_enabled':service_enabled(CONTROL_TIMER),'control_sha256':sha(CONTROL_PATH)}
    if after['service']!='active':raise RuntimeError('Control recovery exercise failed to restore service')
    if after['control_sha256']!=before['control_sha256']:raise RuntimeError('Control source changed during recovery exercise')
    return {'before':before,'while_control_down':probe,'after':after,'failsafe_unit':unit}

def install_control_from_url(params):
    url=str(params.get('url') or '');expected_sha=str(params.get('sha256') or '').lower();expected_current_sha=str(params.get('expected_current_sha256') or '').lower()
    if not url.startswith('https://') or len(expected_sha)!=64:raise RuntimeError('invalid install_control_from_url params')
    cur=sha(CONTROL_PATH)
    if expected_current_sha and cur!=expected_current_sha:raise RuntimeError(f'control CAS mismatch: {cur}')
    req=urllib.request.Request(url,headers={'User-Agent':'TapeInRescue/3.0','Cache-Control':'no-cache'})
    with urllib.request.urlopen(req,timeout=30) as r:data=r.read(6_000_001)
    if len(data)>6_000_000:raise RuntimeError('Control artifact too large')
    got=hashlib.sha256(data).hexdigest()
    if got!=expected_sha:raise RuntimeError(f'artifact sha mismatch: {got}')
    bdir=backup_file(CONTROL_PATH,'control-install')
    fd,tmpname=tempfile.mkstemp(prefix='tapein-control-',suffix='.py',dir=str(CONTROL_PATH.parent));os.close(fd);tmp=pathlib.Path(tmpname)
    try:
        tmp.write_bytes(data);run(['python3','-m','py_compile',str(tmp)],timeout=30);os.chmod(tmp,0o755);os.replace(tmp,CONTROL_PATH);restart_control()
    except Exception:
        saved=bdir/CONTROL_PATH.name
        if saved.is_file():shutil.copy2(saved,CONTROL_PATH);restart_control()
        raise
    return {'installed_sha256':sha(CONTROL_PATH),'backup':str(bdir)}

def execute(action,params):
    if action=='status':return snapshot()
    if action=='restart_control':return restart_control()
    if action=='exercise_control_recovery':return exercise_control_recovery()
    if action=='repair_agent_results_route':return repair_agent_results_route()
    if action=='recover_control_plane':return {'agent_results_route':repair_agent_results_route(),'control_restart':restart_control()}
    if action=='reload_nginx':run(['nginx','-t'],timeout=10);run(['systemctl','reload','nginx.service'],timeout=15);return {'nginx_service':service_state('nginx.service')}
    if action=='install_control_from_url':return install_control_from_url(params)
    raise RuntimeError('action not allowed')

def fetch_bytes(url):
    req=urllib.request.Request(url+('&' if '?' in url else '?')+f'cb={time.time_ns()}',headers={'User-Agent':'TapeInRescue/3.0','Cache-Control':'no-cache','Pragma':'no-cache'})
    with urllib.request.urlopen(req,timeout=15) as r:return r.read(2_000_000)

def load_state():
    try:return json.loads(STATE_FILE.read_text(encoding='utf-8'))
    except Exception:return {'last_seq':0,'last_id':None}

def verify(command_bytes,sig_b64):
    with tempfile.TemporaryDirectory(prefix='tapein-rescue-verify-') as td:
        td=pathlib.Path(td);c=td/'command.json';s=td/'command.sig';c.write_bytes(command_bytes);s.write_bytes(base64.b64decode(sig_b64,validate=True))
        p=run(['openssl','dgst','-sha256','-verify',str(PUBKEY),'-signature',str(s),str(c)],timeout=10,check=False)
        return p.returncode==0

def main():
    STATE_DIR.mkdir(parents=True,exist_ok=True,mode=0o700);RESULT_DIR.mkdir(parents=True,exist_ok=True,mode=0o755)
    state=load_state();base={'schema':'tapein.rescue.result/2','checked_at':dt.datetime.now(dt.timezone.utc).isoformat(),'agent':'3.0'}
    try:
        command_bytes=fetch_bytes(COMMAND_URL);sig_b64=fetch_bytes(SIG_URL).strip()
        if not verify(command_bytes,sig_b64):raise RuntimeError('signature verification failed')
        cmd=json.loads(command_bytes.decode('utf-8'))
        if cmd.get('schema')!=SCHEMA:raise RuntimeError('unsupported command schema')
        seq=int(cmd.get('seq',0));cid=str(cmd.get('id') or '')
        if seq<=int(state.get('last_seq',0)):
            atomic_json(RESULT_FILE,{**base,'status':'IDLE','last_seq':state.get('last_seq',0),'last_id':state.get('last_id'),'system':snapshot()},0o644);return
        if not cid or seq<1:raise RuntimeError('invalid command id/seq')
        action=str(cmd.get('action') or '');started=dt.datetime.now(dt.timezone.utc).isoformat();details=execute(action,cmd.get('params') or {})
        state={'last_seq':seq,'last_id':cid,'last_action':action,'finished_at':dt.datetime.now(dt.timezone.utc).isoformat()};atomic_json(STATE_FILE,state,0o600)
        atomic_json(RESULT_FILE,{**base,'status':'PASS','command_id':cid,'seq':seq,'action':action,'started_at':started,'details':details,'system':snapshot()},0o644)
    except Exception as e:
        atomic_json(RESULT_FILE,{**base,'status':'FAIL','error':f'{type(e).__name__}: {e}','system':snapshot()},0o644);raise

if __name__=='__main__':main()
PY_AGENT
chmod 0755 /usr/local/lib/tapein-rescue/agent.py

cat > /etc/tapein-rescue/public.pem <<'PUBKEY'
-----BEGIN PUBLIC KEY-----
MIIBojANBgkqhkiG9w0BAQEFAAOCAY8AMIIBigKCAYEArduJKJk704yrbwGeG3Qf
6y349eniDLU665dj/hZgz3usF2GWBA410KcvVV32h9NOw/WmaPploYZauN6oVqCB
aRV7EehdRWj8usF9ebXznESUDTfDIzk5FrnSBme2qZZ3RSj8SfVeEqMpVRjJ+2iP
8vS8qiWhylg4UtJDP11hQZAvzeRV4GsBKv2bGR1ABeuMGBH7Xq2fv9lL6cP4LZFO
XZJtGYHXo6Ysc52pPaRgCvl76g2ghBR12+b7Ow108kjbyPQj1sDhgs4qTPy5MmYy
F9R9Z8sZeTW9vbI73CL9Mog4Bs50j7Z3dfC5xTOFUv8dAFQPX5hEAxBdnMhZNh+V
GOrHNINRnXNrjRkHI/PG71MFT6HtPbZVVup03OT9hfmlYcv6ncFrNPirfWJ/INxD
piv+HgaK6HmWFczyOTewfU2zZZZz2Ip2KFCJ/5Az3QTuZC5BXtnrqJeD84NZi1Zf
I7rU7sgbQCChw6o6ywUYuhaPMNF/HGf50bTu+D06Z0EhAgMBAAE=
-----END PUBLIC KEY-----
PUBKEY
chmod 0644 /etc/tapein-rescue/public.pem

cat > /etc/systemd/system/tapein-rescue.service <<'UNIT'
[Unit]
Description=Tape In Rescue Supervisor v3
After=network-online.target nginx.service
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/bin/python3 /usr/local/lib/tapein-rescue/agent.py
User=root
Group=root
PrivateTmp=true
ProtectHome=true
UMask=0077
TimeoutStartSec=70
UNIT

cat > /etc/systemd/system/tapein-rescue.timer <<'TIMER'
[Unit]
Description=Poll signed Tape In rescue commands

[Timer]
OnBootSec=15s
OnUnitActiveSec=30s
AccuracySec=5s
Persistent=true
Unit=tapein-rescue.service

[Install]
WantedBy=timers.target
TIMER

python3 - <<'PY_BOOT'
import importlib.util, json, datetime as dt
spec=importlib.util.spec_from_file_location('tapein_rescue','/usr/local/lib/tapein-rescue/agent.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
route=m.ensure_rescue_route()
m.atomic_json(m.RESULT_FILE,{
  'schema':'tapein.rescue.result/2','checked_at':dt.datetime.now(dt.timezone.utc).isoformat(),
  'agent':'3.0','status':'BOOTSTRAP_INSTALLED','details':{'rescue_route':route},'system':m.snapshot()
},0o644)
PY_BOOT

systemctl daemon-reload
systemctl enable --now tapein-rescue.timer
systemctl start tapein-rescue.service
systemctl is-enabled --quiet tapein-rescue.timer
systemctl is-active --quiet tapein-rescue.timer
python3 -m py_compile /usr/local/lib/tapein-rescue/agent.py
nginx -t

echo "TAPEIN_RESCUE_V3_INSTALL_PASS"
