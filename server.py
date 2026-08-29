#!/usr/bin/env python3
"""Local API bridge and access-control server for the Spatial Atlas web page.

Run from this folder with: python server.py
"""
import base64
import hashlib
import json
import os
import re
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

try:
    import pymysql
    import pymysql.cursors
except ImportError as exc:
    raise SystemExit("Install the database driver first: pip install pymysql") from exc

PORT = int(os.environ.get("SE_ATLAS_PORT", "8765"))
ACTIVE_CONFIG = None
CONFIG_FILE = Path.home() / ".se_gps_navigator" / "db_config.json"
ACCESS_DB = Path(os.environ.get("SE_ATLAS_ACCESS_DB", Path.home() / ".se_gps_navigator" / "atlas_access.sqlite3"))
DEFAULT_CONFIG = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "se_gps",
    "password": "changeme",
    "database": "se_gps_navigator",
}
USERNAME_RE = re.compile(r"^[A-Za-z0-9._-]{3,32}$")
ACCESS_LEVELS = ("user", "trusted", "council", "leader", "admin")
VALID_ROLES = set(ACCESS_LEVELS)
ACCESS_RANK = {level: index for index, level in enumerate(ACCESS_LEVELS)}
VISIBILITY_EDITOR_LEVELS = {"gps": "trusted", "cluster": "council", "region": "council"}
REGION_DISTANCE_METERS = 2_000_000
SESSION_DURATION = timedelta(days=7)


def now():
    return datetime.now(timezone.utc)


def now_text():
    return now().isoformat()


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


