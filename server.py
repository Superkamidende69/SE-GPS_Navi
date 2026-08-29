#!/usr/bin/env python3
"""Local read-only API bridge for the Spatial Atlas web page.

Uses the same config file and environment variables as se_gps_navigator.py.
Run from this folder with: python server.py
"""
import json
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

try:
    import pymysql
    import pymysql.cursors
except ImportError as exc:
    raise SystemExit("Install the database driver first: pip install pymysql") from exc

PORT = 8765
ACTIVE_CONFIG = None
CONFIG_FILE = Path.home() / ".se_gps_navigator" / "db_config.json"
DEFAULT_CONFIG = {"host": "127.0.0.1", "port": 3306, "user": "se_gps", "password": "changeme", "database": "se_gps_navigator"}


def db_config():
    config = dict(DEFAULT_CONFIG)
    if CONFIG_FILE.exists():
        try:
            config.update(json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            pass
    config["host"] = os.environ.get("SE_GPS_DB_HOST", config["host"])
    config["port"] = int(os.environ.get("SE_GPS_DB_PORT", config["port"]))
    config["user"] = os.environ.get("SE_GPS_DB_USER", config["user"])
    config["password"] = os.environ.get("SE_GPS_DB_PASSWORD", config["password"])
    config["database"] = os.environ.get("SE_GPS_DB_NAME", config["database"])
    return config


def load_data():
    global ACTIVE_CONFIG
    if ACTIVE_CONFIG is None:
        ACTIVE_CONFIG = db_config()
    with pymysql.connect(**ACTIVE_CONFIG, autocommit=True, cursorclass=pymysql.cursors.DictCursor) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, x, y, z, ore_type, description, cluster_id, report_count, location_type FROM entries ORDER BY id")
            entries = list(cur.fetchall())
            cur.execute("SELECT id, name, center_x, center_y, center_z FROM clusters ORDER BY id")
            clusters = list(cur.fetchall())
    for entry in entries:
        entry["description"] = entry.get("description") or ""
        entry["ore_type"] = entry.get("ore_type") or "Unknown"
        entry["location_type"] = entry.get("location_type") or ""
        entry["cluster_name"] = next((c["name"] for c in clusters if c["id"] == entry.get("cluster_id")), "Unassigned")
    return {"entries": entries, "clusters": clusters}


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def do_GET(self):
        if self.path == "/api/data":
            try:
                payload = json.dumps(load_data(), default=str).encode("utf-8")
                self.send_response(200)
            except Exception as exc:
                payload = json.dumps({"error": str(exc)}).encode("utf-8")
                self.send_response(503)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        super().do_GET()

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        global ACTIVE_CONFIG
        if self.path not in ("/api/connect", "/api/update"):
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            incoming = json.loads(self.rfile.read(length).decode("utf-8"))
            if self.path == "/api/update":
                if ACTIVE_CONFIG is None:
                    raise RuntimeError("Connect to MySQL before saving edits")
                with pymysql.connect(**ACTIVE_CONFIG, autocommit=True, cursorclass=pymysql.cursors.DictCursor) as conn:
                    with conn.cursor() as cur:
                        cur.execute("UPDATE entries SET name=%s, x=%s, y=%s, z=%s, location_type=%s, description=%s WHERE id=%s", (incoming["name"], incoming["x"], incoming["y"], incoming["z"], incoming["location_type"], incoming.get("description", ""), incoming["id"]))
                payload, status = json.dumps({"ok": True}).encode("utf-8"), 200
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return
            config = {"host": incoming["host"], "port": int(incoming["port"]), "user": incoming["user"], "password": incoming.get("password", ""), "database": incoming["database"]}
            with pymysql.connect(**config, connect_timeout=8):
                pass
            ACTIVE_CONFIG = config
            payload, status = json.dumps({"ok": True}).encode("utf-8"), 200
        except Exception as exc:
            payload, status = json.dumps({"error": str(exc)}).encode("utf-8"), 400
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


if __name__ == "__main__":
    print(f"Spatial Atlas bridge: http://127.0.0.1:{PORT}")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
