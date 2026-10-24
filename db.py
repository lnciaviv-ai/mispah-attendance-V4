#!/usr/bin/env python3
"""Database layer – SQLite (local) or PostgreSQL (Neon / Render DATABASE_URL)."""

import os
import hashlib
import time
from datetime import datetime, date

THEMES = {
    "ocean": {"name": "Ocean Blue", "primary": "#1a5276", "primary_dark": "#0e2f44", "accent": "#27ae60", "bg": "#eaf2f8", "card": "#ffffff", "text": "#1c2833"},
    "forest": {"name": "Forest Green", "primary": "#1e8449", "primary_dark": "#145a32", "accent": "#f39c12", "bg": "#e8f5e9", "card": "#ffffff", "text": "#1b5e20"},
    "sunset": {"name": "Sunset Orange", "primary": "#d35400", "primary_dark": "#a04000", "accent": "#8e44ad", "bg": "#fef5e7", "card": "#ffffff", "text": "#6e2c00"},
    "royal": {"name": "Royal Purple", "primary": "#6c3483", "primary_dark": "#4a235a", "accent": "#2980b9", "bg": "#f5eef8", "card": "#ffffff", "text": "#4a235a"},
    "slate": {"name": "Modern Slate", "primary": "#2c3e50", "primary_dark": "#1a252f", "accent": "#e74c3c", "bg": "#ecf0f1", "card": "#ffffff", "text": "#2c3e50"},
    "rose": {"name": "Rose Pink", "primary": "#ad1457", "primary_dark": "#880e4f", "accent": "#00897b", "bg": "#fce4ec", "card": "#ffffff", "text": "#880e4f"},
}

def _resolve_db_path():
    if os.environ.get("ATTENDANCE_DB"):
        path = os.environ["ATTENDANCE_DB"]
        parent = os.path.dirname(path)
        if parent and not os.path.isdir(parent):
            try:
                os.makedirs(parent, exist_ok=True)
            except Exception:
                pass
        return path
    for candidate in ("/data/attendance.db", "/var/data/attendance.db"):
        parent = os.path.dirname(candidate)
        if os.path.isdir(parent):
            try:
                if os.access(parent, os.W_OK):
                    return candidate
            except Exception:
                pass
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "attendance.db")

DB_PATH = _resolve_db_path()
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
USE_PG = DATABASE_URL.startswith("postgres")


def _with_retry(fn, retries=6, delay=0.2):
    last = None
    for i in range(retries):
        try:
            return fn()
        except Exception as e:
            last = e
            msg = str(e).lower()
            if "locked" in msg or "busy" in msg or "deadlock" in msg:
                time.sleep(delay * (i + 1))
                continue
            raise
    raise last


def get_conn():
    if USE_PG:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        url = DATABASE_URL
        # Neon / Render sometimes use postgres://
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"):]
        conn = psycopg2.connect(url, cursor_factory=RealDictCursor, sslmode="require")
        return conn
    import sqlite3
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
    except Exception:
        pass
    return conn


def _row(r):
    if r is None:
        return None
    if isinstance(r, dict):
        return dict(r)
    return dict(r)


