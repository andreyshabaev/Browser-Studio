#!/usr/bin/env bash
set -euo pipefail

CFG='/etc/nginx/conf.d/00-tapein-authoritative.conf'
CONTROL='/usr/local/lib/tapein-control-v4/tapein_control_v4.py'
ROOT='/var/backups/tapein-breakglass'
TS="$(date -u +%Y%m%dT%H%M%SZ)"
BK="$ROOT/$TS-agent-results-repair"
mkdir -p "$BK"
chmod 700 "$ROOT" "$BK"

test -f "$CFG"
cp -a "$CFG" "$BK/00-tapein-authoritative.conf.before"
if [ -f "$CONTROL" ]; then
  cp -a "$CONTROL" "$BK/tapein_control_v4.py.before"
fi

python3 - <<'PY'
from pathlib import Path
import os
p=Path('/etc/nginx/conf.d/00-tapein-authoritative.conf')
raw=p.read_text(encoding='utf-8')
begin='# TAPEIN_AGENT_RESULTS_STATIC_ROUTE_V1_BEGIN'
block='''    # TAPEIN_AGENT_RESULTS_STATIC_ROUTE_V1_BEGIN
    # Machine-readable Control results bypass Browser Studio release selection.
    location ^~ /agent-results/ {
        root /var/www/browser-studio-cloud/studio;
        default_type application/json;
        add_header Cache-Control "no-store" always;
        try_files $uri =404;
    }
    # TAPEIN_AGENT_RESULTS_STATIC_ROUTE_V1_END

'''
anchor='    location / {\n        auth_request /_studio_release;'
if begin in raw:
    if 'location ^~ /agent-results/' not in raw:
        raise SystemExit('marker-present-but-route-missing')
else:
    if raw.count(anchor) != 1:
        raise SystemExit(f'generic-anchor-count={raw.count(anchor)}')
    new=raw.replace(anchor, block+anchor, 1)
    tmp=p.with_suffix('.conf.breakglass.tmp')
    tmp.write_text(new, encoding='utf-8')
    os.replace(tmp, p)
PY

if ! nginx -t; then
  cp -a "$BK/00-tapein-authoritative.conf.before" "$CFG"
  nginx -t || true
  systemctl reload nginx.service || true
  echo 'BREAKGLASS_FAIL nginx-test rollback=done'
  exit 31
fi
systemctl reload nginx.service

LOCAL_CODE="$(curl -k -sS --resolve tapein.ru:443:127.0.0.1 -o /tmp/tapein-bootstrap-local.json -w '%{http_code}' --max-time 15 'https://tapein.ru/agent-results/system-bootstrap.json?breakglass=1')"
test "$LOCAL_CODE" = '200'

systemctl reset-failed tapein-control-v4.service tapein-control-v4.timer 2>/dev/null || true
systemctl restart tapein-control-v4.timer 2>/dev/null || true
systemctl restart tapein-control-v4.service

sleep 2
CONTROL_STATE="$(systemctl is-active tapein-control-v4.service || true)"
TIMER_STATE="$(systemctl is-active tapein-control-v4.timer || true)"

LOCAL_CODE2="$(curl -k -sS --resolve tapein.ru:443:127.0.0.1 -o /tmp/tapein-bootstrap-local2.json -w '%{http_code}' --max-time 15 'https://tapein.ru/agent-results/system-bootstrap.json?breakglass=2')"
PUBLIC_CODE="$(curl -k -sS -o /tmp/tapein-bootstrap-public.json -w '%{http_code}' --max-time 20 'https://tapein.ru/agent-results/system-bootstrap.json?breakglass=3')"
test "$LOCAL_CODE2" = '200'
test "$PUBLIC_CODE" = '200'

CFG_SHA="$(sha256sum "$CFG" | awk '{print $1}')"
CONTROL_SHA=''
if [ -f "$CONTROL" ]; then CONTROL_SHA="$(sha256sum "$CONTROL" | awk '{print $1}')"; fi
printf 'BREAKGLASS_PASS\n'
printf 'checkpoint=%s\n' "$BK"
printf 'nginx_sha256=%s\n' "$CFG_SHA"
printf 'control_sha256=%s\n' "$CONTROL_SHA"
printf 'control_state=%s timer_state=%s\n' "$CONTROL_STATE" "$TIMER_STATE"
printf 'local_http=%s public_http=%s\n' "$LOCAL_CODE2" "$PUBLIC_CODE"
