from __future__ import annotations
import os
import sys
if __name__=='__main__' and '--service' in sys.argv:
    import service_runtime  # Record boot time before database initialization.
if __name__=='__main__' and '--stop-service' in sys.argv:
    import app_paths
    import service_runtime
    raise SystemExit(service_runtime.request_stop(app_paths.application_root()))
# Archive workers must run before the app takes its installation lease.
if __name__=='__main__' and len(sys.argv)>1 and sys.argv[1]=='--archive-worker':
    import archive_processing
    archive_processing.extract_rar_member(sys.argv[2:])
    raise SystemExit(0)
from waitress import serve
from app import app
import engine
import security
import network_settings

if __name__=="__main__":
    try:
        listener=network_settings.prepare(app.config['TVMANAGER_NETWORK'], security.admin_configured(), security.browser_auth_enabled())
    except ValueError as error:
        raise SystemExit(str(error)) from None
    host,port=listener['host'],listener['port']
    threads=max(4,int(os.getenv("TVMANAGER_THREADS","8")))
    # Required route check: fail fast if an old/partial app file is being served.
    required_routes={"/about","/library-health","/api/version","/api/about","/api/library/health-report"}
    registered={rule.rule for rule in app.url_map.iter_rules()}
    missing=sorted(required_routes-registered)
    if missing:
        raise SystemExit("TV Manager route registration failed. Missing routes: "+", ".join(missing))
    engine.start_scheduler()
    print("Registered support routes: "+", ".join(sorted(required_routes)))
    print(f"TV Manager production server listening on http://{host}:{port} with {threads} threads")
    if '--service' in sys.argv:
        import app_paths
        import service_runtime
        raise SystemExit(service_runtime.serve(app, app_paths.application_root(), engine._STOP, host, port, threads))
    serve(app,host=host,port=port,threads=threads,channel_timeout=120)