def _rows(rs):
    return [_row(r) for r in rs]


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _ph():
    """Placeholder style."""
    return "%s" if USE_PG else "?"


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    if USE_PG:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS classes (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            teacher_name TEXT NOT NULL DEFAULT '—',
            sort_order INTEGER DEFAULT 0,
            theme TEXT DEFAULT 'ocean'
        );
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'teacher')),
            class_id INTEGER REFERENCES classes(id) ON DELETE SET NULL,
            phone TEXT,
            active INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS learners (
            id SERIAL PRIMARY KEY,
            class_id INTEGER NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            gender TEXT NOT NULL CHECK(gender IN ('seun', 'dogter')),
            active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS attendance (
            id SERIAL PRIMARY KEY,
            attendance_date TEXT NOT NULL,
            class_id INTEGER NOT NULL REFERENCES classes(id),
            learner_id INTEGER NOT NULL REFERENCES learners(id) ON DELETE CASCADE,
            status TEXT NOT NULL CHECK(status IN ('present', 'absent')),
            marked_by INTEGER REFERENCES users(id),
            marked_at TEXT,
            reason TEXT,
            status_detail TEXT,
            UNIQUE(attendance_date, learner_id)
        );
        CREATE TABLE IF NOT EXISTS daily_signatures (
            id SERIAL PRIMARY KEY,
            attendance_date TEXT NOT NULL,
            class_id INTEGER NOT NULL REFERENCES classes(id),
            signed_by INTEGER REFERENCES users(id),
            signed_at TEXT,
            UNIQUE(attendance_date, class_id)
        );
        CREATE TABLE IF NOT EXISTS admin_signoff (
            id SERIAL PRIMARY KEY,
            attendance_date TEXT NOT NULL UNIQUE,
            signed_by INTEGER NOT NULL REFERENCES users(id),
            signed_at TEXT NOT NULL,
            notes TEXT
        );
        CREATE TABLE IF NOT EXISTS messages (
            id SERIAL PRIMARY KEY,
            from_user INTEGER NOT NULL REFERENCES users(id),
            to_user INTEGER REFERENCES users(id),
            subject TEXT,
            body TEXT NOT NULL,
            created_at TEXT NOT NULL,
            read_at TEXT,
            is_broadcast INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        CREATE TABLE IF NOT EXISTS reminder_log (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            message TEXT,
            channel TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS audit_log (
            id SERIAL PRIMARY KEY,
            user_id INTEGER,
            action TEXT NOT NULL,
            detail TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS announcements (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            created_by INTEGER,
            created_at TEXT NOT NULL,
            active INTEGER DEFAULT 1
        );
        """)
    else:
        cur.executescript("""
        CREATE TABLE IF NOT EXISTS classes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            teacher_name TEXT NOT NULL DEFAULT '—',
            sort_order INTEGER DEFAULT 0,
            theme TEXT DEFAULT 'ocean'
        );
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'teacher')),
            class_id INTEGER,
            phone TEXT,
            active INTEGER DEFAULT 1,
            FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE SET NULL
        );
        CREATE TABLE IF NOT EXISTS learners (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_id INTEGER NOT NULL,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            gender TEXT NOT NULL CHECK(gender IN ('seun', 'dogter')),
            active INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            attendance_date TEXT NOT NULL,
            class_id INTEGER NOT NULL,
            learner_id INTEGER NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('present', 'absent')),
            marked_by INTEGER,
            marked_at TEXT,
            reason TEXT,
            status_detail TEXT,
            UNIQUE(attendance_date, learner_id)
        );
        CREATE TABLE IF NOT EXISTS daily_signatures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            attendance_date TEXT NOT NULL,
            class_id INTEGER NOT NULL,
            signed_by INTEGER,
            signed_at TEXT,
            UNIQUE(attendance_date, class_id)
        );
        CREATE TABLE IF NOT EXISTS admin_signoff (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            attendance_date TEXT NOT NULL UNIQUE,
            signed_by INTEGER NOT NULL,
            signed_at TEXT NOT NULL,
            notes TEXT
        );
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_user INTEGER NOT NULL,
            to_user INTEGER,
            subject TEXT,
            body TEXT NOT NULL,
            created_at TEXT NOT NULL,
            read_at TEXT,
            is_broadcast INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        CREATE TABLE IF NOT EXISTS reminder_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            message TEXT,
            channel TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            detail TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            created_by INTEGER,
            created_at TEXT NOT NULL,
            active INTEGER DEFAULT 1
        );
        """)

    # Seed classes
    classes = [
        (1, "Multi-Graad 3", "Mev. RM Maree", 1, "ocean"),
        (2, "Multi-Graad 4.1", "Me. F Cupido", 2, "forest"),
        (3, "Multi-Graad 4.2", "Me. BV Hess", 3, "sunset"),
        (4, "Multi-Graad 5.1", "Mnr. L Veroni", 4, "royal"),
        (5, "Multi-Graad 5.2(A)", "Mnr. AA April", 5, "slate"),
        (6, "Multi-Graad 5.2(B)", "Mnr. AL Fisher", 6, "rose"),
        (7, "Multi-Graad 5.3", "Mev. SH Van Dyk", 7, "ocean"),
    ]
    for c in classes:
        if USE_PG:
            cur.execute(
                """INSERT INTO classes (id, name, teacher_name, sort_order, theme) VALUES (%s,%s,%s,%s,%s)
                   ON CONFLICT (id) DO NOTHING""", c)
            cur.execute(
                """INSERT INTO classes (name, teacher_name, sort_order, theme) VALUES (%s,%s,%s,%s)
                   ON CONFLICT (name) DO NOTHING""", (c[1], c[2], c[3], c[4]))
        else:
            cur.execute(
                "INSERT OR IGNORE INTO classes (id, name, teacher_name, sort_order, theme) VALUES (?,?,?,?,?)", c)

    # Fix sequence for PG after explicit ids
    if USE_PG:
        try:
            cur.execute("SELECT setval(pg_get_serial_sequence('classes','id'), COALESCE((SELECT MAX(id) FROM classes),1))")
        except Exception:
            pass

    # Admin
    ph = _ph()
    if USE_PG:
        cur.execute(
            f"INSERT INTO users (username, password_hash, full_name, role, class_id) VALUES ({ph},{ph},{ph},{ph},{ph}) ON CONFLICT (username) DO NOTHING",
            ("admin", hash_password("admin123"), "Administrator", "admin", None),
        )
    else:
        cur.execute(
            "INSERT OR IGNORE INTO users (username, password_hash, full_name, role, class_id) VALUES (?,?,?,?,?)",
            ("admin", hash_password("admin123"), "Administrator", "admin", None),
        )

    teachers = [
        ("maree", "Mev. RM Maree", 1),
        ("cupido", "Me. F Cupido", 2),
        ("hess", "Me. BV Hess", 3),
        ("veroni", "Mnr. L Veroni", 4),
        ("april", "Mnr. AA April", 5),
        ("fisher", "Mnr. AL Fisher", 6),
        ("vandyk", "Mev. SH Van Dyk", 7),
    ]
    for username, full_name, class_id in teachers:
        if USE_PG:
            cur.execute(
                f"INSERT INTO users (username, password_hash, full_name, role, class_id) VALUES ({ph},{ph},{ph},{ph},{ph}) ON CONFLICT (username) DO NOTHING",
                (username, hash_password("teacher123"), full_name, "teacher", class_id),
            )
        else:
            cur.execute(
                "INSERT OR IGNORE INTO users (username, password_hash, full_name, role, class_id) VALUES (?,?,?,?,?)",
                (username, hash_password("teacher123"), full_name, "teacher", class_id),
            )

    sample = [
        (1, "Jade", "G", "dogter"), (1, "Ronald", "K", "seun"), (1, "Damian", "M", "seun"),
        (2, "Cameron", "M", "seun"), (2, "Joshua", "C", "seun"), (2, "Dillon", "W", "seun"),
        (3, "Damian", "J", "seun"), (3, "Muyo", "M", "seun"), (3, "Courtney", "T", "dogter"),
        (4, "Jade", "P", "dogter"), (4, "Putannes", "S", "dogter"), (4, "Adria", "A", "dogter"),
        (5, "Liam", "B", "seun"), (5, "Ethan", "S", "seun"), (5, "Mia", "K", "dogter"),
        (6, "Noah", "P", "seun"), (6, "Ava", "R", "dogter"), (6, "Oliver", "T", "seun"),
        (7, "Sophia", "L", "dogter"), (7, "Lucas", "M", "seun"), (7, "Emma", "J", "dogter"),
    ]
    for class_id, first, last, gender in sample:
        # only seed if no learners yet for that class
        cur.execute(f"SELECT COUNT(*) AS c FROM learners WHERE class_id={ph}", (class_id,))
        row = _row(cur.fetchone())
        if row and int(row.get("c") or 0) == 0:
            break  # if first class empty, seed all; if any exist, skip mass seed
    # Seed samples only when total learners is 0
    cur.execute("SELECT COUNT(*) AS c FROM learners")
    total = int((_row(cur.fetchone()) or {}).get("c") or 0)
    if total == 0:
        for class_id, first, last, gender in sample:
            cur.execute(
                f"INSERT INTO learners (class_id, first_name, last_name, gender) VALUES ({ph},{ph},{ph},{ph})",
                (class_id, first, last, gender),
            )

    defaults = {
        "school_name": "Mispah Skool vir LSEN",
        "reminder_time": "07:30",
        "reminder_message": "Goeie more! Moet asseblief vandag se bywoning merk. Dankie.",
        "admin_display_name": "Administrator",
    }
    for k, v in defaults.items():
        if USE_PG:
            cur.execute(
                f"INSERT INTO settings (key, value) VALUES ({ph},{ph}) ON CONFLICT (key) DO NOTHING",
                (k, v),
            )
        else:
            cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?,?)", (k, v))

    conn.commit()
    conn.close()
    print("Database initialised:", "PostgreSQL (Neon)" if USE_PG else DB_PATH)


def ensure_schema():
    try:
        init_db()
    except Exception as e:
        print("ensure_schema:", e)


def is_persistent_storage():
    if USE_PG:
        return True
    p = os.path.abspath(DB_PATH)
    return p.startswith("/data/") or p.startswith("/var/data/") or bool(os.environ.get("ATTENDANCE_DB"))


# ---------- Auth ----------
def authenticate(username: str, password: str):
    conn = get_conn()
    cur = conn.cursor()
    ph = _ph()
    cur.execute(
        f"SELECT * FROM users WHERE username={ph} AND password_hash={ph}",
        (username.strip().lower(), hash_password(password)),
    )
    user = _row(cur.fetchone())
    conn.close()
    return user


def get_user(user_id: int):
    conn = get_conn()
    cur = conn.cursor()
    ph = _ph()
    cur.execute(f"SELECT * FROM users WHERE id={ph}", (user_id,))
    row = _row(cur.fetchone())
    conn.close()
    return row


# ---------- Classes ----------
def get_all_classes():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM classes ORDER BY sort_order, name")
    rows = _rows(cur.fetchall())
    conn.close()
    return rows


def get_class(class_id: int):
    conn = get_conn()
    cur = conn.cursor()
    ph = _ph()
    cur.execute(f"SELECT * FROM classes WHERE id={ph}", (class_id,))
    row = _row(cur.fetchone())
    conn.close()
    return row


def set_class_theme(class_id: int, theme: str):
    if theme not in THEMES:
        theme = "ocean"
    def _do():
        conn = get_conn()
        try:
            cur = conn.cursor()
            ph = _ph()
            cur.execute(f"UPDATE classes SET theme={ph} WHERE id={ph}", (theme, class_id))
            conn.commit()
        finally:
            conn.close()
    return _with_retry(_do)


def add_class(name: str, teacher_name: str = "", sort_order: int = 99, theme: str = "ocean"):
    def _do():
        conn = get_conn()
        try:
            cur = conn.cursor()
            ph = _ph()
            cur.execute(
                f"INSERT INTO classes (name, teacher_name, sort_order, theme) VALUES ({ph},{ph},{ph},{ph})",
                (name.strip(), teacher_name.strip() or "—", sort_order, theme),
            )
            conn.commit()
            if USE_PG:
                cur.execute("SELECT lastval() AS id")
                return int(_row(cur.fetchone())["id"])
            return cur.lastrowid
        finally:
            conn.close()
    return _with_retry(_do)


def update_class(class_id: int, name: str, teacher_name: str, sort_order: int = None, theme: str = None):
    def _do():
        conn = get_conn()
        try:
            cur = conn.cursor()
            ph = _ph()
            if sort_order is not None and theme is not None:
                cur.execute(
                    f"UPDATE classes SET name={ph}, teacher_name={ph}, sort_order={ph}, theme={ph} WHERE id={ph}",
                    (name.strip(), teacher_name.strip(), sort_order, theme, class_id),
                )
            else:
                cur.execute(
                    f"UPDATE classes SET name={ph}, teacher_name={ph} WHERE id={ph}",
                    (name.strip(), teacher_name.strip(), class_id),
                )
            conn.commit()
        finally:
            conn.close()
    return _with_retry(_do)


def delete_class(class_id: int):
    def _do():
        conn = get_conn()
        try:
            cur = conn.cursor()
            ph = _ph()
            cur.execute(f"SELECT COUNT(*) AS c FROM learners WHERE class_id={ph} AND active=1", (class_id,))
            if int(_row(cur.fetchone())["c"]) > 0:
                raise ValueError("Kan nie klas uitvee terwyl daar nog aktiewe leerders is nie.")
            cur.execute(f"UPDATE users SET class_id=NULL WHERE class_id={ph}", (class_id,))
            cur.execute(f"DELETE FROM classes WHERE id={ph}", (class_id,))
            conn.commit()
        finally:
            conn.close()
    return _with_retry(_do)


def count_active_learners(class_id: int) -> int:
    conn = get_conn()
    cur = conn.cursor()
    ph = _ph()
    cur.execute(f"SELECT COUNT(*) AS c FROM learners WHERE class_id={ph} AND active=1", (class_id,))
    n = int(_row(cur.fetchone())["c"])
    conn.close()
    return n


def transfer_learners(from_class_id: int, to_class_id: int, mode: str = "move"):
    if from_class_id == to_class_id:
        raise ValueError("Bron- en teikenklas kan nie dieselfde wees nie")
    def _do():
        conn = get_conn()
        try:
            cur = conn.cursor()
            ph = _ph()
            cur.execute(
                f"SELECT id, first_name, last_name, gender FROM learners WHERE class_id={ph} AND active=1",
                (from_class_id,),
            )
            learners = _rows(cur.fetchall())
            if not learners:
                return 0
            if mode == "copy":
                for l in learners:
                    cur.execute(
                        f"INSERT INTO learners (class_id, first_name, last_name, gender, active) VALUES ({ph},{ph},{ph},{ph},1)",
                        (to_class_id, l["first_name"], l["last_name"], l["gender"]),
                    )
            else:
                cur.execute(
                    f"UPDATE learners SET class_id={ph} WHERE class_id={ph} AND active=1",
                    (to_class_id, from_class_id),
                )
            conn.commit()
            return len(learners)
        finally:
            conn.close()
    return _with_retry(_do)


# ---------- Teachers ----------
def get_all_teachers():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT u.*, c.name AS class_name
        FROM users u
        LEFT JOIN classes c ON c.id = u.class_id
        WHERE u.role = 'teacher'
        ORDER BY c.sort_order NULLS LAST, u.full_name
    """ if USE_PG else """
        SELECT u.*, c.name AS class_name
        FROM users u
        LEFT JOIN classes c ON c.id = u.class_id
        WHERE u.role = 'teacher'
        ORDER BY c.sort_order, u.full_name
    """)
    rows = _rows(cur.fetchall())
    conn.close()
    return rows


