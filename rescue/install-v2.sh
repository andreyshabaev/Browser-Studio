#!/usr/bin/env bash
set -euo pipefail
curl -fsSL https://raw.githubusercontent.com/andreyshabaev/Browser-Studio/03c8833ed4b018d4889d461308c677c05a0366ca/rescue/install.sh | bash
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
systemctl start tapein-rescue.service || true
echo "Tape In Rescue v2 bootstrap complete"
