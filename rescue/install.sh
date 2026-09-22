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
import base64, datetime as dt, hashlib, json, os, pathlib, shutil, subprocess, tempfile, urllib.request

SCHEMA = 'tapein.rescue.command/1'
COMMAND_URL = 'https://raw.githubusercontent.com/andreyshabaev/Browser-Studio/tapein-rescue-control/rescue/command.json'
SIG_URL = 'https://raw.githubusercontent.com/andreyshabaev/Browser-Studio/tapein-rescue-control/rescue/command.sig'
PUBKEY = pathlib.Path('/etc/tapein-rescue/public.pem')
STATE_DIR = pathlib.Path('/var/lib/tapein-rescue')
STATE_FILE = STATE_DIR / 'state.json'
RESULT_DIR = pathlib.Path('/var/www/__tapein-rescue')
RESULT_FILE = RESULT_DIR / 'status.json'
NGINX_CONF = pathlib.Path('/etc/nginx/conf.d/00-tapein-authoritative.conf')
CONTROL_PATH = pathlib.Path('/usr/local/lib/tapein-control-v4/tapein_control_v4.py')
BACKUP_ROOT = pathlib.Path('/var/backups/tapein-rescue')
CONTROL_SERVICE = 'tapein-control-v4.service'
CONTROL_TIMER = 'tapein-control-v4.timer'
MARKER_BEGIN = '# TAPEIN_RESCUE_STATIC_ROUTES_V1_BEGIN'
MARKER_END = '# TAPEIN_RESCUE_STATIC_ROUTES_V1_END'
STATIC_BLOCK = f'''    {MARKER_BEGIN}\n    # Machine control results bypass Browser Studio release selection.\n    location ^~ /agent-results/ {{\n        root /var/www/browser-studio-cloud/studio;\n        default_type application/json;\n        add_header Cache-Control "no-store" always;\n        try_files $uri =404;\n    }}\n    # Independent break-glass readback surface.\n    location ^~ /__tapein-rescue/ {{\n        root /var/www;\n        default_type application/json;\n        add_header Cache-Control "no-store" always;\n        try_files $uri =404;\n    }}\n    {MARKER_END}\n\n'''
GENERIC_ANCHOR = '    location / {\n        auth_request /_studio_release;'


def run(cmd, timeout=20, check=True):
    p = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout)
    if check and p.returncode != 0:
        raise RuntimeError(f"command failed ({p.returncode}): {' '.join(cmd)} :: {p.stderr[-2000:]}")
    return p


def sha(path):
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except Exception:
        return None


def service_state(name):
    p = run(['systemctl', 'is-active', name], timeout=8, check=False)
    return (p.stdout.strip() or p.stderr.strip() or f'rc={p.returncode}')


def snapshot(extra=None):
    out = {
        'control_service': service_state(CONTROL_SERVICE),
        'control_timer': service_state(CONTROL_TIMER),
        'nginx_service': service_state('nginx.service'),
        'control_sha256': sha(CONTROL_PATH),
        'nginx_sha256': sha(NGINX_CONF),
        'nginx_test': None,
        'agent_results_route_present': False,
        'rescue_route_present': False,
    }
    p = run(['nginx','-t'], timeout=10, check=False)
    out['nginx_test'] = {'ok': p.returncode == 0, 'stderr': p.stderr[-1200:]}
    try:
        txt = NGINX_CONF.read_text(encoding='utf-8')
        out['agent_results_route_present'] = 'location ^~ /agent-results/' in txt
        out['rescue_route_present'] = 'location ^~ /__tapein-rescue/' in txt
    except Exception:
        pass
    if extra:
        out.update(extra)
    return out


def atomic_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    os.replace(tmp, path)


def backup_nginx(tag):
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    d = BACKUP_ROOT / f'{stamp}-{tag}'
    d.mkdir(mode=0o700)
    shutil.copy2(NGINX_CONF, d / NGINX_CONF.name)
    return d


def ensure_static_routes():
    raw = NGINX_CONF.read_text(encoding='utf-8')
    if MARKER_BEGIN in raw:
        if 'location ^~ /agent-results/' not in raw or 'location ^~ /__tapein-rescue/' not in raw:
            raise RuntimeError('rescue marker exists but route block is incomplete')
        return {'changed': False, 'backup': None}
    if GENERIC_ANCHOR not in raw:
        raise RuntimeError('generic Browser Studio location anchor not found')
    backup = backup_nginx('before-static-routes')
    new = raw.replace(GENERIC_ANCHOR, STATIC_BLOCK + GENERIC_ANCHOR, 1)
    tmp = NGINX_CONF.with_suffix('.conf.tapein-rescue.tmp')
    tmp.write_text(new, encoding='utf-8')
    os.replace(tmp, NGINX_CONF)
    try:
        run(['nginx','-t'], timeout=10)
        run(['systemctl','reload','nginx.service'], timeout=15)
    except Exception:
        shutil.copy2(backup / NGINX_CONF.name, NGINX_CONF)
        run(['nginx','-t'], timeout=10, check=False)
        run(['systemctl','reload','nginx.service'], timeout=15, check=False)
        raise
    return {'changed': True, 'backup': str(backup)}