def add_teacher(username: str, password: str, full_name: str, class_id: int):
    def _do():
        conn = get_conn()
        try:
            cur = conn.cursor()
            ph = _ph()
            try:
                cur.execute(
                    f"INSERT INTO users (username, password_hash, full_name, role, class_id) VALUES ({ph},{ph},{ph},{ph},{ph})",
                    (username.strip().lower(), hash_password(password), full_name.strip(), "teacher", class_id),
                )
            except Exception as e:
                if "unique" in str(e).lower() or "duplicate" in str(e).lower():
                    raise ValueError("Gebruikersnaam bestaan reeds")
                raise
            cur.execute(f"UPDATE classes SET teacher_name={ph} WHERE id={ph}", (full_name.strip(), class_id))
            conn.commit()
            if USE_PG:
                cur.execute("SELECT lastval() AS id")
                return int(_row(cur.fetchone())["id"])
            return cur.lastrowid
        finally:
            conn.close()
    return _with_retry(_do)


def delete_teacher(user_id: int):
    def _do():
        conn = get_conn()
        try:
            cur = conn.cursor()
            ph = _ph()
            cur.execute(f"SELECT role FROM users WHERE id={ph}", (user_id,))
            row = _row(cur.fetchone())
            if not row or row["role"] != "teacher":
                raise ValueError("Slegs onderwysers kan verwyder word")
            cur.execute(f"DELETE FROM users WHERE id={ph}", (user_id,))
            conn.commit()
        finally:
            conn.close()
    return _with_retry(_do)


