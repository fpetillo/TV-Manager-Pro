from __future__ import annotations
import os
from waitress import serve
from app import app
import engine
import security

if __name__=="__main__":
    host=os.getenv("HOST","127.0.0.1")
    port=int(os.getenv("PORT","5050"))
    threads=max(4,int(os.getenv("TVMANAGER_THREADS","8")))
    if not security.is_loopback(host):
        if not security.admin_configured() or not security.browser_auth_enabled():
            raise SystemExit("Refusing non-loopback HOST without configured and enabled browser authentication. Start locally, visit /security/setup, then enable LAN binding.")
    engine.start_scheduler()
    print(f"TV Manager production server listening on http://{host}:{port} with {threads} threads")
    serve(app,host=host,port=port,threads=threads,channel_timeout=120)