def restart_control():
    run(['systemctl','restart', CONTROL_TIMER], timeout=15, check=False)
    run(['systemctl','restart', CONTROL_SERVICE], timeout=20)
    return {'control_service': service_state(CONTROL_SERVICE), 'control_timer': service_state(CONTROL_TIMER)}


def install_control_from_url(params):
    url = str(params.get('url') or '')
    expected_sha = str(params.get('sha256') or '').lower()
    expected_current_sha = str(params.get('expected_current_sha256') or '').lower()
    if not url.startswith('https://') or len(expected_sha) != 64:
        raise RuntimeError('invalid install_control_from_url params')
    cur = sha(CONTROL_PATH)
    if expected_current_sha and cur != expected_current_sha:
        raise RuntimeError(f'control CAS mismatch: {cur}')
    with urllib.request.urlopen(url, timeout=30) as r:
        data = r.read(6_000_000)
    got = hashlib.sha256(data).hexdigest()
    if got != expected_sha:
        raise RuntimeError(f'artifact sha mismatch: {got}')
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    bdir = BACKUP_ROOT / f'{stamp}-control-install'
    bdir.mkdir(mode=0o700)
    if CONTROL_PATH.is_file():
        shutil.copy2(CONTROL_PATH, bdir / CONTROL_PATH.name)
    fd, tmpname = tempfile.mkstemp(prefix='tapein-control-', suffix='.py', dir=str(CONTROL_PATH.parent))
    os.close(fd)
    tmp = pathlib.Path(tmpname)
    try:
        tmp.write_bytes(data)
        run(['python3','-m','py_compile',str(tmp)], timeout=30)
        os.chmod(tmp, 0o755)
        os.replace(tmp, CONTROL_PATH)
        restart_control()
    except Exception:
        if (bdir / CONTROL_PATH.name).is_file():
            shutil.copy2(bdir / CONTROL_PATH.name, CONTROL_PATH)
            restart_control()
        raise
    return {'installed_sha256': sha(CONTROL_PATH), 'backup': str(bdir)}


def execute(action, params):
    if action == 'status':
        return snapshot()
    if action == 'restart_control':
        return restart_control()
    if action == 'repair_agent_results_route':
        return ensure_static_routes()
    if action == 'recover_control_plane':
        a = ensure_static_routes()
        b = restart_control()
        return {'route': a, 'restart': b}
    if action == 'reload_nginx':
        run(['nginx','-t'], timeout=10)
        run(['systemctl','reload','nginx.service'], timeout=15)
        return {'nginx_service': service_state('nginx.service')}
    if action == 'install_control_from_url':
        return install_control_from_url(params)
    raise RuntimeError('action not allowed')


def fetch_bytes(url):
    req = urllib.request.Request(url + ('&' if '?' in url else '?') + f'cb={int(dt.datetime.now().timestamp())}', headers={'User-Agent':'TapeInRescue/1.0','Cache-Control':'no-cache'})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read(2_000_000)


def load_state():
    try:
        return json.loads(STATE_FILE.read_text(encoding='utf-8'))
    except Exception:
        return {'last_seq': 0, 'last_id': None}


def verify(command_bytes, sig_b64):
    with tempfile.TemporaryDirectory(prefix='tapein-rescue-verify-') as td:
        td = pathlib.Path(td)
        c = td/'command.json'; s = td/'command.sig'
        c.write_bytes(command_bytes)
        s.write_bytes(base64.b64decode(sig_b64, validate=True))
        p = run(['openssl','dgst','-sha256','-verify',str(PUBKEY),'-signature',str(s),str(c)], timeout=10, check=False)
        return p.returncode == 0