def update_teacher(user_id: int, full_name: str, class_id: int, new_password: str = None):
    def _do():
        conn = get_conn()
        try:
            cur = conn.cursor()
            ph = _ph()
            if new_password:
                cur.execute(
                    f"UPDATE users SET full_name={ph}, class_id={ph}, password_hash={ph} WHERE id={ph} AND role='teacher'",
                    (full_name.strip(), class_id, hash_password(new_password), user_id),
                )
            else:
                cur.execute(
                    f"UPDATE users SET full_name={ph}, class_id={ph} WHERE id={ph} AND role='teacher'",
                    (full_name.strip(), class_id, user_id),
                )
            cur.execute(f"UPDATE classes SET teacher_name={ph} WHERE id={ph}", (full_name.strip(), class_id))
            conn.commit()
        finally:
            conn.close()
    return _with_retry(_do)


def update_user_profile(user_id: int, full_name: str = None, phone: str = None, password: str = None):
    def _do():
        conn = get_conn()
        try:
            cur = conn.cursor()
            ph = _ph()
            if full_name is not None:
                cur.execute(f"UPDATE users SET full_name={ph} WHERE id={ph}", (full_name.strip(), user_id))
            if phone is not None:
                cur.execute(f"UPDATE users SET phone={ph} WHERE id={ph}", (phone.strip(), user_id))
            if password:
                cur.execute(f"UPDATE users SET password_hash={ph} WHERE id={ph}", (hash_password(password), user_id))
            conn.commit()
        finally:
            conn.close()
    return _with_retry(_do)


def get_all_users(active_only=True):
    conn = get_conn()
    cur = conn.cursor()
    sql = "SELECT u.*, c.name AS class_name FROM users u LEFT JOIN classes c ON c.id = u.class_id"
    if active_only:
        sql += " WHERE COALESCE(u.active,1)=1"
    sql += " ORDER BY u.role, u.full_name"
    cur.execute(sql)
    rows = _rows(cur.fetchall())
    conn.close()
    return rows


