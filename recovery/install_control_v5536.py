#!/usr/bin/env python3
from pathlib import Path
import base64, hashlib, os, shutil, sqlite3, subprocess, sys, tempfile, time, urllib.request, json

CONTROL=Path("/usr/local/lib/tapein-control-v4/tapein_control_v4.py")
STATE_DB=Path("/var/lib/tapein-control-v4/state.sqlite")
BACKUP_ROOT=Path("/var/backups/tapein-control-v4/manual-breakglass")
SERVICE="tapein-control-v4.service"
TIMER="tapein-control-v4.timer"
OLD_SHA="42b73cb43d45bab7fa69070e0ad60f9351fd3d44d9314c5af359c1d805a3657f"
NEW_SHA="9193b574cb0c1df4e5d161dbef05cdf828c72c300b7af4ba41336b923422b3ef"
OLD_BUILD="v5-534-browser-studio-checkpoint-scope-fix-v5533"
NEW_BUILD="v5-536-queuev2-bounded-tail-resync-v5535"
OLD_BUILD_LINE=base64.b64decode("Q09OVFJPTF9CVUlMRD0ndjUtNTM0LWJyb3dzZXItc3R1ZGlvLWNoZWNrcG9pbnQtc2NvcGUtZml4LXY1NTMzJwo=")
NEW_BUILD_LINE=base64.b64decode("Q09OVFJPTF9CVUlMRD0ndjUtNTM2LXF1ZXVldjItYm91bmRlZC10YWlsLXJlc3luYy12NTUzNScK")
OLD_BLOCK=base64.b64decode("ZGVmIF9xdWV1ZV92Ml9mdWxsX3JlY29uY2lsZShjLGN1cnNvcl9iZWZvcmU9MCxib3VuZGFyeV9iZWZvcmU9JycsY2Vhc29uPSdzZWVkJyk6CglyYXc9ZmV0Y2hfdGV4dChRVUVVRV9WMl9DU1ZfVVJMK2YnJmNiPXt0aW1lLnRpbWVfbnMoKX0nLG1heF9ieXRlcz04KjEwMjQqMTAyNCkKCWJvdW5kYXJ5X2luZGV4PWN1cnNvcl9iZWZvcmUtMSBpZiBjdXJzb3JfYmVmb3JlPjAgZWxzZSBOb25lCgl0b3RhbCxsYXN0LGJvdW5kYXJ5X2FjdHVhbD1fcXVldWVfdjJfc2Nhbl9tZXRhKHJhdyxib3VuZGFyeV9pbmRleCkKCWlmIGN1cnNvcl9iZWZvcmU+MCBhbmQodG90YWw8Y3Vyc29yX2JlZm9yZSBvciBib3VuZGFyeV9hY3R1YWwhPWJvdW5kYXJ5X2JlZm9yZSk6CgkJcmFpc2UgQ29udHJvbEVycm9yKCdRVUVVRV9WMl9BUFBFTkRfT05MWV9WSU9MQVRJT04nLGpkdW1wKHsnY3Vyc29yX2JlZm9yZSc6Y3Vyc29yX2JlZm9yZSwndG90YWxfcm93cyc6dG90YWwsJ2V4cGVjdGVkX2JvdW5kYXJ5Jzpib3VuZGFyeV9iZWZvcmUsJ2FjdHVhbF9ib3VuZGFyeSc6Ym91bmRhcnlfYWN0dWFsfSkpCgl0YXNrcz1wYXJzZV9xdWV1ZV92Ml9jc3YocmF3LHNraXBfbm9uYmxhbms9Y3Vyc29yX2JlZm9yZSkKCXJldHVybiB0YXNrcyx7J21vZGUnOidmdWxsX3JlY29uY2lsZScsJ3JlYXNvbic6cmVhc29uLCdjdXJzb3JfYmVmb3JlJzpjdXJzb3JfYmVmb3JlLCdjdXJzb3JfYWZ0ZXInOnRvdGFsLCdib3VuZGFyeV9hZnRlcic6bGFzdCwnbmV3X3Jhd19yb3dzJzptYXgoMCx0b3RhbC1jdXJzb3JfYmVmb3JlKSwnaGFzX21vcmUnOkZhbHNlfQoKZGVmIGZldGNoX3F1ZXVlX3YyX2luY3JlbWVudGFsKGMpOgoJcmF3X3N0YXRlPV9jb250cm9sX21ldGFfZ2V0KGMsUVVFVUVfVjJfQ1VSU09SX0tFWSkKCXN0YXRlPXt9CglpZiByYXdfc3RhdGU6CgkJdHJ5OgoJCQlzdGF0ZT1qc29uLmxvYWRzKHJhd19zdGF0ZSkKCQlleGNlcHQgRXhjZXB0aW9uOgoJCQlzdGF0ZT17fQoJdHJ5OgoJCWN1cnNvcj1pbnQoc3RhdGUuZ2V0KCdjdXJzb3InLDApb3IgMClpZiBpc2luc3RhbmNlKHN0YXRlLGRpY3QpZWxzZSAwCgJleGNlcHQgRXhjZXB0aW9uOgoJCWN1cnNvcj0wCglib3VuZGFyeT1zdHIoc3RhdGUuZ2V0KCdib3VuZGFyeV90YXNrX2lkJylvciAnJylpZiBpc2luc3RhbmNlKHN0YXRlLGRpY3QpZWxzZSAnJwoJaWYgY3Vyc29yPDAgb3IoY3Vyc29yPjAgYW5kIG5vdCBib3VuZGFyeSk6CgkJY3Vyc29yPTAKCQlib3VuZGFyeT0nJwoJaWYgY3Vyc29yPT0wOgoJCXJldHVybiBfcXVldWVfdjJfZnVsbF9yZWNvbmNpbGUoYywwLCcnLCdpbml0aWFsX3NlZWQnKQoJZGVmIGhvbGQocmVhc29uKToKCQlyZXR1cm4gW10seyJtb2RlIjoiaW5jcmVtZW50YWxfaG9sZCIsInJlYXNvbiI6c3RyKHJlYXNvbilbOjI0MF0sImN1cnNvcl9iZWZvcmUiOmN1cnNvciwiY3Vyc29yX2FmdGVyIjpjdXJzb3IsImJvdW5kYXJ5X2FmdGVyIjpib3VuZGFyeSwibmV3X3Jhd19yb3dzIjowLCJoYXNfbW9yZSI6RmFsc2UsImRlZ3JhZGVkIjpUcnVlfQoJc3RhcnQ9Y3Vyc29yLTEKCWxpbWl0PVFVRVVFX1YyX0lOQ1JFTUVOVEFMX0JBVENIKzEKCXRxPWYnc2VsZWN0ICogd2hlcmUgQSBpcyBub3QgbnVsbCBsaW1pdCB7bGltaXR9IG9mZnNldCB7c3RhcnR9JwoJdXJsPVFVRVVFX1YyX0dWSVpfQ1NWX1VSTCsnJnRxPScrdXJsbGliLnBhcnNlLnF1b3RlKHRxLHNhZmU9JycpK2YnJmNiPXt0aW1lLnRpbWVfbnMoKX0nCgl0cnk6CgkJcmF3PWZldGNoX3RleHQodXJsLHRpbWVvdXQ9MjAsbWF4X2J5dGVzPTgqMTAyNCoxMDI0KQoJCXNlZW4sbGFzdCxib3VuZGFyeV9hY3R1YWw9X3F1ZXVlX3YyX3NjYW5fbWV0YShyYXcsMCkKCQlpZiBzZWVuPDEgb3IgYm91bmRhcnlfYWN0dWFsIT1ib3VuZGFyeToKCQkJcmV0dXJuIGhvbGQoJ2luY3JlbWVudGFsX2JvdW5kYXJ5X21pc21hdGNoJykKCQluZXdfcmF3PW1heCgwLHNlZW4tMSkKCQl0YXNrcz1wYXJzZV9xdWV1ZV92Ml9jc3YocmF3LHNraXBfbm9uYmxhbms9MSkKCQlyZXR1cm4gdGFza3MseyJtb2RlIjoiaW5jcmVtZW50YWxfZ3ZpeiIsInJlYXNvbiI6ImN1cnNvcl9tYXRjaCIsImN1cnNvcl9iZWZvcmUiOmN1cnNvciwiY3Vyc29yX2FmdGVyIjpjdXJzb3IrbmV3X3JhdywiYm91bmRhcnlfYWZ0ZXIiOmxhc3QgaWYgbmV3X3JhdyBlbHNlIGJvdW5kYXJ5LCJuZXdfcmF3X3Jvd3MiOm5ld19yYXcsImhhc19tb3JlIjpuZXdfcmF3Pj1RVUVVRV9WMl9JTkNSRU1FTlRBTF9CQVRDSCwiZGVncmFkZWQiOkZhbHNlfQoJZXhjZXB0IENvbnRyb2xFcnJvciBhcyBlOgoJCWlmIGUuY29kZT09J1FVRVVFX1YyX0FQUEVORF9PTkxZX1ZJT0xBVElPTic6CgkJCXJhaXNlCgkJcmV0dXJuIGhvbGQoZidpbmNyZW1lbnRhbF9lcnJvcjp7ZS5jb2RlfScpCglleGNlcHQgRXhjZXB0aW9uIGFzIGU6CgkJcmV0dXJuIGhvbGQoZidpbmNyZW1lbnRhbF9lcnJvcjp7dHlwZShlKS5fX25hbWVfX30nKQoK")
NEW_BLOCK=base64.b64decode("ZGVmIF9xdWV1ZV92Ml9xdWVyeV9jc3YodHEsdGltZW91dD0yMCxtYXhfYnl0ZXM9MTAyNCoxMDI0KToKCXVybD1RVUVVRV9WMl9HVklaX0NTVl9VUkwrJyZ0cT0nK3VybGxpYi5wYXJzZS5xdW90ZShzdHIodHEpLHNhZmU9JycpK2YnJmNiPXt0aW1lLnRpbWVfbnMoKX0nCglyZXR1cm4gZmV0Y2hfdGV4dCh1cmwsdGltZW91dD10aW1lb3V0LG1heF9ieXRlcz1tYXhfYnl0ZXMpCgpkZWYgX3F1ZXVlX3YyX2NvdW50X3Jvd3MoKToKCXJhdz1fcXVldWVfdjJfcXVlcnlfY3N2KCdzZWxlY3QgY291bnQoQSkgd2hlcmUgQSBpcyBub3QgbnVsbCcsdGltZW91dD0yMCxtYXhfYnl0ZXM9NjU1MzYpCglyb3dzPWxpc3QoY3N2LnJlYWRlcihpby5TdHJpbmdJT0KHcmF3LmxzdHJpcCgnXHUFEZmYnJlcGxhY2UoJywnLCcnKSkpCgkJZm9yIGNlbGwgaW4gcmV2ZXJzZWQocm93KToKCQkJbT1yZS5zZWFyY2gocidcZCsnLHN0cihjZWxsIG9yICcnKS5yZXBsYWNlKCcsJywnJykpCgkJCWlmIG06CgkJCQlyZXR1cm4gaW50KG0uZ3JvdXAoMCkpCglyYWlzZSBDb250cm9sRXJyb3IoJ1FVRVVFX1YyX0NPVU5UX0lOVkFMSUQnKQoKZGVmIF9xdWV1ZV92Ml9yYXdfdGFza19pZHMocmF3KToKCXRyeTpyPWNzdi5EaWN0UmVhZGVyKGlvLlN0cmluZ0lPKHJhdy5sc3RyaXAoJ1x1ZmVmZicpKSkKCWV4Y2VwdCBFeGNlcHRpb24gYXMgZTpyYWlzZSBDb250cm9sRXJyb3IoJ1FVRVVFX1YyX0NTVl9JTlZBTElEJyx0eXBlKGUpLl9fbmFtZV9fKQoJaWYgbm90IHIuZmllbGRuYW1lcyBvciAndGFza19pZCcgbm90IGluIHtzdHIoeCBvciAnJykuc3RyaXAoKSBmb3IgeCBpbiByLmZpZWxkbmFtZXN9OgoJCXJhaXNlIENvbnRyb2xFcnJvcignUVVFVUVfVjJfSEVBREVSX0lOVkFMSUQnKQoJcmV0dXJuIFtzdHIocm93LmdldCgndGFza19pZCcpb3IgJycpLnN0cmlwKCkgZm9yIHJvdyBpbiByIGlmIGlzaW5zdGFuY2Uocm93LGRpY3QpIGFuZCBhbnkoc3RyKHYgb3IgJycpLnN0cmlwKCkgZm9yIHYgaW4gcm93LnZhbHVlcygpKV0KCmRlZiBmZXRjaF9xdWV1ZV92Ml9pbmNyZW1lbnRhbChjKToKCXJhd19zdGF0ZT1fY29udHJvbF9tZXRhX2dldChjLFFVRVVFX1YyX0NVUlNPUl9LRVkpCglzdGF0ZT17fQoJaWYgcmF3X3N0YXRlOgoJCXRyeTpzdGF0ZT1qc29uLmxvYWRzKHJhd19zdGF0ZSkKCQlleGNlcHQgRXhjZXB0aW9uOnN0YXRlPXt9Cgl0cnk6Y3Vyc29yPWludChzdGF0ZS5nZXQoJ2N1cnNvcicsMClvciAwKWlmIGlzaW5zdGFuY2Uoc3RhdGUsZGljdCllbHNlIDAKCWV4Y2VwdCBFeGNlcHRpb246Y3Vyc29yPTAKCWJvdW5kYXJ5PXN0cihzdGF0ZS5nZXQoJ2JvdW5kYXJ5X3Rhc2tfaWQnKW9yICcnKWlmIGlzaW5zdGFuY2Uoc3RhdGUsZGljdCllbHNlICcnCglpZiBjdXJzb3I8MCBvcihjdXJzb3I+MCBhbmQgbm90IGJvdW5kYXJ5KTpjdXJzb3I9MDtib3VuZGFyeT0nJwoJZGVmIGhvbGQocmVhc29uKToKCQlyZXR1cm4gW10seyJtb2RlIjoiaW5jcmVtZW50YWxfaG9sZCIsInJlYXNvbiI6c3RyKHJlYXNvbilbOjI0MF0sImN1cnNvcl9iZWZvcmUiOmN1cnNvciwiY3Vyc29yX2FmdGVyIjpjdXJzb3IsImJvdW5kYXJ5X2FmdGVyIjpib3VuZGFyeSwibmV3X3Jhd19yb3dzIjowLCJoYXNfbW9yZSI6RmFsc2UsImRlZ3JhZGVkIjpUcnVlfQoJIyBGaXJzdCBzZWVkIGlzIGJvdW5kZWQ6IGNvdW50IHJlbW90ZWx5LCB0aGVuIGluc3BlY3Qgb25seSBhIHNtYWxsIHRhaWwuIEV4aXN0aW5nIHRhc2sgREIgZGVkdXBlcyBvdmVybGFwLgoJaWYgY3Vyc29yPT0wOgoJCXRyeToKCQkJdG90YWw9X3F1ZXVlX3YyX2NvdW50X3Jvd3MoKQoJCQl3aW5kb3c9bWF4KFFVRVVFX1YyX0lOQ1JFTUVOVEFMX0JBVENIKjIsMTAwKQoJCQlzdGFydD1tYXgoMCx0b3RhbC13aW5kb3cpCgkJCXJhdz1fcXVldWVfdjJfcXVlcnlfY3N2KGYnc2VsZWN0ICogd2hlcmUgQSBpcyBub3QgbnVsbCBsaW1pdCB7d2luZG93fSBvZmZzZXQge3N0YXJ0fScpCgkJCWlkcz1fcXVldWVfdjJfcmF3X3Rhc2tfaWRzKHJhdyk7c2Vlbj1sZW4oaWRzKQoJCQlsYXN0PWlkc1stMV0gaWYgaWRzIGVsc2UgJycKCQkJdGFza3M9cGFyc2VfcXVldWVfdjJfY3N2KHJhdykKCQkJcmV0dXJuIHRhc2tzLHsibW9kZSI6ImJvdW5kZWRfdGFpbF9zZWVkIiwicmVhc29uIjoiaW5pdGlhbF9zZWVkIiwiY3Vyc29yX2JlZm9yZSI6MCwiY3Vyc29yX2FmdGVyIjpzdGFydCtzZWVuLCJib3VuZGFyeV9hZnRlciI6bGFzdCwibmV3X3Jhd19yb3dzIjpzZWVuLCJoYXNfbW9yZSI6c3RhcnQrc2Vlbjx0b3RhbCwiZGVncmFkZWQiOkZhbHNlLCJyZW1vdGVfdG90YWwiOnRvdGFsfQoJCWV4Y2VwdCBFeGNlcHRpb24gYXMgZToKCQkJcmV0dXJuIGhvbGQoZidib3VuZGVkX3NlZWRfZXJyb3I6e2UuY29kZSBpZiBpc2luc3RhbmNlKGUsQ29udHJvbEVycm9yKSBlbHNlIHR5cGUoZSkuX19uYW1lX199JykKCXN0YXJ0PWN1cnNvci0xO2xpbWl0PVFVRVVFX1YyX0lOQ1JFTUVOVEFMX0JBVENIKzEKCXRyeToKCQlyYXc9X3F1ZXVlX3YyX3F1ZXJ5X2NzdihmJ3NlbGVjdCAqIHdoZXJlIEEgaXMgbm90IG51bGwgbGltaXQge2xpbWl0fSBvZmZzZXQge3N0YXJ0fScpCgkJaWRzPV9xdWV1ZV92Ml9yYXdfdGFza19pZHMocmF3KQoJCWlmIGlkcyBhbmQgaWRzWzBdPT1ib3VuZGFyeToKCQkJbmV3X2lkcz1pZHNbMTpdO3Rhc2tzPXBhcnNlX3F1ZXVlX3YyX2NzdyhyYXcsc2tpcF9ub25ibGFuaz0xKQoJCQlyZXR1cm4gdGFza3MseyJtb2RlIjoiaW5jcmVtZW50YWxfZ3ZpeiIsInJlYXNvbiI6ImN1cnNvcl9tYXRjaCIsImN1cnNvcl9iZWZvcmUiOmN1cnNvciwiY3Vyc29yX2FmdGVyIjpjdXJzb3IrbGVuKG5ld19pZHMpLCJib3VuZGFyeV9hZnRlciI6bmV3X2lkc1stMV0gaWYgbmV3X2lkcyBlbHNlIGJvdW5kYXJ5LCJuZXdfcmF3X3Jvd3MiOmxlbihuZXdfaWRzKSwiaGFzX21vcmUiOmxlbihuZXdfaWRzKT49UVVFVUVfVjJfSU5DUkVNRU5UQUxfQkFUQ0gsImRlZ3JhZGVkIjpmYWxzZX0KCQkjIE9uZSBib3VuZGVkIHNlbGYtaGVhbCB3aW5kb3cgYXJvdW5kIHRoZSBkdXJhYmxlIGN1cnNvcjsgbmV2ZXIgc2NhbiBmdWxsIGhpc3RvcnkuCgkJcmVjb3ZlcnlfYmFjaz04O3JlY292ZXJ5X3N0YXJ0PW1heCgwLGN1cnNvci1yZWNvdmVyeV9iYWNrKQoJCXJhdzI9X3F1ZXVlX3YyX3F1ZXJ5X2NzdiBmJ3NlbGVjdCAqIHdoZXJlIEEgaXMgbm90IG51bGwgbGltaXQge1FVRVVFX1YyX0lOQ1JFTUVOVEFMX0JBVENIK3JlY292ZXJ5X2JhY2srMX0gb2Zmc2V0IHtyZWNvdmVyeV9zdGFydH0nKQoJCWlkczI9X3F1ZXVlX3YyX3Jhd190YXNrX2lkcyhyYXcyKQoJCWlmIGJvdW5kYXJ5IGluIGlkczI6CgkJCWk9aWRzMi5pbmRleChib3VuZGFyeSk7bmV3X2lkcz1pZHMyW2krMTppKzErUVVFVUVfVjJfSU5DUkVNRU5UQUxfQkFUQ0hdCgkJCSMgUmVidWlsZCBhIHRpbnkgQ1NWIGNvbnRhaW5pbmcgaGVhZGVyIHBsdXMgb25seSByb3dzIGFmdGVyIHRoZSByZWNvdmVyZWQgYm91bmRhcnkuCgkJCXJvd3M9bGlzdChjc3YucmVhZGVyKGlvLlN0cmluZ0lPKHJhdzIubHN0cmlwKCdcdWZlZmYnKSkpO2hlYWRlcj1yb3dzWzBdIGlmIHJvd3MgZWxzZSBbXQoJCQlib2R5PXJvd3NbMStpKzE6MStpKzErbGVuKG5ld19pZHMpXQoJCQlidWY9aW8uU3RyaW5nSU8oKTt3PWNzdi53cml0ZXIoYnVmLGxpbmV0ZXJtaW5hdG9yPSdcXG4nKTt3LndyaXRlcm93KGhlYWRlcik7dy53cml0ZXJvd3MoYm9keSkKCQkJdGFza3M9cGFyc2VfcXVldWVfdjJfY3N2KGJ1Zi5nZXR2YWx1ZSgpKQoJCQlyZXR1cm4gdGFza3MseyJtb2RlIjoiYm91bmRlZF9jdXJzb3JfcmVjb3ZlcnkiLCJyZWFzb24iOiJib3VuZGFyeV9yZWNvdmVyZWQiLCJjdXJzb3JfYmVmb3JlIjpjdXJzb3IsImN1cnNvcl9hZnRlciI6Y3Vyc29yK2xlbihuZXdfaWRzKSwiYm91bmRhcnlfYWZ0ZXIiOm5ld19pZHNbLTFdIGlmIG5ld19pZHMgZWxzZSBib3VuZGFyeSwibmV3X3Jhd19yb3dzIjpsZW4obmV3X2lkcyksImhhc19tb3JlIjpsZW4obmV3X2lkcyk+PVFVRVVFX1YyX0lOQ1JFTUVOVEFMX0JBVENILCJkZWdyYWRlZCI6ZmFsc2V9CgkJIyBCb3VuZGFyeSBkaXNhcHBlYXJlZCAoZm9yIGV4YW1wbGUgYWZ0ZXIgYSBvbmUtb2ZmIHNoZWV0IHJlcGFpcikuIFJlY292ZXIgd2l0aG91dCBhIGZ1bGwtaGlzdG9yeSBzY2FuOgoJCSMgY291bnQgcmVtb3RlbHksIGluc3BlY3Qgb25seSBhIGJvdW5kZWQgdGFpbCwgYW5kIHJlbHkgb24gdGhlIGxvY2FsIHRhc2sgREIgZm9yIGlkZW1wb3RlbnQgZGVkdXBlLgoJCXRyeToKCQkJdG90YWw9X3F1ZXVlX3YyX2NvdW50X3Jvd3MoKQoJCQl3aW5kb3c9bWF4KFFVRVVFX1YyX0lOQ1JFTUVOVEFMX0JBVENIKjIsMTAwKQoJCQl0YWlsX3N0YXJ0PW1heCgwLHRvdGFsLXdpbmRvdykKCQkJcmF3Mz1fcXVldWVfdjJfcXVlcnlfY3N2KGYnc2VsZWN0ICogd2hlcmUgQSBpcyBub3QgbnVsbCBsaW1pdCB7d2luZG93fSBvZmZzZXQge3RhaWxfc3RhcnR9JykKCQkJaWRzMz1fcXVldWVfdjJfcmF3X3Rhc2tfaWRzKHJhdyMzKTtzZWVuMz1sZW4oaWRzMykKCQkJbGFzdDM9aWRzM1stMV0gaWYgaWRzMyBlbHNlICcnCgkJCXRhc2tzMz1wYXJzZV9xdWV1ZV92Ml9jc3YocmF3MykKCQkJcmV0dXJuIHRhc2tzMyx7Im1vZGUiOiJib3VuZGVkX3RhaWxfcmVzeW5jIiwicmVhc29uIjoiYm91bmRhcnlfbWlzc2luZ19yZXN5bmNlZCIsImN1cnNvcl9iZWZvcmUiOmN1cnNvciwiY3Vyc29yX2FmdGVyIjp0YWlsX3N0YXJ0K3NlZW4zLCJib3VuZGFyeV9hZnRlciI6bGFzdDMsIm5ld19yYXdfcm93cyI6c2VlbjMsImhhc19tb3JlIjp0YWlsX3N0YXJ0K3NlZW4zPHRvdGFsLCJkZWdyYWRlZCI6ZmFsc2UsInJlbW90ZV90b3RhbCI6dG90YWx9CgkJZXhjZXB0IEV4Y2VwdGlvbiBhcyBlOgoJCQlyZXR1cm4gaG9sZChmJ2luY3JlbWVudGFsX2JvdW5kYXJ5X21pc21hdGNoOntlLmNvZGUgaWYgaXNpbnN0YW5jZShlLENvbnRyb2xFcnJvcikgZWxzZSB0eXBlKGUpLl9fbmFtZV9ffScpCglleGNlcHQgQ29udHJvbEVycm9yIGFzIGU6cmV0dXJuIGhvbGQoZidpbmNyZW1lbnRhbF9lcnJvcjp7ZS5jb2RlfScpCglleGNlcHQgRXhjZXB0aW9uIGFzIGU6cmV0dXJuIGhvbGQoZidpbmNyZW1lbnRhbF9lcnJvcjp7dHlwZShlKS5fX25hbWVfX30nKQoK")

