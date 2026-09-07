"""Emergency support-route registration for TV Manager.

These routes are registered immediately after the Flask app is created so
support pages exist even if later template/static routing changes are broken.
They intentionally avoid relying on client-side JavaScript.
"""
from __future__ import annotations

from datetime import datetime


def register_support_routes(app, base_path, version_getter):
    """Register dependable support pages and route diagnostics."""
    def version():
        try:
            return version_getter() if callable(version_getter) else str(version_getter)
        except Exception:
            return "development"

    def shell(title, eyebrow, body, nav_current=""):
        v = version()
        def current(path):
            return ' aria-current="page"' if nav_current == path else ""
        return f'''<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} - TV Manager</title><link rel="stylesheet" href="/static/style.css"></head>
<body><main class="shell manager-shell">
<header class="topbar"><div><p class="eyebrow">{eyebrow}</p><h1>{title}</h1><p class="subtitle">TV Manager v{v}</p></div></header>
<nav class="appnav professional-nav">
<a href="/dashboard">Dashboard</a><a href="/manager">Shows</a><a href="/library-health"{current('/library-health')}>Library Health</a><a href="/about"{current('/about')}>About</a><a href="/routes"{current('/routes')}>Routes</a><a href="/system">System</a><a href="/import">Migration</a>
</nav>
{body}
<footer class="app-version-footer"><span>TV Manager</span><strong>v{v}</strong><a href="/about">About</a><a href="/routes">Routes</a></footer>
</main></body></html>'''

    def route_inventory():
        rows = []
        for rule in sorted(app.url_map.iter_rules(), key=lambda r: r.rule):
            methods = sorted(m for m in rule.methods if m not in {"HEAD", "OPTIONS"})
            rows.append({"path": rule.rule, "endpoint": rule.endpoint, "methods": methods})
        return rows

    def about():
        body = f'''
<section class="panel about-card"><p class="eyebrow">RUNNING BUILD</p><h2>TV Manager v{version()}</h2>
<div class="detail-grid"><div><span>Product</span><strong>TV Manager</strong></div><div><span>Version</span><strong>v{version()}</strong></div><div><span>Runtime</span><strong>Python / Flask</strong></div><div><span>Database</span><strong>SQLite local-first</strong></div></div>
<p class="notice good">About route is registered by support_routes.py.</p></section>
<section class="panel"><h2>Support links</h2><ul class="clean-list"><li><a href="/routes">Route Diagnostics</a></li><li><a href="/library-health">Library Health</a></li><li><a href="/api/version">Version API</a></li><li><a href="/api/about">About API</a></li></ul></section>'''
        return shell("About", "ABOUT", body, "/about")

    def library_health():
        body = f'''
<section class="panel"><h2>Library Health route verified</h2><p class="notice good">This page is being served by support_routes.py in TV Manager v{version()}.</p>
<p>Open the JSON report for live counts and warnings: <a class="btn secondary" href="/api/library/health-report">/api/library/health-report</a></p></section>
<section class="panel"><h2>Next checks</h2><ul class="clean-list"><li>Use <a href="/routes">Route Diagnostics</a> to confirm all registered routes.</li><li>Use <a href="/system">System</a> for diagnostics.</li><li>Use <a href="/import">Import Center</a> for SickChill migration.</li></ul></section>'''
        return shell("Library Health", "LIBRARY HEALTH", body, "/library-health")

    def routes_page():
        routes = route_inventory()
        required = ["/about", "/library-health", "/routes", "/api/version", "/api/about", "/api/routes"]
        present = {r["path"] for r in routes}
        checks = "".join(f"<li>{'OK' if p in present else 'MISSING'} <code>{p}</code></li>" for p in required)
        rows = "".join(f"<tr><td><code>{r['path']}</code></td><td>{','.join(r['methods'])}</td><td>{r['endpoint']}</td></tr>" for r in routes)
        body = f'''<section class="panel"><h2>Required support routes</h2><ul class="clean-list">{checks}</ul></section>
<section class="panel"><h2>Registered Flask routes</h2><table><thead><tr><th>Path</th><th>Methods</th><th>Endpoint</th></tr></thead><tbody>{rows}</tbody></table></section>'''
        return shell("Route Diagnostics", "DIAGNOSTICS", body, "/routes")

    def api_version():
        from flask import jsonify
        return jsonify(product="TV Manager", version=version(), build="v" + version(), route_source="support_routes.py")

    def api_about():
        from flask import jsonify
        return jsonify(product="TV Manager", version=version(), support_routes=True, generated_at=datetime.now().isoformat(timespec="seconds"), pages=["/about", "/library-health", "/routes"])

    def api_routes():
        from flask import jsonify
        routes = route_inventory()
        return jsonify(product="TV Manager", version=version(), routes=routes, count=len(routes))

    app.add_url_rule('/about', 'support_about', about, methods=['GET'])
    app.add_url_rule('/about/', 'support_about_slash', about, methods=['GET'])
    app.add_url_rule('/version', 'support_version_page', about, methods=['GET'])
    app.add_url_rule('/library-health', 'support_library_health', library_health, methods=['GET'])
    app.add_url_rule('/library-health/', 'support_library_health_slash', library_health, methods=['GET'])
    app.add_url_rule('/library_health', 'support_library_health_alt', library_health, methods=['GET'])
    app.add_url_rule('/health/library', 'support_library_health_alt2', library_health, methods=['GET'])
    app.add_url_rule('/routes', 'support_routes_page', routes_page, methods=['GET'])
    app.add_url_rule('/api/version', 'support_api_version', api_version, methods=['GET'])
    app.add_url_rule('/api/about', 'support_api_about', api_about, methods=['GET'])
    app.add_url_rule('/api/routes', 'support_api_routes', api_routes, methods=['GET'])
    return True