def get_teachers_with_phones():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT u.id, u.full_name, u.phone, u.username, c.name AS class_name
        FROM users u
        LEFT JOIN classes c ON c.id = u.class_id
        WHERE u.role='teacher' AND COALESCE(u.active,1)=1
        ORDER BY u.full_name
    """)
    rows = _rows(cur.fetchall())
    conn.close()
    return rows


# ---------- Learners ----------
def get_learners_by_class(class_id: int, active_only: bool = True):
    conn = get_conn()
    cur = conn.cursor()
    ph = _ph()
    if active_only:
        cur.execute(
            f"SELECT * FROM learners WHERE class_id={ph} AND active=1 ORDER BY last_name, first_name",
            (class_id,),
        )
    else:
        cur.execute(
            f"SELECT * FROM learners WHERE class_id={ph} ORDER BY last_name, first_name",
            (class_id,),
        )
    rows = _rows(cur.fetchall())
    conn.close()
    return rows


def get_all_learners(active_only: bool = True):
    conn = get_conn()
    cur = conn.cursor()
    sql = """
        SELECT l.*, c.name AS class_name
        FROM learners l
        JOIN classes c ON c.id = l.class_id
    """
    if active_only:
        sql += " WHERE l.active=1"
    sql += " ORDER BY c.sort_order, l.last_name, l.first_name"
    cur.execute(sql)
    rows = _rows(cur.fetchall())
    conn.close()
    return rows


def add_learner(class_id: int, first_name: str, last_name: str, gender: str, parent_name: str = "", parent_phone: str = ""):
    def _do():
        conn = get_conn()
        try:
            cur = conn.cursor()
            ph = _ph()
            cur.execute(
                f"INSERT INTO learners (class_id, first_name, last_name, gender) VALUES ({ph},{ph},{ph},{ph})",
                (class_id, first_name.strip(), last_name.strip(), gender),
            )
            conn.commit()
            if USE_PG:
                cur.execute("SELECT lastval() AS id")
                return int(_row(cur.fetchone())["id"])
            return cur.lastrowid
        finally:
            conn.close()
    return _with_retry(_do)


def update_learner(learner_id: int, class_id: int, first_name: str, last_name: str, gender: str, active: int = 1):
    def _do():
        conn = get_conn()
        try:
            cur = conn.cursor()
            ph = _ph()
            cur.execute(
                f"UPDATE learners SET class_id={ph}, first_name={ph}, last_name={ph}, gender={ph}, active={ph} WHERE id={ph}",
                (class_id, first_name.strip(), last_name.strip(), gender, active, learner_id),
            )
            conn.commit()
        finally:
            conn.close()
    return _with_retry(_do)


def deactivate_learner(learner_id: int):
    def _do():
        conn = get_conn()
        try:
            cur = conn.cursor()
            ph = _ph()
            cur.execute(f"UPDATE learners SET active=0 WHERE id={ph}", (learner_id,))
            conn.commit()
        finally:
            conn.close()
    return _with_retry(_do)


def delete_learner_permanently(learner_id: int):
    def _do():
        conn = get_conn()
        try:
            cur = conn.cursor()
            ph = _ph()
            cur.execute(f"DELETE FROM attendance WHERE learner_id={ph}", (learner_id,))
            cur.execute(f"DELETE FROM learners WHERE id={ph}", (learner_id,))
            conn.commit()
        finally:
            conn.close()
    return _with_retry(_do)


def search_learners(q: str, active_only=True):
    conn = get_conn()
    cur = conn.cursor()
    ph = _ph()
    like = f"%{q.strip()}%"
    sql = f"""
        SELECT l.*, c.name AS class_name FROM learners l
        JOIN classes c ON c.id = l.class_id
        WHERE (l.first_name LIKE {ph} OR l.last_name LIKE {ph} OR c.name LIKE {ph})
    """
    if active_only:
        sql += " AND l.active=1"
    sql += " ORDER BY l.last_name, l.first_name LIMIT 40"
    cur.execute(sql, (like, like, like))
    rows = _rows(cur.fetchall())
    conn.close()
    return rows


# ---------- Attendance ----------
def save_attendance_v2(attendance_date: str, class_id: int, records: list, user_id: int):
    def _do():
        conn = get_conn()
        try:
            cur = conn.cursor()
            ph = _ph()
            now = datetime.now().isoformat(timespec="seconds")
            for rec in records:
                status = rec["status"]
                legacy = "absent" if status == "absent" else "present"
                reason = rec.get("reason") or ""
                if USE_PG:
                    cur.execute(
                        f"""INSERT INTO attendance (attendance_date, class_id, learner_id, status, marked_by, marked_at, reason, status_detail)
                            VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})
                            ON CONFLICT (attendance_date, learner_id)
                            DO UPDATE SET status=EXCLUDED.status, marked_by=EXCLUDED.marked_by, marked_at=EXCLUDED.marked_at,
                                          reason=EXCLUDED.reason, status_detail=EXCLUDED.status_detail""",
                        (attendance_date, class_id, rec["learner_id"], legacy, user_id, now, reason, status),
                    )
                else:
                    cur.execute(
                        """INSERT INTO attendance (attendance_date, class_id, learner_id, status, marked_by, marked_at, reason, status_detail)
                           VALUES (?,?,?,?,?,?,?,?)
                           ON CONFLICT(attendance_date, learner_id)
                           DO UPDATE SET status=excluded.status, marked_by=excluded.marked_by, marked_at=excluded.marked_at,
                                         reason=excluded.reason, status_detail=excluded.status_detail""",
                        (attendance_date, class_id, rec["learner_id"], legacy, user_id, now, reason, status),
                    )
            if USE_PG:
                cur.execute(
                    f"""INSERT INTO daily_signatures (attendance_date, class_id, signed_by, signed_at)
                        VALUES ({ph},{ph},{ph},{ph})
                        ON CONFLICT (attendance_date, class_id)
                        DO UPDATE SET signed_by=EXCLUDED.signed_by, signed_at=EXCLUDED.signed_at""",
                    (attendance_date, class_id, user_id, now),
                )
            else:
                cur.execute(
                    """INSERT INTO daily_signatures (attendance_date, class_id, signed_by, signed_at)
                       VALUES (?,?,?,?)
                       ON CONFLICT(attendance_date, class_id)
                       DO UPDATE SET signed_by=excluded.signed_by, signed_at=excluded.signed_at""",
                    (attendance_date, class_id, user_id, now),
                )
            conn.commit()
        finally:
            conn.close()
    _with_retry(_do)
    try:
        audit(user_id, "mark_attendance", f"class={class_id} date={attendance_date} n={len(records)}")
    except Exception:
        pass


def save_attendance_with_reasons(attendance_date, class_id, records, user_id):
    return save_attendance_v2(attendance_date, class_id, records, user_id)


def save_attendance(attendance_date, class_id, records, user_id):
    return save_attendance_v2(attendance_date, class_id, records, user_id)


def get_attendance_for_class(attendance_date: str, class_id: int):
    conn = get_conn()
    cur = conn.cursor()
    ph = _ph()
    cur.execute(
        f"""SELECT a.*, l.first_name, l.last_name, l.gender
            FROM attendance a
            JOIN learners l ON l.id = a.learner_id
            WHERE a.attendance_date={ph} AND a.class_id={ph}""",
        (attendance_date, class_id),
    )
    rows = _rows(cur.fetchall())
    conn.close()
    return rows


def get_class_attendance_detail(attendance_date: str, class_id: int):
    return get_class_attendance_detail_v2(attendance_date, class_id)


def get_class_attendance_detail_v2(attendance_date: str, class_id: int):
    learners = get_learners_by_class(class_id)
    conn = get_conn()
    cur = conn.cursor()
    ph = _ph()
    cur.execute(
        f"SELECT learner_id, status, status_detail, reason FROM attendance WHERE attendance_date={ph} AND class_id={ph}",
        (attendance_date, class_id),
    )
    att = {r["learner_id"]: r for r in _rows(cur.fetchall())}
    conn.close()
    for l in learners:
        a = att.get(l["id"])
        if a:
            l["status"] = a.get("status_detail") or a.get("status")
            l["reason"] = a.get("reason") or ""
        else:
            l["status"] = None
            l["reason"] = ""
    return learners


def get_full_daily_register(attendance_date: str):
    classes = get_all_classes()
    result = []
    conn = get_conn()
    cur = conn.cursor()
    ph = _ph()
    for cls in classes:
        cur.execute(
            f"SELECT gender, COUNT(*) AS cnt FROM learners WHERE class_id={ph} AND active=1 GROUP BY gender",
            (cls["id"],),
        )
        gender_counts = {r["gender"]: r["cnt"] for r in _rows(cur.fetchall())}
        seuns_total = gender_counts.get("seun", 0)
        dogters_total = gender_counts.get("dogter", 0)

        cur.execute(
            f"""SELECT a.status, l.first_name, l.last_name, l.gender
                FROM attendance a
                JOIN learners l ON l.id = a.learner_id
                WHERE a.attendance_date={ph} AND a.class_id={ph} AND l.active=1""",
            (attendance_date, cls["id"]),
        )
        att_rows = _rows(cur.fetchall())
        present_seuns = present_dogters = 0
        absent_names = []
        marked = False
        for r in att_rows:
            marked = True
            if r["status"] == "present":
                if r["gender"] == "seun":
                    present_seuns += 1
                else:
                    present_dogters += 1
            else:
                absent_names.append(f"{r['first_name']} {r['last_name']}")

        if not marked:
            seuns = dogters = total = None
            absent_names = []
            signed = False
        else:
            seuns = present_seuns
            dogters = present_dogters
            total = seuns + dogters
            cur.execute(
                f"SELECT * FROM daily_signatures WHERE attendance_date={ph} AND class_id={ph}",
                (attendance_date, cls["id"]),
            )
            signed = bool(cur.fetchone())

        result.append({
            "class": cls,
            "seuns": seuns,
            "dogters": dogters,
            "totaal": total,
            "absent_names": absent_names,
            "signed": signed,
            "learners_total": seuns_total + dogters_total,
            "seuns_enrolled": seuns_total,
            "dogters_enrolled": dogters_total,
        })
    conn.close()
    return result


def admin_sign_off(attendance_date: str, user_id: int, notes: str = ""):
    def _do():
        conn = get_conn()
        try:
            cur = conn.cursor()
            ph = _ph()
            now = datetime.now().isoformat(timespec="seconds")
            if USE_PG:
                cur.execute(
                    f"""INSERT INTO admin_signoff (attendance_date, signed_by, signed_at, notes)
                        VALUES ({ph},{ph},{ph},{ph})
                        ON CONFLICT (attendance_date)
                        DO UPDATE SET signed_by=EXCLUDED.signed_by, signed_at=EXCLUDED.signed_at, notes=EXCLUDED.notes""",
                    (attendance_date, user_id, now, notes),
                )
            else:
                cur.execute(
                    """INSERT INTO admin_signoff (attendance_date, signed_by, signed_at, notes)
                       VALUES (?,?,?,?)
                       ON CONFLICT(attendance_date)
                       DO UPDATE SET signed_by=excluded.signed_by, signed_at=excluded.signed_at, notes=excluded.notes""",
                    (attendance_date, user_id, now, notes),
                )
            conn.commit()
        finally:
            conn.close()
    return _with_retry(_do)


def get_admin_signoff(attendance_date: str):
    conn = get_conn()
    cur = conn.cursor()
    ph = _ph()
    cur.execute(
        f"""SELECT s.*, u.full_name FROM admin_signoff s
            JOIN users u ON u.id = s.signed_by WHERE s.attendance_date={ph}""",
        (attendance_date,),
    )
    row = _row(cur.fetchone())
    conn.close()
    return row


def get_today_stats():
    ensure_schema()
    today = date.today().isoformat()
    conn = get_conn()
    cur = conn.cursor()
    ph = _ph()
    row = {"present": 0, "absent": 0, "marked": 0, "enrolled": 0, "classes_submitted": 0, "classes_total": 0}
    try:
        cur.execute(
            f"""SELECT
                SUM(CASE WHEN status='present' THEN 1 ELSE 0 END) AS present,
                SUM(CASE WHEN status='absent' THEN 1 ELSE 0 END) AS absent,
                COUNT(*) AS marked
                FROM attendance WHERE attendance_date={ph}""",
            (today,),
        )
        r = _row(cur.fetchone()) or {}
        row["present"] = int(r.get("present") or 0)
        row["absent"] = int(r.get("absent") or 0)
        row["marked"] = int(r.get("marked") or 0)
        cur.execute("SELECT COUNT(*) AS c FROM learners WHERE active=1")
        row["enrolled"] = int(_row(cur.fetchone())["c"])
        cur.execute(f"SELECT COUNT(DISTINCT class_id) AS c FROM daily_signatures WHERE attendance_date={ph}", (today,))
        row["classes_submitted"] = int(_row(cur.fetchone())["c"])
        cur.execute("SELECT COUNT(*) AS c FROM classes")
        row["classes_total"] = int(_row(cur.fetchone())["c"])
    except Exception:
        pass
    conn.close()
    return row


def get_attendance_trends(days: int = 30):
    conn = get_conn()
    cur = conn.cursor()
    ph = _ph()
    if USE_PG:
        cur.execute(
            f"""SELECT attendance_date,
                       SUM(CASE WHEN status='present' THEN 1 ELSE 0 END) AS present,
                       SUM(CASE WHEN status='absent' THEN 1 ELSE 0 END) AS absent,
                       COUNT(*) AS total
                FROM attendance
                WHERE attendance_date >= (CURRENT_DATE - (%s || ' days')::interval)::text
                GROUP BY attendance_date ORDER BY attendance_date""",
            (str(days),),
        )
    else:
        cur.execute(
            """SELECT attendance_date,
                      SUM(CASE WHEN status='present' THEN 1 ELSE 0 END) AS present,
                      SUM(CASE WHEN status='absent' THEN 1 ELSE 0 END) AS absent,
                      COUNT(*) AS total
               FROM attendance
               WHERE attendance_date >= date('now', ?)
               GROUP BY attendance_date ORDER BY attendance_date""",
            (f"-{days} days",),
        )
    daily = _rows(cur.fetchall())

    if USE_PG:
        cur.execute(
            f"""SELECT c.name AS class_name, c.id AS class_id,
                       SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END) AS present,
                       SUM(CASE WHEN a.status='absent' THEN 1 ELSE 0 END) AS absent,
                       COUNT(*) AS total
                FROM attendance a JOIN classes c ON c.id = a.class_id
                WHERE a.attendance_date >= (CURRENT_DATE - (%s || ' days')::interval)::text
                GROUP BY c.id, c.name, c.sort_order ORDER BY c.sort_order""",
            (str(days),),
        )
    else:
        cur.execute(
            """SELECT c.name AS class_name, c.id AS class_id,
                      SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END) AS present,
                      SUM(CASE WHEN a.status='absent' THEN 1 ELSE 0 END) AS absent,
                      COUNT(*) AS total
               FROM attendance a JOIN classes c ON c.id = a.class_id
               WHERE a.attendance_date >= date('now', ?)
               GROUP BY c.id ORDER BY c.sort_order""",
            (f"-{days} days",),
        )
    by_class = _rows(cur.fetchall())

    if USE_PG:
        cur.execute(
            f"""SELECT l.first_name, l.last_name, c.name AS class_name,
                       SUM(CASE WHEN a.status='absent' THEN 1 ELSE 0 END) AS absent_count
                FROM attendance a
                JOIN learners l ON l.id = a.learner_id
                JOIN classes c ON c.id = a.class_id
                WHERE a.attendance_date >= (CURRENT_DATE - (%s || ' days')::interval)::text AND a.status='absent'
                GROUP BY l.id, l.first_name, l.last_name, c.name
                HAVING SUM(CASE WHEN a.status='absent' THEN 1 ELSE 0 END) >= 3
                ORDER BY absent_count DESC LIMIT 20""",
            (str(days),),
        )
    else:
        cur.execute(
            """SELECT l.first_name, l.last_name, c.name AS class_name,
                      SUM(CASE WHEN a.status='absent' THEN 1 ELSE 0 END) AS absent_count
               FROM attendance a
               JOIN learners l ON l.id = a.learner_id
               JOIN classes c ON c.id = a.class_id
               WHERE a.attendance_date >= date('now', ?) AND a.status='absent'
               GROUP BY l.id
               HAVING absent_count >= 3
               ORDER BY absent_count DESC LIMIT 20""",
            (f"-{days} days",),
        )
    frequent_absent = _rows(cur.fetchall())
    conn.close()
    return {"daily": daily, "by_class": by_class, "frequent_absent": frequent_absent}


def get_learner_history(learner_id: int, limit=60):
    conn = get_conn()
    cur = conn.cursor()
    ph = _ph()
    cur.execute(
        f"""SELECT a.*, c.name AS class_name FROM attendance a
            JOIN classes c ON c.id = a.class_id
            WHERE a.learner_id={ph}
            ORDER BY a.attendance_date DESC LIMIT {int(limit)}""",
        (learner_id,),
    )
    rows = _rows(cur.fetchall())
    conn.close()
    return rows


def export_register_csv(attendance_date: str):
    register = get_full_daily_register(attendance_date)
    lines = ["Klas,Opvoeder,Seuns,Dogters,Totaal,Afwesig,Geteken"]
    for r in register:
        c = r["class"]
        seuns = r["seuns"] if r["seuns"] is not None else ""
        dogters = r["dogters"] if r["dogters"] is not None else ""
        totaal = r["totaal"] if r["totaal"] is not None else ""
        absent = "; ".join(r["absent_names"]) if r["absent_names"] else ""
        signed = "Ja" if r["signed"] else "Nee"
        lines.append(f'"{c["name"]}","{c["teacher_name"]}",{seuns},{dogters},{totaal},"{absent}",{signed}')
    return "\n".join(lines)


def export_all_attendance_csv(days=90):
    conn = get_conn()
    cur = conn.cursor()
    ph = _ph()
    if USE_PG:
        cur.execute(
            f"""SELECT a.attendance_date, c.name AS class_name, l.first_name, l.last_name, l.gender,
                       a.status, COALESCE(a.status_detail, a.status) AS detail, COALESCE(a.reason,'') AS reason
                FROM attendance a
                JOIN learners l ON l.id = a.learner_id
                JOIN classes c ON c.id = a.class_id
                WHERE a.attendance_date >= (CURRENT_DATE - (%s || ' days')::interval)::text
                ORDER BY a.attendance_date DESC""",
            (str(days),),
        )
    else:
        cur.execute(
            """SELECT a.attendance_date, c.name AS class_name, l.first_name, l.last_name, l.gender,
                      a.status, COALESCE(a.status_detail, a.status) AS detail, COALESCE(a.reason,'') AS reason
               FROM attendance a
               JOIN learners l ON l.id = a.learner_id
               JOIN classes c ON c.id = a.class_id
               WHERE a.attendance_date >= date('now', ?)
               ORDER BY a.attendance_date DESC""",
            (f"-{days} days",),
        )
    rows = _rows(cur.fetchall())
    conn.close()
    lines = ["Datum,Klas,Voornaam,Van,Geslag,Status,Detail,Rede"]
    for r in rows:
        lines.append(
            f'{r["attendance_date"]},"{r["class_name"]}","{r["first_name"]}","{r["last_name"]}",{r["gender"]},{r["status"]},{r["detail"]},"{r["reason"]}"'
        )
    return "\n".join(lines)


# ---------- Settings / messages / audit / announcements ----------
def get_setting(key: str, default: str = ""):
    conn = get_conn()
    cur = conn.cursor()
    ph = _ph()
    cur.execute(f"SELECT value FROM settings WHERE key={ph}", (key,))
    row = _row(cur.fetchone())
    conn.close()
    return row["value"] if row else default


def set_setting(key: str, value: str):
    def _do():
        conn = get_conn()
        try:
            cur = conn.cursor()
            ph = _ph()
            if USE_PG:
                cur.execute(
                    f"INSERT INTO settings (key, value) VALUES ({ph},{ph}) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value",
                    (key, value),
                )
            else:
                cur.execute(
                    "INSERT INTO settings (key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (key, value),
                )
            conn.commit()
        finally:
            conn.close()
    return _with_retry(_do)


def get_all_settings():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT key, value FROM settings")
    rows = {r["key"]: r["value"] for r in _rows(cur.fetchall())}
    conn.close()
    return rows


def send_message(from_user: int, body: str, to_user: int = None, subject: str = "", is_broadcast: bool = False):
    def _do():
        conn = get_conn()
        try:
            cur = conn.cursor()
            ph = _ph()
            now = datetime.now().isoformat(timespec="seconds")
            cur.execute(
                f"""INSERT INTO messages (from_user, to_user, subject, body, created_at, is_broadcast)
                    VALUES ({ph},{ph},{ph},{ph},{ph},{ph})""",
                (from_user, to_user, subject.strip(), body.strip(), now, 1 if is_broadcast else 0),
            )
            conn.commit()
            if USE_PG:
                cur.execute("SELECT lastval() AS id")
                return int(_row(cur.fetchone())["id"])
            return cur.lastrowid
        finally:
            conn.close()
    return _with_retry(_do)


def get_conversation(limit: int = 100):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        f"""SELECT m.*, u.full_name AS from_name, t.full_name AS to_name
            FROM messages m
            JOIN users u ON u.id = m.from_user
            LEFT JOIN users t ON t.id = m.to_user
            ORDER BY m.created_at DESC LIMIT {int(limit)}"""
    )
    rows = _rows(cur.fetchall())
    conn.close()
    return rows


def audit(user_id, action: str, detail: str = ""):
    def _do():
        conn = get_conn()
        try:
            cur = conn.cursor()
            ph = _ph()
            now = datetime.now().isoformat(timespec="seconds")
            cur.execute(
                f"INSERT INTO audit_log (user_id, action, detail, created_at) VALUES ({ph},{ph},{ph},{ph})",
                (user_id, action, detail, now),
            )
            conn.commit()
        finally:
            conn.close()
    try:
        return _with_retry(_do)
    except Exception:
        pass


def log_audit(user_id, action, detail=""):
    return audit(user_id, action, detail)


def get_audit_log(limit=100):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        f"""SELECT a.*, u.full_name FROM audit_log a
            LEFT JOIN users u ON u.id = a.user_id
            ORDER BY a.created_at DESC LIMIT {int(limit)}"""
    )
    rows = _rows(cur.fetchall())
    conn.close()
    return rows


def add_announcement(title, body, user_id):
    def _do():
        conn = get_conn()
        try:
            cur = conn.cursor()
            ph = _ph()
            now = datetime.now().isoformat(timespec="seconds")
            cur.execute(
                f"INSERT INTO announcements (title, body, created_by, created_at, active) VALUES ({ph},{ph},{ph},{ph},1)",
                (title.strip(), body.strip(), user_id, now),
            )
            conn.commit()
            if USE_PG:
                cur.execute("SELECT lastval() AS id")
                return int(_row(cur.fetchone())["id"])
            return cur.lastrowid
        finally:
            conn.close()
    return _with_retry(_do)


def get_active_announcements():
    ensure_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT a.*, u.full_name FROM announcements a
            LEFT JOIN users u ON u.id = a.created_by
            WHERE a.active=1 ORDER BY a.created_at DESC LIMIT 5
        """)
        rows = _rows(cur.fetchall())
    except Exception:
        rows = []
    conn.close()
    return rows


