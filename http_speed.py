"""Response compression and browser caching (v18.23.0).

* Text responses (HTML, JSON, CSS, JavaScript) over 1 KB are gzip-compressed when the browser
  accepts it. Show lists and the Missing page are several hundred KB of JSON; compressed they
  are roughly a tenth of that.
* Static files requested with ?v=<version> (every page links them that way) are cached by the
  browser for a year: a new release changes the version and so the address. Other static files
  are cached for an hour.
"""
from __future__ import annotations

import gzip

from flask import request

COMPRESSIBLE = ("text/", "application/json", "application/javascript", "image/svg+xml", "application/xml")
MIN_BYTES = 1024
MAX_BYTES = 8 * 1024 * 1024


def init(app):
    def _max_age(filename):
        return 31536000 if request.args.get("v") else 3600

    app.get_send_file_max_age = _max_age  # used by Flask's static file route

    @app.after_request
    def _cache_and_compress(response):
        if request.path.startswith("/static/") and request.args.get("v") and response.status_code == 200:
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return compress(response)

    return app


def compress(response):
    if response.status_code != 200 or "Content-Encoding" in response.headers:
        return response
    if response.is_streamed and not response.direct_passthrough:
        return response  # generated streams (progress feeds, downloads) are left alone
    if "gzip" not in (request.headers.get("Accept-Encoding") or "").lower():
        return response
    mimetype = response.mimetype or ""
    if not mimetype.startswith(COMPRESSIBLE):
        return response
    if response.direct_passthrough:
        # Static files are sent as a file stream; read small text files so they can be compressed.
        length = response.content_length
        if length is None or length > MAX_BYTES:
            return response
        response.direct_passthrough = False
    data = response.get_data()
    if len(data) < MIN_BYTES or len(data) > MAX_BYTES:
        return response
    packed = gzip.compress(data, compresslevel=5)
    if len(packed) >= len(data):
        return response
    response.set_data(packed)
    response.headers["Content-Encoding"] = "gzip"
    response.headers["Content-Length"] = str(len(packed))
    vary = response.headers.get("Vary")
    response.headers["Vary"] = "Accept-Encoding" if not vary else (vary if "accept-encoding" in vary.lower() else vary + ", Accept-Encoding")
    # A compressed body is not byte-range addressable.
    response.headers.pop("Accept-Ranges", None)
    return response
