"""Local service control and bounded, observable shutdown for Waitress."""
import json
import os
from pathlib import Path
import threading
import time
import uuid


STOPPING = threading.Event()
PROCESS_STARTED = time.time()


def state_path(base):
    return Path(base) / '.runtime' / 'service.json'


def request_stop(base):
    path = state_path(base)
    path.parent.mkdir(exist_ok=True)
    try:
        state = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        state = {}
    request = path.with_name('service-stop.json')
    temporary = request.with_suffix('.' + uuid.uuid4().hex + '.tmp')
    temporary.write_text(json.dumps({'instance': state.get('instance'), 'requested_at': time.time()}), encoding='utf-8')
    os.replace(temporary, request)
    print('Requested service shutdown; active work will drain before exit.', flush=True)
    return 0


class DrainMiddleware:
    def __init__(self, application):
        self.application = application
        self.active = 0
        self.lock = threading.Lock()

    def __call__(self, environ, start_response):
        with self.lock:
            if STOPPING.is_set():
                start_response('503 Service Unavailable', [('Content-Type', 'text/plain'), ('Retry-After', '30')])
                return [b'TV Manager is stopping. Try again after it restarts.']
            self.active += 1
        try:
            response = self.application(environ, start_response)
        except BaseException:
            with self.lock:
                self.active -= 1
            raise
        def stream():
            try:
                yield from response
            finally:
                try:
                    if hasattr(response, 'close'):
                        response.close()
                finally:
                    with self.lock:
                        self.active -= 1
        return stream()


def workers():
    return [t for t in threading.enumerate() if t.is_alive() and
            t.name.startswith(('tvmanager-', 'TVManagerJob-', 'TVManagerImport-', 'TVManagerScheduler'))]


def serve(application, base, scheduler_stop, host, port, threads=8, drain_seconds=150):
    from waitress import create_server
    STOPPING.clear()
    guarded = DrainMiddleware(application)
    http = create_server(guarded, host=host, port=port, threads=threads, channel_timeout=120)
    path = state_path(base)
    path.parent.mkdir(exist_ok=True)
    instance = uuid.uuid4().hex
    path.write_text(json.dumps({'instance': instance, 'pid': os.getpid(), 'host': host,
                                'port': port, 'started_at': time.time()}), encoding='utf-8')
    runner = threading.Thread(target=http.run, name='TVManagerHTTP', daemon=True)
    runner.start()
    request = path.with_name('service-stop.json')
    result = 0
    print('Service mode ready; local stop control enabled.', flush=True)
    try:
        while runner.is_alive():
            try:
                intent = json.loads(request.read_text(encoding='utf-8'))
                if intent.get('instance') == instance or intent.get('requested_at', 0) >= PROCESS_STARTED:
                    break
            except (OSError, ValueError):
                pass
            time.sleep(.25)
        else:
            result = 1
    except KeyboardInterrupt:
        pass
    finally:
        STOPPING.set()
        scheduler_stop.set()
        print('Service stopping: refusing new requests and draining active jobs.', flush=True)
        deadline = time.monotonic() + drain_seconds
        while (guarded.active or workers()) and time.monotonic() < deadline:
            time.sleep(.1)
        if guarded.active or workers():
            print('ERROR: shutdown drain timed out. Review interrupted jobs before restarting.', flush=True)
            result = 2
        http.close()
        runner.join(timeout=5)
        # The installation lease prevents another instance replacing this state.
        path.unlink(missing_ok=True)
        request.unlink(missing_ok=True)
        print('Service shutdown complete.' if result == 0 else 'Service shutdown incomplete.', flush=True)
    return result