def sha(p):
    h=hashlib.sha256()
    with open(p,"rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()

def run(args, check=True, timeout=120):
    cp=subprocess.run(args,text=True,capture_output=True,timeout=timeout)
    if check and cp.returncode!=0:
        raise RuntimeError("CMD_FAIL "+repr(args)+" rc="+str(cp.returncode)+" stderr="+cp.stderr[-1200:])
    return cp

def current_build_bytes(data):
    for line in data.splitlines():
        if line.startswith(b"CONTROL_BUILD="):
            return line.split(b"=",1)[1].strip().strip(b"'\"").decode("utf-8","replace")
    return ""

def restore(backup):
    shutil.copy2(backup,CONTROL)
    os.chmod(CONTROL,0o755)
    run(["systemctl","restart",TIMER],check=False,timeout=30)
    run(["systemctl","start",SERVICE],check=False,timeout=180)

def fail(msg, code=1):
    print("RECOVERY_FAIL:",msg)
    raise SystemExit(code)

if os.geteuid()!=0:
    fail("must_run_as_root",10)
if not CONTROL.is_file():
    fail("control_path_missing:"+str(CONTROL),11)

data=CONTROL.read_bytes()
cur_sha=hashlib.sha256(data).hexdigest()
cur_build=current_build_bytes(data)
print("PRECHECK build="+cur_build+" sha256="+cur_sha)

if cur_sha==NEW_SHA:
    print("ALREADY_INSTALLED")
    candidate=CONTROL
    backup=None
elif cur_sha==OLD_SHA:
    if cur_build!=OLD_BUILD:
        fail("old_sha_but_build_mismatch:"+cur_build,12)
    if data.count(OLD_BUILD_LINE)!=1:
        fail("old_build_marker_count="+str(data.count(OLD_BUILD_LINE)),13)
    if data.count(OLD_BLOCK)!=1:
        fail("old_queue_block_count="+str(data.count(OLD_BLOCK)),14)

    candidate_bytes=data.replace(OLD_BUILD_LINE,NEW_BUILD_LINE,1).replace(OLD_BLOCK,NEW_BLOCK,1)
    cand_sha=hashlib.sha256(candidate_bytes).hexdigest()
    if cand_sha!=NEW_SHA:
        fail("candidate_sha_mismatch:"+cand_sha,15)

    tmp=CONTROL.with_name(CONTROL.name+".breakglass-new")
    tmp.write_bytes(candidate_bytes)
    os.chmod(tmp,0o755)
    os.chown(tmp,0,0)

    run(["/usr/bin/python3","-m","py_compile",str(tmp)],timeout=60)
    st=run(["/usr/bin/python3",str(tmp),"selftest"],check=False,timeout=60)
    if st.returncode!=0 or "PASS" not in (st.stdout+st.stderr):
        tmp.unlink(missing_ok=True)
        fail("candidate_selftest_failed:"+((st.stdout+st.stderr)[-1200:]),16)

    BACKUP_ROOT.mkdir(parents=True,exist_ok=True)
    stamp=time.strftime("%Y%m%dT%H%M%SZ",time.gmtime())
    backup=BACKUP_ROOT/("tapein_control_v4.py.v5-534."+stamp)
    shutil.copy2(CONTROL,backup)
    if sha(backup)!=OLD_SHA:
        tmp.unlink(missing_ok=True)
        fail("rollback_checkpoint_sha_mismatch",17)

    os.replace(tmp,CONTROL)
    dfd=os.open(str(CONTROL.parent),os.O_DIRECTORY)
    try: os.fsync(dfd)
    finally: os.close(dfd)
    if sha(CONTROL)!=NEW_SHA:
        restore(backup)
        fail("post_install_file_sha_mismatch_rolled_back",18)
    print("INSTALLED rollback="+str(backup))
else:
    fail("BASE_MISMATCH expected_v5_534_or_v5_536 actual_sha="+cur_sha+" actual_build="+cur_build,20)

try:
    run(["systemctl","daemon-reload"],timeout=30)
    run(["systemctl","restart",TIMER],timeout=30)
    svc=run(["systemctl","start",SERVICE],check=False,timeout=240)
    if svc.returncode!=0:
        raise RuntimeError("service_start_rc="+str(svc.returncode)+" "+svc.stderr[-1200:])
    timer=run(["systemctl","is-active",TIMER],check=False,timeout=20)
    if timer.stdout.strip()!="active":
        raise RuntimeError("timer_not_active:"+timer.stdout.strip()+":"+timer.stderr.strip())

    if sha(CONTROL)!=NEW_SHA or current_build_bytes(CONTROL.read_bytes())!=NEW_BUILD:
        raise RuntimeError("installed_identity_changed")

    if not STATE_DB.is_file():
        raise RuntimeError("state_db_missing")
    con=sqlite3.connect(str(STATE_DB))
    try:
        row=con.execute("SELECT value,updated_at FROM control_meta WHERE key='queue_v2.ingress_cursor_v1'").fetchone()
    finally:
        con.close()
    if not row:
        raise RuntimeError("queue_v2_cursor_missing_after_service_run")
    try:
        cursor=json.loads(row[0])
    except Exception as e:
        raise RuntimeError("queue_v2_cursor_invalid:"+type(e).__name__)
    if not isinstance(cursor,dict) or int(cursor.get("cursor",0) or 0)<0:
        raise RuntimeError("queue_v2_cursor_shape_invalid")

    reg_url="https://tapein.ru/agent-results/dbee2e0fbfca21b77fdf8990179a4bc8abec8131d61f4877afdae4b7619d1319.system-registry.json?cb="+str(time.time_ns())
    req=urllib.request.Request(reg_url,headers={"User-Agent":"TapeInBreakglass/1.0","Cache-Control":"no-cache"})
    with urllib.request.urlopen(req,timeout=30) as r:
        reg=json.loads(r.read(1024*1024).decode("utf-8"))
    if reg.get("control_build")!=NEW_BUILD:
        raise RuntimeError("registry_build_mismatch:"+str(reg.get("control_build")))
    if reg.get("control_sha256")!=NEW_SHA:
        raise RuntimeError("registry_sha_mismatch:"+str(reg.get("control_sha256")))

    print("POSTCHECK timer=active")
    print("POSTCHECK cursor="+json.dumps(cursor,separators=(",",":")))
    print("POSTCHECK registry_build="+str(reg.get("control_build")))
    print("POSTCHECK registry_sha256="+str(reg.get("control_sha256")))
    print("RECOVERY_PASS")
except Exception as e:
    if 'backup' in globals() and backup is not None and Path(backup).is_file():
        restore(backup)
        print("ROLLBACK_DONE sha256="+sha(CONTROL))
    fail("runtime_activation_failed:"+str(e),30)
