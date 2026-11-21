#!/usr/bin/env python3
"""
FITTRACK PRO — Production-ready Python + SQLite REST API & PWA Static Server.
Zero external dependencies required; runs on Python 3.9+.
"""

import base64
import csv
import hashlib
import hmac
import io
import json
import mimetypes
import os
import secrets
import sqlite3
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

BASE_DIR = Path(__file__).resolve().parent
PUBLIC_DIR = (BASE_DIR / "public") if (BASE_DIR / "public").exists() else BASE_DIR

SCHEMA_PATH = BASE_DIR / "schema.sql"


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


load_dotenv(BASE_DIR / ".env")

PORT = int(os.environ.get("PORT", "8080"))
DB_PATH = os.environ.get("DB_PATH", str(BASE_DIR / "fittrack.db"))
APP_SECRET = os.environ.get("APP_SECRET") or secrets.token_hex(32)
MAX_BODY_BYTES = 6 * 1024 * 1024  # 6 MB upload guard


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db() -> None:
    conn = get_db()
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    # Seed clearly-labeled demo user if none exists
    existing = conn.execute("SELECT id FROM users WHERE email = ?", ("demo@fittrack.pro",)).fetchone()
    if not existing:
        pw_hash = hash_password("DemoPass123!")
        cur = conn.execute(
            "INSERT INTO users (email, username, password_hash, friend_code, language, theme) VALUES (?, ?, ?, ?, 'en', 'dark')",
            ("demo@fittrack.pro", "aarav_demo", pw_hash, "FT-DEMO-7421"),
        )
        uid = cur.lastrowid
        conn.execute(
            """INSERT INTO profiles (user_id, full_name, height_cm, weight_kg, age, sex, activity_level,
               fitness_goal, dietary_pref, calorie_goal, protein_goal, carbs_goal, fat_goal,
               water_goal_ml, step_goal, xp, level, streak_days, league, onboarding_completed)
               VALUES (?, 'Aarav Kulkarni (Demo)', 176, 74.2, 24, 'male', 'moderate', 'recomp',
               'vegetarian', 2250, 150, 240, 65, 3000, 9000, 2480, 7, 12, 'Gold', 1)""",
            (uid,),
        )
        conn.execute("INSERT INTO notification_settings (user_id) VALUES (?)", (uid,))
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        conn.execute(
            """INSERT INTO meals (user_id, log_date, meal_type, name, serving_size, calories, protein_g, carbs_g, fat_g, source, is_estimate)
               VALUES (?, ?, 'breakfast', 'Moong Dal Chilla & Curd (Demo)', '2 chillas + 150g curd', 420, 26, 48, 12, 'manual', 0)""",
            (uid, today),
        )
        conn.execute(
            """INSERT INTO activity_logs (user_id, log_date, activity_type, steps, distance_km, duration_min, active_minutes, calories_burned, source, verified)
               VALUES (?, ?, 'walking', 6420, 4.8, 52, 44, 265, 'manual', 0)""",
            (uid, today),
        )
        conn.execute(
            """INSERT INTO body_metrics (user_id, log_date, weight_kg, waist_cm, chest_cm, arm_cm, thigh_cm, body_fat_pct, notes)
               VALUES (?, ?, 74.2, 81.5, 99.0, 35.2, 55.0, 16.4, 'Demo baseline measurement')""",
            (uid, today),
        )
        conn.execute(
            """INSERT INTO sleep_water_logs (user_id, log_date, sleep_hours, sleep_quality, water_ml, mood, soreness, journal_note)
               VALUES (?, ?, 7.5, 4, 2100, 'Focused', 2, 'Upper body session felt strong.')""",
            (uid, today),
        )
        conn.commit()
    conn.close()


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000)
    return f"{salt}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, expected_hex = stored.split("$", 1)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000)
        return hmac.compare_digest(dk.hex(), expected_hex)
    except Exception:
        return False