def main():
    STATE_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    state = load_state()
    base = {'schema':'tapein.rescue.result/1','checked_at':dt.datetime.now(dt.timezone.utc).isoformat(),'agent':'1.0'}
    try:
        command_bytes = fetch_bytes(COMMAND_URL)
        sig_b64 = fetch_bytes(SIG_URL).strip()
        if not verify(command_bytes, sig_b64):
            raise RuntimeError('signature verification failed')
        cmd = json.loads(command_bytes.decode('utf-8'))
        if cmd.get('schema') != SCHEMA:
            raise RuntimeError('unsupported command schema')
        seq = int(cmd.get('seq', 0)); cid = str(cmd.get('id') or '')
        if seq <= int(state.get('last_seq', 0)):
            atomic_json(RESULT_FILE, {**base, 'status':'IDLE', 'last_seq':state.get('last_seq',0), 'last_id':state.get('last_id'), 'system': snapshot()})
            return
        if not cid or seq < 1:
            raise RuntimeError('invalid command id/seq')
        action = str(cmd.get('action') or '')
        started = dt.datetime.now(dt.timezone.utc).isoformat()
        details = execute(action, cmd.get('params') or {})
        state = {'last_seq': seq, 'last_id': cid, 'last_action': action, 'finished_at': dt.datetime.now(dt.timezone.utc).isoformat()}
        atomic_json(STATE_FILE, state)
        atomic_json(RESULT_FILE, {**base, 'status':'PASS','command_id':cid,'seq':seq,'action':action,'started_at':started,'details':details,'system':snapshot()})
    except Exception as e:
        atomic_json(RESULT_FILE, {**base, 'status':'FAIL','error':f'{type(e).__name__}: {e}','system':snapshot()})
        raise

if __name__ == '__main__':
    main()
PY_AGENT
chmod 0755 /usr/local/lib/tapein-rescue/agent.py

cat > /etc/tapein-rescue/public.pem <<'PUBKEY'
-----BEGIN PUBLIC KEY-----
MIIBojANBgkqhkiG9w0BAQEFAAOCAY8AMIIBigKCAYEAkqVH+l+Tw6yR/kPXAn4l
qphAs6Y8tiy2y62W4tJ7v2NCEeOoLGvNIu1uMnhXLMwlRMyma99BDyZXp+JcSOc3
0/Pq2xDNoaLQK5wKcYuR0wub1rG0qzm+oYeKVpBktbQp/z87ibphTkPiWWdXs1J6
7StIP3NHgW9D5ieGlQUIDnthvkknsZBBHZOnnLe7WqfAgTQ0JX3dGjLHWmxvORjw
u+3Tvr9cthw62/SQJg01kGFFv0MjbfuH4ej+C0shFCENu3f/9gJs7FxOWHZ4vf6e
2bb530jndQ+SGR6avT3bRgszB9XJw7dFVvFuG8luLPAkxR2lrB/7YsA7BdloNugt
IynXjrRlPrrIaMM9bv+M0mzOg0XOYL5vuwKAROGJJRuViY5qhAIIfbYOrAca05fk
0kYMzdQwgiuPLpfpJP/nWbI4Tcshc3seZEECvup/v2ytNv4Acn23r13+bZId4Nmt
Z3uPNisARHyK27Iln0jyK67ctphimBZ79Ac+ylbmlEPNAgMBAAE=
-----END PUBLIC KEY-----
PUBKEY
chmod 0644 /etc/tapein-rescue/public.pem

cat > /etc/systemd/system/tapein-rescue.service <<'UNIT'
[Unit]
Description=Tape In Rescue Supervisor
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
TimeoutStartSec=60
UNIT

cat > /etc/systemd/system/tapein-rescue.timer <<'TIMER'
[Unit]
Description=Poll signed Tape In rescue commands

[Timer]
OnBootSec=20s
OnUnitActiveSec=30s
AccuracySec=5s
Persistent=true
Unit=tapein-rescue.service

[Install]
WantedBy=timers.target
TIMER

systemctl daemon-reload

# One-time break-glass recovery. This changes only Control-plane infrastructure:
# 1) adds isolated machine-result/rescue routes to the authoritative nginx file;
# 2) restarts only tapein-control-v4.
python3 - <<'PY_BOOT'
import importlib.util, json, datetime as dt
spec=importlib.util.spec_from_file_location('tapein_rescue','/usr/local/lib/tapein-rescue/agent.py')
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
route=m.ensure_static_routes()
restart=m.restart_control()
m.atomic_json(m.RESULT_FILE, {
  'schema':'tapein.rescue.result/1',
  'checked_at':dt.datetime.now(dt.timezone.utc).isoformat(),
  'agent':'1.0',
  'status':'BOOTSTRAP_PASS',
  'details':{'route':route,'restart':restart},
  'system':m.snapshot(),
})
PY_BOOT

systemctl enable --now tapein-rescue.timer
systemctl start tapein-rescue.service || true

echo "Tape In Rescue installed."
echo "Status: https://tapein.ru/__tapein-rescue/status.json"
