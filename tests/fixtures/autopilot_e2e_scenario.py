"""End-to-end Autopilot scenario: fake Newznab indexer + fake SABnzbd over real HTTP.
Run from a scratch app copy folder: python autopilot_e2e.py"""
import json, os, sys, threading, time
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.getcwd())
import logging; logging.disable(50)

SAB_QUEUE = {}      # nzo_id -> {"name":..., "status": "Downloading"/"Completed"/"Failed"}
SAB_ADDED = []
SEARCHES = []


class Indexer(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_GET(self):
        q = {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}
        if q.get("t") == "caps":
            body = '<caps><searching><search available="yes"/><tv-search available="yes" supportedParams="q,season,ep"/></searching><categories><category id="5000" name="TV"/></categories></caps>'
        else:
            SEARCHES.append(q)
            se = f"S{int(q.get('season', 1)):02d}E{int(q.get('ep', 1)):02d}" if q.get("ep") else ""
            items = []
            for tag, size in (("ALPHA", 2_000_000_000), ("BRAVO", 1_500_000_000)):
                title = f"Good.Show.{se}.1080p.WEB.h264-{tag}"
                items.append(f'<item><title>{title}</title><guid>guid-{se}-{tag}</guid><link>http://127.0.0.1:{PORT}/get/{se}-{tag}.nzb</link>'
                             f'<pubDate>Mon, 01 Jan 2024 00:00:00 +0000</pubDate><enclosure url="http://127.0.0.1:{PORT}/get/{se}-{tag}.nzb" length="{size}" type="application/x-nzb"/>'
                             f'<newznab:attr name="size" value="{size}"/><newznab:attr name="category" value="5040"/></item>')
            body = ('<?xml version="1.0"?><rss version="2.0" xmlns:newznab="http://www.newznab.com/DTD/2010/feeds/attributes/"><channel>'
                    + "".join(items) + "</channel></rss>")
        data = body.encode()
        self.send_response(200); self.send_header("Content-Type", "application/xml"); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)


class Sab(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_GET(self):
        q = {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}
        mode = q.get("mode")
        if mode == "addurl":
            nzo = f"SABnzbd_nzo_{len(SAB_ADDED) + 1}"
            SAB_ADDED.append(q.get("name"))
            SAB_QUEUE[nzo] = {"name": q.get("nzbname") or q.get("name"), "status": "Downloading"}
            out = {"status": True, "nzo_ids": [nzo]}
        elif mode == "history":
            out = {"history": {"slots": [{"nzo_id": k, "status": v["status"], "name": v["name"], "fail_message": "Unpacking failed" if v["status"] == "Failed" else ""}
                                         for k, v in SAB_QUEUE.items() if v["status"] in ("Completed", "Failed")]}}
        elif mode == "queue":
            out = {"queue": {"slots": [{"nzo_id": k, "status": v["status"], "filename": v["name"], "percentage": "10"} for k, v in SAB_QUEUE.items() if v["status"] == "Downloading"]}}
        elif mode == "version":
            out = {"version": "4.0.0"}
        else:
            out = {"status": True}
        data = json.dumps(out).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)


idx = ThreadingHTTPServer(("127.0.0.1", 0), Indexer); PORT = idx.server_address[1]
sab = ThreadingHTTPServer(("127.0.0.1", 0), Sab)
for srv in (idx, sab):
    threading.Thread(target=srv.serve_forever, daemon=True).start()

import app, engine, autopilot  # noqa: E402

today = date.today()
with engine.cx() as c:
    c.execute("INSERT INTO shows(id,name,location,season_folders,status) VALUES(1,'Good Show','/nowhere/Good Show',1,'Continuing')")
    rows = [(1, 1, "Pilot", (today - timedelta(days=30)).isoformat(), "Skipped"),
            (1, 2, "Second", (today - timedelta(days=23)).isoformat(), "Wanted"),
            (1, 3, "Third", (today + timedelta(days=5)).isoformat(), "Wanted"),
            (1, 4, "Fourth", (today - timedelta(days=9)).isoformat(), "Ignored")]
    for season, ep, name, air, status in rows:
        c.execute("INSERT INTO episodes(show_id,season,episode,name,airdate,status,monitored) VALUES(1,?,?,?,?,?,1)", (season, ep, name, air, status))
    c.commit()
engine.set_setting("Newznab", "newznab_data", f"Fake|http://127.0.0.1:{PORT}/|KEY|5000,5040|1|eponly|1|1|1")
engine.set_setting("General", "use_nzbs", "1")
engine.set_setting("General", "nzb_method", "sabnzbd")
engine.set_setting("SABnzbd", "sab_host", f"http://127.0.0.1:{sab.server_address[1]}/")
engine.set_setting("SABnzbd", "sab_apikey", "SABKEY")
engine.set_setting("TVManager", "simulation_mode", "0")
autopilot.save_settings({"max_attempts": 2, "postprocess": 0, "batch_size": 10})


def downloads():
    with engine.cx() as c:
        return [dict(r) for r in c.execute("SELECT d.id,d.status,d.external_id,d.release_name,e.episode FROM downloads d JOIN episodes e ON e.id=d.episode_id ORDER BY d.id")]


out = {}
r1 = autopilot.run_cycle()
out["run1"] = r1["steps"]["search"]; out["counts1"] = r1["counts"]; out["dl1"] = downloads(); out["sab1"] = list(SAB_ADDED)
first = [d for d in out["dl1"] if d["episode"] == 1][0]
SAB_QUEUE[first["external_id"]]["status"] = "Failed"
r2 = autopilot.run_cycle()
out["run2"] = {"failures": r2["steps"]["failures"], "search": r2["steps"]["search"]}; out["dl2"] = downloads()
with engine.cx() as c:
    c.execute("UPDATE downloads SET added_at=datetime('now','-13 hours') WHERE id=(SELECT d.id FROM downloads d JOIN episodes e ON e.id=d.episode_id WHERE e.episode=2 ORDER BY d.id LIMIT 1)")
    c.commit()
r3 = autopilot.run_cycle()
out["run3"] = {"failures": r3["steps"]["failures"], "search": r3["steps"]["search"]}; out["dl3"] = downloads()
second = [d for d in out["dl3"] if d["episode"] == 1][-1]
SAB_QUEUE[second["external_id"]]["status"] = "Failed"
r4 = autopilot.run_cycle()
out["run4"] = {"failures": r4["steps"]["failures"], "search": r4["steps"]["search"]}
out["status"] = {k: v for k, v in autopilot.status().items() if k in ("counts", "set_aside")}
with engine.cx() as c:
    out["blocked"] = [r[0] for r in c.execute("SELECT guid FROM failed_releases ORDER BY guid")]
    out["episodes"] = [dict(r) for r in c.execute("SELECT episode,status,last_search IS NOT NULL searched FROM episodes ORDER BY episode")]
out["searched_eps"] = sorted({q.get("ep") for q in SEARCHES if q.get("ep")})
out["retry"] = autopilot.retry(None)
out["after_retry_due"] = autopilot.eligible_episode_ids()
print(json.dumps(out, default=str))