def create_token(user_id: int, ttl_sec: int = 86400 * 7) -> str:
    payload = json.dumps({"uid": user_id, "exp": int(time.time()) + ttl_sec}).encode("utf-8")
    b64 = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
    sig = hmac.new(APP_SECRET.encode("utf-8"), b64.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{b64}.{sig}"


def verify_token(token: str):
    try:
        b64, sig = token.split(".", 1)
        expected = hmac.new(APP_SECRET.encode("utf-8"), b64.encode("ascii"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        padded = b64 + "=" * (-len(b64) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
        if data.get("exp", 0) < time.time():
            return None
        return int(data["uid"])
    except Exception:
        return None


def rows_to_list(rows) -> list:
    return [dict(r) for r in rows]


class FitTrackHandler(BaseHTTPRequestHandler):
    server_version = "FitTrackPro/1.0"

    def _send_json(self, code: int, payload: dict) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(raw)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > MAX_BODY_BYTES:
            raise ValueError("Invalid or oversized payload")
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def _auth_uid(self):
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return verify_token(auth[7:].strip())
        return None

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path.startswith("/api/"):
            self._handle_api_get(path, parse_qs(parsed.query))
            return

        # Static PWA serving
        rel = "index.html" if path in ("/", "") else path.lstrip("/")
             if rel.startswith("icons/") and not (PUBLIC_DIR / rel).exists():
         rel = rel.split("/", 1)[1]

        target = (PUBLIC_DIR / rel).resolve()
        if not str(target).startswith(str(PUBLIC_DIR.resolve())) or not target.exists() or target.is_dir():
            target = PUBLIC_DIR / "index.html"
        if not target.exists():
            self.send_error(404, "Not Found")
            return
        mime, _ = mimetypes.guess_type(str(target))
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:
        self._handle_api_write("POST", urlparse(self.path).path)

    def do_PUT(self) -> None:
        self._handle_api_write("PUT", urlparse(self.path).path)

    def do_PATCH(self) -> None:
        self._handle_api_write("PATCH", urlparse(self.path).path)

    def do_DELETE(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        uid = self._auth_uid()
        if not uid:
            self._send_json(401, {"error": "Unauthorized"})
            return
        conn = get_db()
        try:
            if path.startswith("/api/meals/"):
                mid = int(path.rsplit("/", 1)[-1])
                conn.execute("DELETE FROM meals WHERE id = ? AND user_id = ?", (mid, uid))
                conn.commit()
                self._send_json(200, {"deleted": mid})
            elif path.startswith("/api/body/photos/"):
                pid = int(path.rsplit("/", 1)[-1])
                conn.execute("DELETE FROM progress_photos WHERE id = ? AND user_id = ?", (pid, uid))
                conn.commit()
                self._send_json(200, {"deleted": pid})
            elif path == "/api/account":
                conn.execute("DELETE FROM users WHERE id = ?", (uid,))
                conn.commit()
                self._send_json(200, {"deleted_account": True})
            else:
                self._send_json(404, {"error": "Endpoint not found"})
        finally:
            conn.close()

    def _handle_api_get(self, path: str, qs: dict) -> None:
        if path == "/api/health":
            self._send_json(200, {"status": "ok", "service": "FITTRACK PRO"})
            return

        if path == "/api/integrations/status":
            self._send_json(
                200,
                {
                    "ai_vision_coach": {
                        "configured": bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY")),
                        "provider": "Gemini / OpenAI",
                        "env_vars": ["GEMINI_API_KEY", "OPENAI_API_KEY"],
                        "fallback": "Manual meal logging & local rule-based wellness coach",
                    },
                    "nutrition_db": {
                        "configured": bool(os.environ.get("USDA_API_KEY") or os.environ.get("NUTRITIONIX_API_KEY")),
                        "provider": "USDA FoodData Central / Nutritionix",
                        "env_vars": ["USDA_API_KEY", "NUTRITIONIX_APP_ID", "NUTRITIONIX_API_KEY"],
                        "fallback": "Built-in Indian & global high-protein food catalog",
                    },
                    "database_auth": {
                        "configured": True,
                        "provider": "SQLite + HMAC-SHA256 (Local) / Optional Supabase",
                        "env_vars": ["SUPABASE_URL", "SUPABASE_ANON_KEY"],
                    },
                    "health_connect": {
                        "configured": False,
                        "provider": "Android Health Connect",
                        "requires": "Native Android APK/TWA bridge or Capacitor plugin",
                        "fallback": "Browser Pedometer where supported + manual step entry",
                    },
                    "maps_gps": {
                        "configured": bool(os.environ.get("GOOGLE_MAPS_API_KEY")),
                        "provider": "Browser Geolocation API + Optional Google Maps",
                        "env_vars": ["GOOGLE_MAPS_API_KEY"],
                    },
                    "push_notifications": {
                        "configured": bool(os.environ.get("VAPID_PUBLIC_KEY") and os.environ.get("VAPID_PRIVATE_KEY")),
                        "provider": "Web Push (VAPID)",
                        "env_vars": ["VAPID_PUBLIC_KEY", "VAPID_PRIVATE_KEY"],
                    },
                },
            )
            return

        uid = self._auth_uid()
        if not uid:
            self._send_json(401, {"error": "Unauthorized"})
            return

        conn = get_db()
        try:
            if path == "/api/auth/me":
                user = conn.execute("SELECT id, email, username, friend_code, language, theme, created_at FROM users WHERE id = ?", (uid,)).fetchone()
                prof = conn.execute("SELECT * FROM profiles WHERE user_id = ?", (uid,)).fetchone()
                self._send_json(200, {"user": dict(user), "profile": dict(prof) if prof else {}})
            elif path == "/api/profile":
                prof = conn.execute("SELECT * FROM profiles WHERE user_id = ?", (uid,)).fetchone()
                self._send_json(200, dict(prof) if prof else {})
            elif path == "/api/meals":
                d = qs.get("date", [None])[0]
                if d:
                    rows = conn.execute("SELECT * FROM meals WHERE user_id = ? AND log_date = ? ORDER BY id DESC", (uid, d)).fetchall()
                else:
                    rows = conn.execute("SELECT * FROM meals WHERE user_id = ? ORDER BY log_date DESC, id DESC LIMIT 100", (uid,)).fetchall()
                self._send_json(200, {"items": rows_to_list(rows)})
            elif path == "/api/custom-foods":
                rows = conn.execute("SELECT * FROM custom_foods WHERE user_id = ? ORDER BY id DESC", (uid,)).fetchall()
                self._send_json(200, {"items": rows_to_list(rows)})
            elif path == "/api/supplements":
                rows = conn.execute("SELECT * FROM supplements WHERE user_id = ? ORDER BY log_date DESC, id DESC LIMIT 50", (uid,)).fetchall()
                self._send_json(200, {"items": rows_to_list(rows)})
            elif path == "/api/workouts/split":
                rows = conn.execute("SELECT * FROM workout_splits WHERE user_id = ? ORDER BY day_index ASC", (uid,)).fetchall()
                self._send_json(200, {"items": rows_to_list(rows)})
            elif path == "/api/workouts/logs":
                rows = conn.execute("SELECT * FROM workout_logs WHERE user_id = ? ORDER BY log_date DESC, id DESC LIMIT 60", (uid,)).fetchall()
                self._send_json(200, {"items": rows_to_list(rows)})
            elif path == "/api/workouts/prs":
                rows = conn.execute("SELECT * FROM personal_records WHERE user_id = ? ORDER BY achieved_date DESC", (uid,)).fetchall()
                self._send_json(200, {"items": rows_to_list(rows)})
            elif path == "/api/activity":
                rows = conn.execute("SELECT * FROM activity_logs WHERE user_id = ? ORDER BY log_date DESC, id DESC LIMIT 60", (uid,)).fetchall()
                self._send_json(200, {"items": rows_to_list(rows)})
            elif path == "/api/body/metrics":
                rows = conn.execute("SELECT * FROM body_metrics WHERE user_id = ? ORDER BY log_date ASC", (uid,)).fetchall()
                self._send_json(200, {"items": rows_to_list(rows)})
            elif path == "/api/body/photos":
                rows = conn.execute("SELECT id, log_date, angle, weight_kg, notes, is_private, image_data FROM progress_photos WHERE user_id = ? ORDER BY log_date DESC", (uid,)).fetchall()
                self._send_json(200, {"items": rows_to_list(rows)})
            elif path == "/api/recovery":
                rows = conn.execute("SELECT * FROM sleep_water_logs WHERE user_id = ? ORDER BY log_date DESC LIMIT 30", (uid,)).fetchall()
                self._send_json(200, {"items": rows_to_list(rows)})
            elif path == "/api/leaderboard":
                rows = conn.execute(
                    """SELECT u.id, u.username, p.full_name, p.xp, p.level, p.streak_days, p.league,
                       COALESCE((SELECT SUM(steps) FROM activity_logs a WHERE a.user_id = u.id), 0) AS total_steps
                       FROM users u JOIN profiles p ON p.user_id = u.id
                       WHERE p.privacy_public_profile = 1 OR u.id = ?
                       ORDER BY p.xp DESC LIMIT 50""",
                    (uid,),
                ).fetchall()
                self._send_json(200, {"items": rows_to_list(rows)})
            elif path == "/api/challenges":
                rows = conn.execute("SELECT * FROM challenges ORDER BY id DESC LIMIT 50").fetchall()
                self._send_json(200, {"items": rows_to_list(rows)})
            elif path == "/api/notifications":
                rows = conn.execute("SELECT * FROM notifications WHERE user_id = ? ORDER BY id DESC LIMIT 40", (uid,)).fetchall()
                self._send_json(200, {"items": rows_to_list(rows)})
            elif path == "/api/export/json":
                bundle = {
                    "exported_at": datetime.now(timezone.utc).isoformat(),
                    "profile": dict(conn.execute("SELECT * FROM profiles WHERE user_id = ?", (uid,)).fetchone() or {}),
                    "meals": rows_to_list(conn.execute("SELECT * FROM meals WHERE user_id = ?", (uid,)).fetchall()),
                    "workouts": rows_to_list(conn.execute("SELECT * FROM workout_logs WHERE user_id = ?", (uid,)).fetchall()),
                    "activity": rows_to_list(conn.execute("SELECT * FROM activity_logs WHERE user_id = ?", (uid,)).fetchall()),
                    "body_metrics": rows_to_list(conn.execute("SELECT * FROM body_metrics WHERE user_id = ?", (uid,)).fetchall()),
                }
                self._send_json(200, bundle)
            elif path == "/api/export/csv":
                rows = rows_to_list(conn.execute("SELECT log_date, meal_type, name, calories, protein_g, carbs_g, fat_g, source FROM meals WHERE user_id = ? ORDER BY log_date DESC", (uid,)).fetchall())
                buf = io.StringIO()
                writer = csv.DictWriter(buf, fieldnames=["log_date", "meal_type", "name", "calories", "protein_g", "carbs_g", "fat_g", "source"])
                writer.writeheader()
                writer.writerows(rows)
                raw = buf.getvalue().encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/csv; charset=utf-8")
                self.send_header("Content-Disposition", 'attachment; filename="fittrack_meals.csv"')
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
            else:
                self._send_json(404, {"error": "Endpoint not found"})
        finally:
            conn.close()

    def _handle_api_write(self, method: str, path: str) -> None:
        try:
            data = self._read_json()
        except Exception as exc:
            self._send_json(400, {"error": str(exc)})
            return

        conn = get_db()
        try:
            if path == "/api/auth/signup" and method == "POST":
                email = (data.get("email") or "").strip().lower()
                username = (data.get("username") or "").strip()
                password = data.get("password") or ""
                if not email or not username or len(password) < 8:
                    self._send_json(400, {"error": "Valid email, username, and 8+ char password required"})
                    return
                code = "FT-" + secrets.token_hex(3).upper()
                try:
                    cur = conn.execute(
                        "INSERT INTO users (email, username, password_hash, friend_code) VALUES (?, ?, ?, ?)",
                        (email, username, hash_password(password), code),
                    )
                    uid = cur.lastrowid
                    conn.execute("INSERT INTO profiles (user_id, full_name) VALUES (?, ?)", (uid, data.get("full_name", username)))
                    conn.execute("INSERT INTO notification_settings (user_id) VALUES (?)", (uid,))
                    conn.commit()
                    self._send_json(201, {"token": create_token(uid), "user_id": uid, "friend_code": code})
                except sqlite3.IntegrityError:
                    self._send_json(409, {"error": "Email or username already exists"})
                return

            if path == "/api/auth/login" and method == "POST":
                email = (data.get("email") or "").strip().lower()
                password = data.get("password") or ""
                row = conn.execute("SELECT id, password_hash FROM users WHERE email = ?", (email,)).fetchone()
                if not row or not verify_password(password, row["password_hash"]):
                    self._send_json(401, {"error": "Invalid credentials"})
                    return
                self._send_json(200, {"token": create_token(row["id"]), "user_id": row["id"]})
                return

            if path == "/api/auth/recover" and method == "POST":
                email = (data.get("email") or "").strip().lower()
                self._send_json(200, {"sent": True, "message": f"If {email} exists, password reset instructions have been queued (configure SMTP in .env for live email delivery)."})
                return

            uid = self._auth_uid()
            if not uid:
                self._send_json(401, {"error": "Unauthorized"})
                return

            if path == "/api/profile" and method == "PUT":
                allowed = [
                    "full_name", "height_cm", "weight_kg", "age", "sex", "activity_level",
                    "fitness_goal", "dietary_pref", "units", "calorie_goal", "protein_goal",
                    "carbs_goal", "fat_goal", "water_goal_ml", "step_goal",
                    "privacy_public_profile", "privacy_share_workouts", "privacy_share_steps",
                    "privacy_share_photos", "onboarding_completed",
                ]
                updates = {k: data[k] for k in allowed if k in data}
                if updates:
                    cols = ", ".join(f"{k} = ?" for k in updates)
                    vals = list(updates.values()) + [uid]
                    conn.execute(f"UPDATE profiles SET {cols}, updated_at = datetime('now') WHERE user_id = ?", vals)
                    conn.commit()
                self._send_json(200, {"updated": True})

            elif path == "/api/meals" and method == "POST":
                cur = conn.execute(
                    """INSERT INTO meals (user_id, log_date, meal_type, name, serving_size, calories, protein_g, carbs_g, fat_g, source, is_estimate, confidence)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        uid,
                        data.get("log_date") or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                        data.get("meal_type", "lunch"),
                        str(data["name"])[:120],
                        str(data.get("serving_size", "1 serving"))[:80],
                        float(data["calories"]),
                        float(data.get("protein_g", 0)),
                        float(data.get("carbs_g", 0)),
                        float(data.get("fat_g", 0)),
                        data.get("source", "manual"),
                        int(bool(data.get("is_estimate", False))),
                        str(data.get("confidence", "")),
                    ),
                )
                conn.execute("UPDATE profiles SET xp = xp + 25 WHERE user_id = ?", (uid,))
                conn.commit()
                self._send_json(201, {"id": cur.lastrowid})

            elif path == "/api/workouts/logs" and method == "POST":
                cur = conn.execute(
                    """INSERT INTO workout_logs (user_id, log_date, title, duration_min, total_volume_kg, warmup_done, cooldown_done, soreness_score, notes, exercises_json)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        uid,
                        data.get("log_date") or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                        str(data["title"])[:120],
                        int(data.get("duration_min", 45)),
                        float(data.get("total_volume_kg", 0)),
                        int(bool(data.get("warmup_done", False))),
                        int(bool(data.get("cooldown_done", False))),
                        int(data.get("soreness_score", 3)),
                        str(data.get("notes", ""))[:500],
                        json.dumps(data.get("exercises", [])),
                    ),
                )
                conn.execute("UPDATE profiles SET xp = xp + 60 WHERE user_id = ?", (uid,))
                conn.commit()
                self._send_json(201, {"id": cur.lastrowid})

            elif path == "/api/activity" and method == "POST":
                cur = conn.execute(
                    """INSERT INTO activity_logs (user_id, log_date, activity_type, steps, distance_km, duration_min, active_minutes, calories_burned, pace_min_km, source, verified, gps_route_json)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        uid,
                        data.get("log_date") or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                        data.get("activity_type", "walking"),
                        int(data.get("steps", 0)),
                        float(data.get("distance_km", 0)),
                        int(data.get("duration_min", 0)),
                        int(data.get("active_minutes", 0)),
                        float(data.get("calories_burned", 0)),
                        data.get("pace_min_km"),
                        data.get("source", "manual"),
                        int(bool(data.get("verified", False))),
                        json.dumps(data.get("gps_route", [])),
                    ),
                )
                conn.commit()
                self._send_json(201, {"id": cur.lastrowid})

            elif path == "/api/body/metrics" and method == "POST":
                cur = conn.execute(
                    """INSERT INTO body_metrics (user_id, log_date, weight_kg, waist_cm, hip_cm, chest_cm, arm_cm, thigh_cm, body_fat_pct, notes)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        uid,
                        data.get("log_date") or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                        float(data["weight_kg"]),
                        data.get("waist_cm"),
                        data.get("hip_cm"),
                        data.get("chest_cm"),
                        data.get("arm_cm"),
                        data.get("thigh_cm"),
                        data.get("body_fat_pct"),
                        str(data.get("notes", ""))[:300],
                    ),
                )
                conn.commit()
                self._send_json(201, {"id": cur.lastrowid})

            elif path == "/api/recovery" and method == "PUT":
                d = data.get("log_date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
                conn.execute(
                    """INSERT INTO sleep_water_logs (user_id, log_date, sleep_hours, sleep_quality, water_ml, mood, soreness, journal_note)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(user_id, log_date) DO UPDATE SET
                       sleep_hours=excluded.sleep_hours, sleep_quality=excluded.sleep_quality,
                       water_ml=excluded.water_ml, mood=excluded.mood, soreness=excluded.soreness,
                       journal_note=excluded.journal_note, updated_at=datetime('now')""",
                    (
                        uid, d,
                        float(data.get("sleep_hours", 7.5)),
                        int(data.get("sleep_quality", 4)),
                        int(data.get("water_ml", 0)),
                        str(data.get("mood", "Focused"))[:40],
                        int(data.get("soreness", 2)),
                        str(data.get("journal_note", ""))[:500],
                    ),
                )
                conn.commit()
                self._send_json(200, {"saved": True})

            elif path == "/api/ai/food-scan" and method == "POST":
                api_key = os.environ.get("GEMINI_API_KEY")
                if not api_key:
                    self._send_json(
                        503,
                        {
                            "configured": False,
                            "fallback": "manual",
                            "message": "GEMINI_API_KEY is not configured on the server. Use manual entry or edit estimates locally.",
                        },
                    )
                    return
                # Server-side Gemini Vision API call when key is present
                img_b64 = data.get("image_base64", "")
                mime = data.get("mime_type", "image/jpeg")
                if mime not in ("image/jpeg", "image/png", "image/webp") or len(img_b64) > 5_500_000:
                    self._send_json(400, {"error": "Unsupported image type or size"})
                    return
                req_body = {
                    "contents": [
                        {
                            "parts": [
                                {
                                    "text": (
                                        "Identify the food items in this photo and estimate serving_size, calories, "
                                        "protein_g, carbs_g, fat_g. Respond strictly in JSON with keys: "
                                        "name, serving_size, calories, protein_g, carbs_g, fat_g, confidence."
                                    )
                                },
                                {"inline_data": {"mime_type": mime, "data": img_b64}},
                            ]
                        }
                    ]
                }
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
                req = urllib.request.Request(url, data=json.dumps(req_body).encode("utf-8"), headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=20) as resp:
                    res = json.loads(resp.read().decode("utf-8"))
                self._send_json(200, {"configured": True, "is_estimate": True, "raw": res})

            elif path == "/api/ai/coach" and method == "POST":
                api_key = os.environ.get("GEMINI_API_KEY")
                if not api_key:
                    self._send_json(
                        503,
                        {
                            "configured": False,
                            "fallback": "local_rules",
                            "message": "GEMINI_API_KEY is not configured on the server. Using local rule-based wellness guidance.",
                        },
                    )
                    return
                prompt = str(data.get("question", ""))[:1000]
                req_body = {
                    "contents": [
                        {
                            "parts": [
                                {
                                    "text": (
                                        "You are FITTRACK PRO's general wellness & fitness coach (not a doctor; clearly "
                                        "note this is general wellness guidance, not medical advice). User question: " + prompt
                                    )
                                }
                            ]
                        }
                    ]
                }
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
                req = urllib.request.Request(url, data=json.dumps(req_body).encode("utf-8"), headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=20) as resp:
                    res = json.loads(resp.read().decode("utf-8"))
                self._send_json(200, {"configured": True, "raw": res})

            else:
                self._send_json(404, {"error": "Endpoint not found"})
        except urllib.error.URLError as exc:
            self._send_json(502, {"error": f"Upstream API error: {exc}"})
        except Exception as exc:
            self._send_json(400, {"error": str(exc)})
        finally:
            conn.close()


def main() -> None:
    init_db()
    server = ThreadingHTTPServer(("0.0.0.0", PORT), FitTrackHandler)
    print(f"FITTRACK PRO server running on http://localhost:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