def deactivate_announcement(aid):
    def _do():
        conn = get_conn()
        try:
            cur = conn.cursor()
            ph = _ph()
            cur.execute(f"UPDATE announcements SET active=0 WHERE id={ph}", (aid,))
            conn.commit()
        finally:
            conn.close()
    return _with_retry(_do)


def log_reminder(user_id: int, message: str, channel: str = "in-app"):
    def _do():
        conn = get_conn()
        try:
            cur = conn.cursor()
            ph = _ph()
            now = datetime.now().isoformat(timespec="seconds")
            cur.execute(
                f"INSERT INTO reminder_log (user_id, message, channel, created_at) VALUES ({ph},{ph},{ph},{ph})",
                (user_id, message, channel, now),
            )
            conn.commit()
        finally:
            conn.close()
    return _with_retry(_do)


def export_full_backup():
    ensure_schema()
    conn = get_conn()
    cur = conn.cursor()
    data = {"version": 1, "exported_at": datetime.now().isoformat(timespec="seconds")}
    for table in ("classes", "users", "learners", "attendance", "daily_signatures",
                  "admin_signoff", "messages", "settings", "announcements", "audit_log", "reminder_log"):
        try:
            cur.execute(f"SELECT * FROM {table}")
            data[table] = _rows(cur.fetchall())
        except Exception:
            data[table] = []
    conn.close()
    return data


def import_full_backup(data: dict, replace: bool = True):
    ensure_schema()
    if not isinstance(data, dict) or data.get("version") != 1:
        raise ValueError("Ongeldige rugsteun-lêer")
    def _do():
        conn = get_conn()
        try:
            cur = conn.cursor()
            order = ["classes", "users", "learners", "attendance", "daily_signatures",
                     "admin_signoff", "messages", "settings", "announcements", "audit_log", "reminder_log"]
            if replace:
                for table in reversed(order):
                    try:
                        cur.execute(f"DELETE FROM {table}")
                    except Exception:
                        pass
            for table in order:
                rows = data.get(table) or []
                if not rows:
                    continue
                cols = list(rows[0].keys())
                phs = ",".join([_ph()] * len(cols))
                col_list = ",".join(cols)
                for row in rows:
                    vals = [row.get(c) for c in cols]
                    try:
                        cur.execute(f"INSERT INTO {table} ({col_list}) VALUES ({phs})", vals)
                    except Exception:
                        pass
            conn.commit()
        finally:
            conn.close()
    return _with_retry(_do)


if __name__ == "__main__":
    init_db()
    print("Done. USE_PG =", USE_PG)
