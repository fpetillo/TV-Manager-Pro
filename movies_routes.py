"""HTTP routes for the Movies page and API."""
import threading

from flask import jsonify, render_template, request

import engine
import movies


def _error(exc):
    status = 400 if isinstance(exc, ValueError) else 502
    return jsonify(ok=False, error=str(exc)[:500]), status


def register(app):
    @app.get('/movies')
    def movies_page():
        return render_template('movies.html')

    @app.get('/movie/<int:mid>')
    def movie_page(mid):
        return render_template('movie_detail.html', movie_id=mid)

    @app.get('/api/movies/<int:mid>/detail')
    def api_movie_detail(mid):
        try:
            return jsonify(movies.detail(mid))
        except Exception as exc:
            return _error(exc)

    @app.get('/api/movies/dashboard')
    def api_movies_dashboard():
        return jsonify(movies.dashboard_summary())

    @app.get('/api/movies/calendar')
    def api_movies_calendar():
        from datetime import date, timedelta
        start = request.args.get('start') or date.today().isoformat()
        end = request.args.get('end') or (date.today() + timedelta(days=int(request.args.get('days', 14) or 14))).isoformat()
        return jsonify(results=movies.calendar(start, end))

    @app.get('/api/movies')
    def api_movies():
        a = request.args
        return jsonify(movies.listing(a.get('status', ''), a.get('q', '').strip(), a.get('page', 1),
                                      a.get('page_size', 60), a.get('sort', 'added')))

    @app.post('/api/movies')
    def api_movies_add():
        try:
            body = request.get_json(silent=True) or {}
            return jsonify(ok=True, **movies.add_movie(body.get('tmdb_id'), added_via='manual'))
        except Exception as exc:
            return _error(exc)

    @app.get('/api/movies/summary')
    def api_movies_summary():
        return jsonify(movies.summary())

    @app.get('/api/movies/discover')
    def api_movies_discover():
        try:
            a = request.args
            return jsonify(movies.discover_list(a.get('list', 'digital'), a.get('q', '').strip(), a.get('page', 1)))
        except Exception as exc:
            return _error(exc)

    @app.get('/api/movies/settings')
    def api_movies_settings():
        return jsonify(movies.settings_public())

    @app.post('/api/movies/settings')
    def api_movies_settings_save():
        try:
            return jsonify(ok=True, settings=movies.save_settings(request.get_json(silent=True) or {}))
        except Exception as exc:
            return _error(exc)

    @app.get('/api/movies/downloads')
    def api_movies_downloads():
        return jsonify(downloads=movies.downloads())

    @app.post('/api/movies/downloads/<int:did>/fail')
    def api_movies_download_fail(did):
        try:
            return jsonify(movies.retry_download(did))
        except Exception as exc:
            return _error(exc)

    @app.get('/api/movies/<int:mid>')
    def api_movie(mid):
        try:
            return jsonify(movie=movies.get_movie(mid), results=movies.results(mid))
        except Exception as exc:
            return _error(exc)

    @app.post('/api/movies/<int:mid>')
    def api_movie_update(mid):
        try:
            return jsonify(ok=True, movie=movies.update_movie(mid, request.get_json(silent=True) or {}))
        except Exception as exc:
            return _error(exc)

    @app.post('/api/movies/<int:mid>/search')
    def api_movie_search(mid):
        try:
            body = request.get_json(silent=True) or {}
            return jsonify(ok=True, **movies.search_movie(mid, auto_grab=bool(body.get('auto_grab'))))
        except Exception as exc:
            return _error(exc)

    @app.post('/api/movies/results/<int:rid>/grab')
    def api_movie_grab(rid):
        try:
            return jsonify(movies.grab_result(rid))
        except Exception as exc:
            return _error(exc)

    @app.post('/api/movies/jobs/<name>/run')
    def api_movie_job_run(name):
        if name not in movies.JOB_INTERVALS:
            return jsonify(ok=False, error='Unknown movie job'), 404
        # Same lease and run-history path as the scheduler, in the background.
        threading.Thread(target=engine.run_job, args=(name,), daemon=True, name=f'TVManagerMovieJob-{name}').start()
        return jsonify(ok=True, started=name)