def access_connection():
    ACCESS_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(ACCESS_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE COLLATE NOCASE,
            display_name TEXT NOT NULL,
            role TEXT NOT NULL,
            access_level TEXT NOT NULL DEFAULT 'user',
            password_salt TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS sessions (
            token_hash TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS entity_visibility (
            entity_type TEXT NOT NULL CHECK(entity_type IN ('gps', 'cluster', 'region')),
            entity_key TEXT NOT NULL,
            visibility TEXT NOT NULL DEFAULT 'user',
            updated_by INTEGER,
            updated_at TEXT NOT NULL,
            PRIMARY KEY(entity_type, entity_key)
        )"""
    )
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
    if "access_level" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN access_level TEXT NOT NULL DEFAULT 'user'")
        conn.execute("UPDATE users SET access_level=CASE role WHEN 'viewer' THEN 'user' WHEN 'editor' THEN 'trusted' ELSE 'admin' END")
        conn.commit()
    return conn


def password_material(password):
    if not isinstance(password, str) or len(password) < 8:
        raise ValueError("Passwords must contain at least 8 characters")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 310000)
    return base64.b64encode(salt).decode("ascii"), base64.b64encode(digest).decode("ascii")


def verify_password(password, salt_text, digest_text):
    if not isinstance(password, str):
        return False
    salt = base64.b64decode(salt_text.encode("ascii"))
    actual = base64.b64decode(digest_text.encode("ascii"))
    expected = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 310000)
    return secrets.compare_digest(actual, expected)


def legacy_role_for(access_level):
    if access_level == "user":
        return "viewer"
    if access_level in {"trusted", "council"}:
        return "editor"
    return "admin"


def access_rank(level):
    return ACCESS_RANK.get(level, -1)


def validate_visibility(value):
    visibility = str(value or "user").strip().lower()
    if visibility not in VALID_ROLES:
        raise ValueError("Choose user, trusted, council, leader, or admin visibility")
    return visibility


def visibility_key(entity_type, entity_key):
    if entity_type not in VISIBILITY_EDITOR_LEVELS:
        raise ValueError("Unknown visibility target")
    if entity_type == "gps":
        try:
            return str(int(entity_key))
        except (TypeError, ValueError) as exc:
            raise ValueError("A GPS id is required") from exc
    key = str(entity_key or "").strip()
    if not key or len(key) > 2000:
        raise ValueError("A valid cluster or region key is required")
    return key


def checked_visibility(actor, entity_type, entity_key, visibility):
    entity_key = visibility_key(entity_type, entity_key)
    visibility = validate_visibility(visibility)
    required = VISIBILITY_EDITOR_LEVELS[entity_type]
    if access_rank(actor["role"]) < access_rank(required):
        raise PermissionError(f"{required.title()} access is required to change this visibility")
    if access_rank(visibility) > access_rank(actor["role"]):
        raise PermissionError("You cannot restrict visibility above your own access level")
    return entity_key, visibility


def save_visibility(actor, entity_type, entity_key, visibility):
    entity_key, visibility = checked_visibility(actor, entity_type, entity_key, visibility)
    with access_connection() as conn:
        conn.execute(
            """INSERT INTO entity_visibility (entity_type, entity_key, visibility, updated_by, updated_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(entity_type, entity_key) DO UPDATE SET
                 visibility=excluded.visibility, updated_by=excluded.updated_by, updated_at=excluded.updated_at""",
            (entity_type, entity_key, visibility, actor["id"], now_text()),
        )
    return visibility


def saved_visibility():
    with access_connection() as conn:
        rows = conn.execute("SELECT entity_type, entity_key, visibility FROM entity_visibility").fetchall()
    return {(row["entity_type"], row["entity_key"]): validate_visibility(row["visibility"]) for row in rows}


def region_keys(clusters):
    remaining = set(range(len(clusters)))
    keys = {}
    while remaining:
        seed = next(iter(remaining))
        queue = [seed]
        members = []
        remaining.remove(seed)
        while queue:
            current = queue.pop()
            members.append(current)
            current_cluster = clusters[current]
            for candidate in tuple(remaining):
                other = clusters[candidate]
                distance = ((float(current_cluster["center_x"]) - float(other["center_x"])) ** 2 + (float(current_cluster["center_y"]) - float(other["center_y"])) ** 2 + (float(current_cluster["center_z"]) - float(other["center_z"])) ** 2) ** .5
                if distance <= REGION_DISTANCE_METERS:
                    remaining.remove(candidate)
                    queue.append(candidate)
        key = json.dumps(sorted(str(clusters[index]["name"]) for index in members), separators=(",", ":"))
        for index in members:
            keys[clusters[index]["id"]] = key
    return keys


def validate_user_fields(incoming, creating=False):
    username = str(incoming.get("username", "")).strip()
    display_name = str(incoming.get("display_name", "")).strip()
    role = str(incoming.get("role", "user")).strip().lower()
    if creating or "username" in incoming:
        if not USERNAME_RE.fullmatch(username):
            raise ValueError("Username must be 3–32 letters, numbers, dots, dashes, or underscores")
    if creating or "display_name" in incoming:
        if not display_name or len(display_name) > 48:
            raise ValueError("Display name must be between 1 and 48 characters")
    if creating or "role" in incoming:
        if role not in VALID_ROLES:
            raise ValueError("Choose user, trusted, council, leader, or admin access")
    return username, display_name, role


def public_user(row):
    return {
        "id": row["id"],
        "username": row["username"],
        "display_name": row["display_name"],
        "role": row["access_level"],
        "is_active": bool(row["is_active"]),
        "created_at": row["created_at"],
    }


def user_count():
    with access_connection() as conn:
        return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]


def create_session(conn, user_id):
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (now_text(),))
    conn.execute(
        "INSERT INTO sessions (token_hash, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
        (token_hash, user_id, (now() + SESSION_DURATION).isoformat(), now_text()),
    )
    return token


def token_user(headers):
    authorization = headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        return None
    token_hash = hashlib.sha256(authorization[7:].strip().encode("utf-8")).hexdigest()
    with access_connection() as conn:
        row = conn.execute(
            """SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id
               WHERE s.token_hash=? AND s.expires_at>? AND u.is_active=1""",
            (token_hash, now_text()),
        ).fetchone()
    return public_user(row) if row else None


def load_data(user):
    global ACTIVE_CONFIG
    if ACTIVE_CONFIG is None:
        ACTIVE_CONFIG = db_config()
    with pymysql.connect(**ACTIVE_CONFIG, autocommit=True, cursorclass=pymysql.cursors.DictCursor) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, x, y, z, ore_type, description, cluster_id, report_count, location_type FROM entries ORDER BY id")
            entries = list(cur.fetchall())
            cur.execute("SELECT id, name, center_x, center_y, center_z FROM clusters ORDER BY id")
            clusters = list(cur.fetchall())
    visibility = saved_visibility()
    cluster_by_id = {cluster["id"]: cluster for cluster in clusters}
    cluster_regions = region_keys(clusters)
    user_rank = access_rank(user["role"])
    visible_entries = []
    for entry in entries:
        entry["description"] = entry.get("description") or ""
        entry["ore_type"] = entry.get("ore_type") or "Unknown"
        entry["location_type"] = entry.get("location_type") or ""
        cluster = cluster_by_id.get(entry.get("cluster_id"))
        entry["cluster_name"] = cluster["name"] if cluster else "Unassigned"
        region_key = cluster_regions.get(entry.get("cluster_id"), "")
        gps_visibility = visibility.get(("gps", str(entry["id"])), "user")
        cluster_visibility = visibility.get(("cluster", entry["cluster_name"]), "user")
        region_visibility = visibility.get(("region", region_key), "user")
        if user_rank < max(access_rank(gps_visibility), access_rank(cluster_visibility), access_rank(region_visibility)):
            continue
        entry["visibility"] = gps_visibility
        visible_entries.append(entry)
    visible_cluster_ids = {entry.get("cluster_id") for entry in visible_entries if entry.get("cluster_id") in cluster_by_id}
    visible_clusters = []
    for cluster in clusters:
        if cluster["id"] not in visible_cluster_ids:
            continue
        region_key = cluster_regions.get(cluster["id"], "")
        cluster["visibility"] = visibility.get(("cluster", cluster["name"]), "user")
        cluster["region_key"] = region_key
        cluster["region_visibility"] = visibility.get(("region", region_key), "user")
        visible_clusters.append(cluster)
    return {"entries": visible_entries, "clusters": visible_clusters}


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def send_json(self, payload, status=200):
        encoded = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def require_user(self, roles=None):
        user = token_user(self.headers)
        if not user:
            self.send_json({"error": "Sign in required"}, 401)
            return None
        if roles and user["role"] not in roles:
            self.send_json({"error": "You do not have permission for this action"}, 403)
            return None
        return user

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/auth/session":
            user = token_user(self.headers)
            self.send_json({"setup_required": user_count() == 0, "user": user}, 200 if user or user_count() == 0 else 401)
            return
        if path == "/api/users":
            if not self.require_user({"admin"}):
                return
            with access_connection() as conn:
                users = [public_user(row) for row in conn.execute("SELECT * FROM users ORDER BY is_active DESC, display_name COLLATE NOCASE, username COLLATE NOCASE")]
            self.send_json({"users": users})
            return
        if path == "/api/data":
            user = self.require_user()
            if not user:
                return
            try:
                self.send_json(load_data(user))
            except Exception as exc:
                self.send_json({"error": str(exc)}, 503)
            return
        super().do_GET()

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_POST(self):
        global ACTIVE_CONFIG
        path = urlparse(self.path).path
        try:
            incoming = self.read_json()
            if path == "/api/auth/setup":
                with access_connection() as conn:
                    if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]:
                        raise PermissionError("An administrator has already been set up")
                    username, display_name, _ = validate_user_fields(incoming, creating=True)
                    salt, digest = password_material(incoming.get("password"))
                    cur = conn.execute(
                        "INSERT INTO users (username, display_name, role, access_level, password_salt, password_hash, is_active, created_at, updated_at) VALUES (?, ?, 'admin', 'admin', ?, ?, 1, ?, ?)",
                        (username, display_name, salt, digest, now_text(), now_text()),
                    )
                    row = conn.execute("SELECT * FROM users WHERE id=?", (cur.lastrowid,)).fetchone()
                    token = create_session(conn, row["id"])
                self.send_json({"ok": True, "token": token, "user": public_user(row)}, 201)
                return
            if path == "/api/auth/login":
                username = str(incoming.get("username", "")).strip()
                with access_connection() as conn:
                    row = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
                    if not row or not row["is_active"] or not verify_password(incoming.get("password"), row["password_salt"], row["password_hash"]):
                        raise PermissionError("Invalid username or password")
                    token = create_session(conn, row["id"])
                self.send_json({"ok": True, "token": token, "user": public_user(row)})
                return
            if path == "/api/auth/logout":
                authorization = self.headers.get("Authorization", "")
                if authorization.startswith("Bearer "):
                    token_hash = hashlib.sha256(authorization[7:].strip().encode("utf-8")).hexdigest()
                    with access_connection() as conn:
                        conn.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash,))
                self.send_json({"ok": True})
                return
            if path == "/api/users":
                if not self.require_user({"admin"}):
                    return
                username, display_name, role = validate_user_fields(incoming, creating=True)
                salt, digest = password_material(incoming.get("password"))
                with access_connection() as conn:
                    cur = conn.execute(
                        "INSERT INTO users (username, display_name, role, access_level, password_salt, password_hash, is_active, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)",
                        (username, display_name, legacy_role_for(role), role, salt, digest, now_text(), now_text()),
                    )
                    row = conn.execute("SELECT * FROM users WHERE id=?", (cur.lastrowid,)).fetchone()
                self.send_json({"ok": True, "user": public_user(row)}, 201)
                return
            if path == "/api/visibility":
                actor = self.require_user()
                if not actor:
                    return
                visibility = save_visibility(actor, str(incoming.get("entity_type", "")), incoming.get("entity_key"), incoming.get("visibility"))
                self.send_json({"ok": True, "visibility": visibility})
                return
            if path == "/api/update":
                actor = self.require_user({"trusted", "council", "leader", "admin"})
                if not actor:
                    return
                if "visibility" in incoming:
                    checked_visibility(actor, "gps", incoming["id"], incoming["visibility"])
                if ACTIVE_CONFIG is None:
                    raise RuntimeError("Connect to MySQL before saving edits")
                with pymysql.connect(**ACTIVE_CONFIG, autocommit=True, cursorclass=pymysql.cursors.DictCursor) as conn:
                    with conn.cursor() as cur:
                        cur.execute("UPDATE entries SET name=%s, x=%s, y=%s, z=%s, location_type=%s, description=%s WHERE id=%s", (incoming["name"], incoming["x"], incoming["y"], incoming["z"], incoming["location_type"], incoming.get("description", ""), incoming["id"]))
                if "visibility" in incoming:
                    save_visibility(actor, "gps", incoming["id"], incoming["visibility"])
                self.send_json({"ok": True})
                return
            if path == "/api/connect":
                if not self.require_user({"leader", "admin"}):
                    return
                config = {"host": incoming["host"], "port": int(incoming["port"]), "user": incoming["user"], "password": incoming.get("password", ""), "database": incoming["database"]}
                with pymysql.connect(**config, connect_timeout=8):
                    pass
                ACTIVE_CONFIG = config
                self.send_json({"ok": True})
                return
            self.send_error(404)
        except PermissionError as exc:
            self.send_json({"error": str(exc)}, 403)
        except sqlite3.IntegrityError:
            self.send_json({"error": "That username is already in use"}, 400)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            self.send_json({"error": str(exc)}, 400)
        except Exception as exc:
            self.send_json({"error": str(exc)}, 400)

    def do_PATCH(self):
        path = urlparse(self.path).path
        match = re.fullmatch(r"/api/users/(\d+)", path)
        if not match:
            self.send_error(404)
            return
        actor = self.require_user({"admin"})
        if not actor:
            return
        try:
            incoming = self.read_json()
            user_id = int(match.group(1))
            with access_connection() as conn:
                target = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
                if not target:
                    raise ValueError("User not found")
                username, display_name, role = target["username"], target["display_name"], target["access_level"]
                if any(field in incoming for field in ("username", "display_name", "role")):
                    new_username, new_display_name, new_role = validate_user_fields(incoming)
                    if "username" in incoming:
                        username = new_username
                    if "display_name" in incoming:
                        display_name = new_display_name
                    if "role" in incoming:
                        role = new_role
                is_active = bool(incoming.get("is_active", target["is_active"]))
                removing_admin = target["access_level"] == "admin" and (role != "admin" or not is_active)
                active_admins = conn.execute("SELECT COUNT(*) FROM users WHERE access_level='admin' AND is_active=1").fetchone()[0]
                if removing_admin and active_admins <= 1:
                    raise ValueError("Keep at least one active administrator")
                if target["id"] == actor["id"] and (role != "admin" or not is_active):
                    raise ValueError("You cannot remove your own administrator access")
                values = [username, display_name, legacy_role_for(role), role, int(is_active), now_text()]
                query = "UPDATE users SET username=?, display_name=?, role=?, access_level=?, is_active=?, updated_at=?"
                if incoming.get("password"):
                    salt, digest = password_material(incoming["password"])
                    query += ", password_salt=?, password_hash=?"
                    values.extend([salt, digest])
                query += " WHERE id=?"
                values.append(user_id)
                conn.execute(query, values)
                row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
            self.send_json({"ok": True, "user": public_user(row)})
        except sqlite3.IntegrityError:
            self.send_json({"error": "That username is already in use"}, 400)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            self.send_json({"error": str(exc)}, 400)

    def do_DELETE(self):
        path = urlparse(self.path).path
        match = re.fullmatch(r"/api/users/(\d+)", path)
        if not match:
            self.send_error(404)
            return
        actor = self.require_user({"admin"})
        if not actor:
            return
        try:
            user_id = int(match.group(1))
            with access_connection() as conn:
                target = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
                if not target:
                    raise ValueError("User not found")
                if target["id"] == actor["id"]:
                    raise ValueError("You cannot delete your own account")
                active_admins = conn.execute("SELECT COUNT(*) FROM users WHERE access_level='admin' AND is_active=1").fetchone()[0]
                if target["access_level"] == "admin" and target["is_active"] and active_admins <= 1:
                    raise ValueError("Keep at least one active administrator")
                conn.execute("DELETE FROM users WHERE id=?", (user_id,))
            self.send_json({"ok": True})
        except ValueError as exc:
            self.send_json({"error": str(exc)}, 400)


if __name__ == "__main__":
    print(f"Spatial Atlas bridge: http://127.0.0.1:{PORT}")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
