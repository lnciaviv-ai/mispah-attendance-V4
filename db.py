#!/usr/bin/env python3
"""Database layer for Mispah School Daily Attendance System."""

import sqlite3
import hashlib
import os
from datetime import datetime, date
import time

DB_PATH = os.environ.get("ATTENDANCE_DB", os.path.join(os.path.dirname(os.path.abspath(__file__)), "attendance.db"))

THEMES = {
    "ocean": {
        "name": "Ocean Blue",
        "primary": "#1a5276",
        "primary_dark": "#0e2f44",
        "accent": "#27ae60",
        "bg": "#eaf2f8",
        "card": "#ffffff",
        "text": "#1c2833",
    },
    "forest": {
        "name": "Forest Green",
        "primary": "#1e8449",
        "primary_dark": "#145a32",
        "accent": "#f39c12",
        "bg": "#e8f5e9",
        "card": "#ffffff",
        "text": "#1b5e20",
    },
    "sunset": {
        "name": "Sunset Orange",
        "primary": "#d35400",
        "primary_dark": "#a04000",
        "accent": "#8e44ad",
        "bg": "#fef5e7",
        "card": "#ffffff",
        "text": "#6e2c00",
    },
    "royal": {
        "name": "Royal Purple",
        "primary": "#6c3483",
        "primary_dark": "#4a235a",
        "accent": "#2980b9",
        "bg": "#f5eef8",
        "card": "#ffffff",
        "text": "#4a235a",
    },
    "slate": {
        "name": "Modern Slate",
        "primary": "#2c3e50",
        "primary_dark": "#1a252f",
        "accent": "#e74c3c",
        "bg": "#ecf0f1",
        "card": "#ffffff",
        "text": "#2c3e50",
    },
    "rose": {
        "name": "Rose Pink",
        "primary": "#ad1457",
        "primary_dark": "#880e4f",
        "accent": "#00897b",
        "bg": "#fce4ec",
        "card": "#ffffff",
        "text": "#880e4f",
    },
}

def _with_retry(fn, retries=6, delay=0.2):
    """Retry write when SQLite reports database is locked."""
    last = None
    for i in range(retries):
        try:
            return fn()
        except sqlite3.OperationalError as e:
            last = e
            if "locked" in str(e).lower() or "busy" in str(e).lower():
                time.sleep(delay * (i + 1))
                continue
            raise
    raise last

def get_conn():
    """Open a SQLite connection that tolerates concurrent access (Render / multi-request)."""
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        full_name TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('admin', 'teacher')),
        class_id INTEGER,
        FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE SET NULL
    );

    CREATE TABLE IF NOT EXISTS classes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        teacher_name TEXT NOT NULL,
        sort_order INTEGER DEFAULT 0,
        theme TEXT DEFAULT 'ocean'
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
        UNIQUE(attendance_date, learner_id),
        FOREIGN KEY (class_id) REFERENCES classes(id),
        FOREIGN KEY (learner_id) REFERENCES learners(id) ON DELETE CASCADE,
        FOREIGN KEY (marked_by) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS daily_signatures (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        attendance_date TEXT NOT NULL,
        class_id INTEGER NOT NULL,
        signed_by INTEGER,
        signed_at TEXT,
        UNIQUE(attendance_date, class_id),
        FOREIGN KEY (class_id) REFERENCES classes(id),
        FOREIGN KEY (signed_by) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS admin_signoff (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        attendance_date TEXT NOT NULL UNIQUE,
        signed_by INTEGER NOT NULL,
        signed_at TEXT NOT NULL,
        notes TEXT,
        FOREIGN KEY (signed_by) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_user INTEGER NOT NULL,
        to_user INTEGER,
        subject TEXT,
        body TEXT NOT NULL,
        created_at TEXT NOT NULL,
        read_at TEXT,
        is_broadcast INTEGER DEFAULT 0,
        FOREIGN KEY (from_user) REFERENCES users(id),
        FOREIGN KEY (to_user) REFERENCES users(id)
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
        created_at TEXT,
        FOREIGN KEY (user_id) REFERENCES users(id)
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

    try:
        cur.execute("ALTER TABLE classes ADD COLUMN theme TEXT DEFAULT 'ocean'")
    except sqlite3.OperationalError:
        pass


    # Column migrations (safe if already exist)
    for stmt in [
        "ALTER TABLE classes ADD COLUMN theme TEXT DEFAULT 'ocean'",
        "ALTER TABLE users ADD COLUMN phone TEXT",
        "ALTER TABLE users ADD COLUMN active INTEGER DEFAULT 1",
        "ALTER TABLE attendance ADD COLUMN reason TEXT",
        "ALTER TABLE attendance ADD COLUMN status_detail TEXT",
    ]:
        try:
            cur.execute(stmt)
        except Exception:
            pass

    # Default settings
    defaults = {
        "school_name": "Mispah Skool vir LSEN",
        "reminder_time": "07:30",
        "reminder_message": "Goeie more! Moet asseblief vandag se bywoning merk. Dankie.",
        "admin_display_name": "Administrator",
    }
    for k, v in defaults.items():
        cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?,?)", (k, v))

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
        cur.execute(
            "INSERT OR IGNORE INTO classes (id, name, teacher_name, sort_order, theme) VALUES (?,?,?,?,?)",
            c,
        )

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
        cur.execute(
            "INSERT OR IGNORE INTO users (username, password_hash, full_name, role, class_id) VALUES (?,?,?,?,?)",
            (username, hash_password("teacher123"), full_name, "teacher", class_id),
        )

    sample_learners = [
        (1, "Jade", "G", "dogter"),
        (1, "Ronald", "K", "seun"),
        (1, "Damian", "M", "seun"),
        (2, "Cameron", "M", "seun"),
        (2, "Joshua", "C", "seun"),
        (2, "Dillon", "W", "seun"),
        (2, "Feralo", "D", "seun"),
        (3, "Damian", "J", "seun"),
        (3, "Muyo", "M", "seun"),
        (3, "Courtney", "T", "dogter"),
        (4, "Jade", "P", "dogter"),
        (4, "Putannes", "S", "dogter"),
        (4, "Adria", "A", "dogter"),
        (5, "Liam", "B", "seun"),
        (5, "Ethan", "S", "seun"),
        (5, "Mia", "K", "dogter"),
        (6, "Noah", "P", "seun"),
        (6, "Ava", "R", "dogter"),
        (6, "Oliver", "T", "seun"),
        (7, "Sophia", "L", "dogter"),
        (7, "Lucas", "M", "seun"),
        (7, "Emma", "J", "dogter"),
        (7, "James", "H", "seun"),
        (7, "Isabella", "V", "dogter"),
    ]
    for class_id, first, last, gender in sample_learners:
        cur.execute(
            """INSERT OR IGNORE INTO learners (class_id, first_name, last_name, gender)
               SELECT ?,?,?,? WHERE NOT EXISTS (
                   SELECT 1 FROM learners WHERE class_id=? AND first_name=? AND last_name=?
               )""",
            (class_id, first, last, gender, class_id, first, last),
        )

    conn.commit()
    conn.close()
    ensure_schema()
    print("Database initialised:", DB_PATH)

def authenticate(username: str, password: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM users WHERE username=? AND password_hash=?",
        (username.strip().lower(), hash_password(password)),
    )
    user = cur.fetchone()
    conn.close()
    return dict(user) if user else None

def get_user(user_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id=?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def get_all_classes():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM classes ORDER BY sort_order, name")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def get_class(class_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM classes WHERE id=?", (class_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def set_class_theme(class_id: int, theme: str):
    if theme not in THEMES:
        theme = "ocean"
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE classes SET theme=? WHERE id=?", (theme, class_id))
    conn.commit()
    conn.close()

def update_class_teacher_name(class_id: int, teacher_name: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE classes SET teacher_name=? WHERE id=?", (teacher_name.strip(), class_id))
    conn.commit()
    conn.close()

def get_all_teachers():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT u.*, c.name AS class_name
        FROM users u
        LEFT JOIN classes c ON c.id = u.class_id
        WHERE u.role = 'teacher'
        ORDER BY c.sort_order, u.full_name
    """)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def add_teacher(username: str, password: str, full_name: str, class_id: int):
    def _do():
        conn = get_conn()
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO users (username, password_hash, full_name, role, class_id) VALUES (?,?,?,?,?)",
                (username.strip().lower(), hash_password(password), full_name.strip(), "teacher", class_id),
            )
            cur.execute("UPDATE classes SET teacher_name=? WHERE id=?", (full_name.strip(), class_id))
            conn.commit()
            return cur.lastrowid
        except sqlite3.IntegrityError:
            raise ValueError("Gebruikersnaam bestaan reeds")
        finally:
            conn.close()
    return _with_retry(_do)

def delete_teacher(user_id: int):
    def _do():
        conn = get_conn()
        try:
            cur = conn.cursor()
            cur.execute("SELECT role FROM users WHERE id=?", (user_id,))
            row = cur.fetchone()
            if not row or row["role"] != "teacher":
                raise ValueError("Slegs onderwysers kan verwyder word")
            cur.execute("DELETE FROM users WHERE id=?", (user_id,))
            conn.commit()
        finally:
            conn.close()
    return _with_retry(_do)

def update_teacher(user_id: int, full_name: str, class_id: int, new_password: str = None):
    def _do():
        conn = get_conn()
        try:
            cur = conn.cursor()
            if new_password:
                cur.execute(
                    "UPDATE users SET full_name=?, class_id=?, password_hash=? WHERE id=? AND role='teacher'",
                    (full_name.strip(), class_id, hash_password(new_password), user_id),
                )
            else:
                cur.execute(
                    "UPDATE users SET full_name=?, class_id=? WHERE id=? AND role='teacher'",
                    (full_name.strip(), class_id, user_id),
                )
            cur.execute("UPDATE classes SET teacher_name=? WHERE id=?", (full_name.strip(), class_id))
            conn.commit()
        finally:
            conn.close()
    return _with_retry(_do)

def get_learners_by_class(class_id: int, active_only: bool = True):
    conn = get_conn()
    cur = conn.cursor()
    if active_only:
        cur.execute(
            "SELECT * FROM learners WHERE class_id=? AND active=1 ORDER BY last_name, first_name",
            (class_id,),
        )
    else:
        cur.execute(
            "SELECT * FROM learners WHERE class_id=? ORDER BY last_name, first_name",
            (class_id,),
        )
    rows = [dict(r) for r in cur.fetchall()]
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
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def add_learner(class_id: int, first_name: str, last_name: str, gender: str, parent_name: str = "", parent_phone: str = ""):
    """parent_name/parent_phone ignored — kept only for backward-compatible call sites."""
    def _do():
        conn = get_conn()
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO learners (class_id, first_name, last_name, gender) VALUES (?,?,?,?)",
                (class_id, first_name.strip(), last_name.strip(), gender),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()
    return _with_retry(_do)

def update_learner(learner_id: int, class_id: int, first_name: str, last_name: str, gender: str, active: int = 1):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """UPDATE learners SET class_id=?, first_name=?, last_name=?, gender=?, active=?
           WHERE id=?""",
        (class_id, first_name.strip(), last_name.strip(), gender, active, learner_id),
    )
    conn.commit()
    conn.close()

def deactivate_learner(learner_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE learners SET active=0 WHERE id=?", (learner_id,))
    conn.commit()
    conn.close()

def delete_learner_permanently(learner_id: int):
    def _do():
        conn = get_conn()
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM attendance WHERE learner_id=?", (learner_id,))
            cur.execute("DELETE FROM learners WHERE id=?", (learner_id,))
            conn.commit()
        finally:
            conn.close()
    return _with_retry(_do)

def save_attendance(attendance_date: str, class_id: int, records: list, user_id: int):
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.now().isoformat(timespec="seconds")
    for rec in records:
        cur.execute(
            """INSERT INTO attendance (attendance_date, class_id, learner_id, status, marked_by, marked_at)
               VALUES (?,?,?,?,?,?)
               ON CONFLICT(attendance_date, learner_id)
               DO UPDATE SET status=excluded.status, marked_by=excluded.marked_by, marked_at=excluded.marked_at""",
            (attendance_date, class_id, rec["learner_id"], rec["status"], user_id, now),
        )
    cur.execute(
        """INSERT INTO daily_signatures (attendance_date, class_id, signed_by, signed_at)
           VALUES (?,?,?,?)
           ON CONFLICT(attendance_date, class_id)
           DO UPDATE SET signed_by=excluded.signed_by, signed_at=excluded.signed_at""",
        (attendance_date, class_id, user_id, now),
    )
    conn.commit()
    conn.close()

def get_attendance_for_class(attendance_date: str, class_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """SELECT a.*, l.first_name, l.last_name, l.gender
           FROM attendance a
           JOIN learners l ON l.id = a.learner_id
           WHERE a.attendance_date=? AND a.class_id=?""",
        (attendance_date, class_id),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def get_class_attendance_detail(attendance_date: str, class_id: int):
    learners = get_learners_by_class(class_id)
    att_map = {a["learner_id"]: a for a in get_attendance_for_class(attendance_date, class_id)}
    for l in learners:
        a = att_map.get(l["id"])
        l["status"] = a["status"] if a else None
        l["reason"] = a.get("reason") if a else None
    return learners

def get_full_daily_register(attendance_date: str):
    classes = get_all_classes()
    result = []
    conn = get_conn()
    cur = conn.cursor()

    for cls in classes:
        cur.execute(
            """SELECT gender, COUNT(*) as cnt FROM learners
               WHERE class_id=? AND active=1 GROUP BY gender""",
            (cls["id"],),
        )
        gender_counts = {r["gender"]: r["cnt"] for r in cur.fetchall()}
        seuns_total = gender_counts.get("seun", 0)
        dogters_total = gender_counts.get("dogter", 0)

        cur.execute(
            """SELECT a.status, l.first_name, l.last_name, l.gender
               FROM attendance a
               JOIN learners l ON l.id = a.learner_id
               WHERE a.attendance_date=? AND a.class_id=? AND l.active=1""",
            (attendance_date, cls["id"]),
        )
        att_rows = cur.fetchall()

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
                "SELECT * FROM daily_signatures WHERE attendance_date=? AND class_id=?",
                (attendance_date, cls["id"]),
            )
            sig = cur.fetchone()
            signed = bool(sig)

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
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.now().isoformat(timespec="seconds")
    cur.execute(
        """INSERT INTO admin_signoff (attendance_date, signed_by, signed_at, notes)
           VALUES (?,?,?,?)
           ON CONFLICT(attendance_date)
           DO UPDATE SET signed_by=excluded.signed_by, signed_at=excluded.signed_at, notes=excluded.notes""",
        (attendance_date, user_id, now, notes),
    )
    conn.commit()
    conn.close()

def get_admin_signoff(attendance_date: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT s.*, u.full_name
        FROM admin_signoff s
        JOIN users u ON u.id = s.signed_by
        WHERE s.attendance_date=?
    """, (attendance_date,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None



# ---------- Classes CRUD ----------
def add_class(name: str, teacher_name: str = "", sort_order: int = 99, theme: str = "ocean"):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO classes (name, teacher_name, sort_order, theme) VALUES (?,?,?,?)",
        (name.strip(), teacher_name.strip() or "—", sort_order, theme),
    )
    conn.commit()
    cid = cur.lastrowid
    conn.close()
    return cid

def update_class(class_id: int, name: str, teacher_name: str, sort_order: int = None, theme: str = None):
    conn = get_conn()
    cur = conn.cursor()
    if sort_order is not None and theme is not None:
        cur.execute(
            "UPDATE classes SET name=?, teacher_name=?, sort_order=?, theme=? WHERE id=?",
            (name.strip(), teacher_name.strip(), sort_order, theme, class_id),
        )
    else:
        cur.execute(
            "UPDATE classes SET name=?, teacher_name=? WHERE id=?",
            (name.strip(), teacher_name.strip(), class_id),
        )
    conn.commit()
    conn.close()


def transfer_learners(from_class_id: int, to_class_id: int, mode: str = "move"):
    """
    mode=move: change class_id of all active learners (keeps same learner records + history)
    mode=copy: create new learner rows in destination class (duplicates names)
    Returns number of learners affected.
    """
    if from_class_id == to_class_id:
        raise ValueError("Bron- en teikenklas kan nie dieselfde wees nie")
    def _do():
        conn = get_conn()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, first_name, last_name, gender FROM learners WHERE class_id=? AND active=1",
                (from_class_id,),
            )
            learners = cur.fetchall()
            if not learners:
                return 0
            if mode == "copy":
                for l in learners:
                    cur.execute(
                        "INSERT INTO learners (class_id, first_name, last_name, gender, active) VALUES (?,?,?,?,1)",
                        (to_class_id, l["first_name"], l["last_name"], l["gender"]),
                    )
            else:
                # move — preserve learner id and all attendance history
                cur.execute(
                    "UPDATE learners SET class_id=? WHERE class_id=? AND active=1",
                    (to_class_id, from_class_id),
                )
            conn.commit()
            return len(learners)
        finally:
            conn.close()
    return _with_retry(_do)

def count_active_learners(class_id: int) -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as c FROM learners WHERE class_id=? AND active=1", (class_id,))
    n = cur.fetchone()["c"]
    conn.close()
    return n


def delete_class(class_id: int):
    """Delete class only if no active learners."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as c FROM learners WHERE class_id=? AND active=1", (class_id,))
    if cur.fetchone()["c"] > 0:
        conn.close()
        raise ValueError("Kan nie klas uitvee terwyl daar nog aktiewe leerders is nie. Skuif of verwyder eers die leerders.")
    cur.execute("UPDATE users SET class_id=NULL WHERE class_id=?", (class_id,))
    cur.execute("DELETE FROM classes WHERE id=?", (class_id,))
    conn.commit()
    conn.close()

# ---------- Settings ----------
def get_setting(key: str, default: str = ""):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT value FROM settings WHERE key=?", (key,))
    row = cur.fetchone()
    conn.close()
    return row["value"] if row else default

def set_setting(key: str, value: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO settings (key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )
    conn.commit()
    conn.close()

def get_all_settings():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT key, value FROM settings")
    rows = {r["key"]: r["value"] for r in cur.fetchall()}
    conn.close()
    return rows

# ---------- User phone / profile ----------
def update_user_profile(user_id: int, full_name: str = None, phone: str = None, password: str = None):
    conn = get_conn()
    cur = conn.cursor()
    if full_name is not None:
        cur.execute("UPDATE users SET full_name=? WHERE id=?", (full_name.strip(), user_id))
    if phone is not None:
        cur.execute("UPDATE users SET phone=? WHERE id=?", (phone.strip(), user_id))
    if password:
        cur.execute("UPDATE users SET password_hash=? WHERE id=?", (hash_password(password), user_id))
    conn.commit()
    conn.close()

def get_all_users(active_only=True):
    conn = get_conn()
    cur = conn.cursor()
    sql = "SELECT u.*, c.name AS class_name FROM users u LEFT JOIN classes c ON c.id = u.class_id"
    if active_only:
        sql += " WHERE COALESCE(u.active,1)=1"
    sql += " ORDER BY u.role, u.full_name"
    cur.execute(sql)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

# ---------- Messages ----------
def send_message(from_user: int, body: str, to_user: int = None, subject: str = "", is_broadcast: bool = False):
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.now().isoformat(timespec="seconds")
    cur.execute(
        """INSERT INTO messages (from_user, to_user, subject, body, created_at, is_broadcast)
           VALUES (?,?,?,?,?,?)""",
        (from_user, to_user, subject.strip(), body.strip(), now, 1 if is_broadcast else 0),
    )
    conn.commit()
    mid = cur.lastrowid
    conn.close()
    return mid

def get_messages_for_user(user_id: int, limit: int = 50):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT m.*, u.full_name AS from_name
        FROM messages m
        JOIN users u ON u.id = m.from_user
        WHERE m.to_user=? OR m.to_user IS NULL OR m.is_broadcast=1 OR m.from_user=?
        ORDER BY m.created_at DESC
        LIMIT ?
    """, (user_id, user_id, limit))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def get_conversation(limit: int = 100):
    """All messages for the noticeboard / chat."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT m.*, u.full_name AS from_name, t.full_name AS to_name
        FROM messages m
        JOIN users u ON u.id = m.from_user
        LEFT JOIN users t ON t.id = m.to_user
        ORDER BY m.created_at DESC
        LIMIT ?
    """, (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def mark_message_read(msg_id: int):
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.now().isoformat(timespec="seconds")
    cur.execute("UPDATE messages SET read_at=? WHERE id=? AND read_at IS NULL", (now, msg_id))
    conn.commit()
    conn.close()

# ---------- Trends ----------
def get_attendance_trends(days: int = 30):
    """Return daily totals and per-class rates for the last N days."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT attendance_date,
               SUM(CASE WHEN status='present' THEN 1 ELSE 0 END) AS present,
               SUM(CASE WHEN status='absent' THEN 1 ELSE 0 END) AS absent,
               COUNT(*) AS total
        FROM attendance
        WHERE attendance_date >= date('now', ?)
        GROUP BY attendance_date
        ORDER BY attendance_date
    """, (f"-{days} days",))
    daily = [dict(r) for r in cur.fetchall()]

    cur.execute("""
        SELECT c.name AS class_name, c.id AS class_id,
               SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END) AS present,
               SUM(CASE WHEN a.status='absent' THEN 1 ELSE 0 END) AS absent,
               COUNT(*) AS total
        FROM attendance a
        JOIN classes c ON c.id = a.class_id
        WHERE a.attendance_date >= date('now', ?)
        GROUP BY c.id
        ORDER BY c.sort_order
    """, (f"-{days} days",))
    by_class = [dict(r) for r in cur.fetchall()]

    cur.execute("""
        SELECT l.first_name, l.last_name, c.name AS class_name,
               SUM(CASE WHEN a.status='absent' THEN 1 ELSE 0 END) AS absent_count
        FROM attendance a
        JOIN learners l ON l.id = a.learner_id
        JOIN classes c ON c.id = a.class_id
        WHERE a.attendance_date >= date('now', ?) AND a.status='absent'
        GROUP BY l.id
        HAVING absent_count >= 3
        ORDER BY absent_count DESC
        LIMIT 20
    """, (f"-{days} days",))
    frequent_absent = [dict(r) for r in cur.fetchall()]

    conn.close()
    return {"daily": daily, "by_class": by_class, "frequent_absent": frequent_absent}

# ---------- Reminders ----------
def log_reminder(user_id: int, message: str, channel: str = "in-app"):
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.now().isoformat(timespec="seconds")
    cur.execute(
        "INSERT INTO reminder_log (user_id, message, channel, created_at) VALUES (?,?,?,?)",
        (user_id, message, channel, now),
    )
    conn.commit()
    conn.close()

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
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows



# ---------- Premium helpers ----------
def log_audit(user_id, action, detail=""):
    from datetime import datetime
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO audit_log (user_id, action, detail, created_at) VALUES (?,?,?,?)",
        (user_id, action, detail, datetime.now().isoformat(timespec="seconds")),
    )
    conn.commit()
    conn.close()

def get_audit_log(limit=100):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT a.*, u.full_name FROM audit_log a
        LEFT JOIN users u ON u.id = a.user_id
        ORDER BY a.id DESC LIMIT ?
    """, (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def search_learners(q, active_only=True):
    conn = get_conn()
    cur = conn.cursor()
    q = f"%{q.strip()}%"
    sql = """
        SELECT l.*, c.name AS class_name FROM learners l
        JOIN classes c ON c.id = l.class_id
        WHERE (l.first_name LIKE ? OR l.last_name LIKE ? OR c.name LIKE ?)
    """
    if active_only:
        sql += " AND l.active=1"
    sql += " ORDER BY l.last_name, l.first_name LIMIT 50"
    cur.execute(sql, (q, q, q))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def get_dashboard_stats(attendance_date=None):
    if not attendance_date:
        from datetime import date
        attendance_date = date.today().isoformat()
    classes = get_all_classes()
    submitted = 0
    pending = []
    total_present = total_absent = total_enrolled = 0
    conn = get_conn()
    cur = conn.cursor()
    for cls in classes:
        cur.execute("SELECT COUNT(*) as c FROM learners WHERE class_id=? AND active=1", (cls["id"],))
        enrolled = cur.fetchone()["c"]
        total_enrolled += enrolled
        cur.execute("SELECT COUNT(*) as c FROM daily_signatures WHERE attendance_date=? AND class_id=?",
                    (attendance_date, cls["id"]))
        if cur.fetchone()["c"]:
            submitted += 1
            cur.execute("""
                SELECT status, COUNT(*) as c FROM attendance
                WHERE attendance_date=? AND class_id=? GROUP BY status
            """, (attendance_date, cls["id"]))
            for r in cur.fetchall():
                if r["status"] == "present":
                    total_present += r["c"]
                else:
                    total_absent += r["c"]
        else:
            pending.append(cls["name"])
    signoff = get_admin_signoff(attendance_date)
    conn.close()
    return {
        "date": attendance_date,
        "classes_total": len(classes),
        "classes_submitted": submitted,
        "pending_classes": pending,
        "present": total_present,
        "absent": total_absent,
        "enrolled": total_enrolled,
        "admin_signed": bool(signoff),
        "signoff": signoff,
    }

def get_previous_attendance(class_id, before_date):
    """Get the most recent attendance records for a class before a given date."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT attendance_date FROM attendance
        WHERE class_id=? AND attendance_date < ?
        ORDER BY attendance_date DESC LIMIT 1
    """, (class_id, before_date))
    row = cur.fetchone()
    if not row:
        conn.close()
        return None, []
    prev = row["attendance_date"]
    cur.execute("""
        SELECT learner_id, status, reason FROM attendance
        WHERE class_id=? AND attendance_date=?
    """, (class_id, prev))
    recs = [dict(r) for r in cur.fetchall()]
    conn.close()
    return prev, recs

def save_attendance_with_reasons(attendance_date, class_id, records, user_id):
    """records: [{learner_id, status, reason?}]"""
    conn = get_conn()
    cur = conn.cursor()
    from datetime import datetime
    now = datetime.now().isoformat(timespec="seconds")
    for rec in records:
        cur.execute("""
            INSERT INTO attendance (attendance_date, class_id, learner_id, status, reason, marked_by, marked_at)
            VALUES (?,?,?,?,?,?,?)
            ON CONFLICT(attendance_date, learner_id)
            DO UPDATE SET status=excluded.status, reason=excluded.reason,
                          marked_by=excluded.marked_by, marked_at=excluded.marked_at
        """, (attendance_date, class_id, rec["learner_id"], rec["status"],
              rec.get("reason") or None, user_id, now))
    cur.execute("""
        INSERT INTO daily_signatures (attendance_date, class_id, signed_by, signed_at)
        VALUES (?,?,?,?)
        ON CONFLICT(attendance_date, class_id)
        DO UPDATE SET signed_by=excluded.signed_by, signed_at=excluded.signed_at
    """, (attendance_date, class_id, user_id, now))
    conn.commit()
    conn.close()

def export_register_csv(attendance_date):
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

def get_weekly_summary(start_date, end_date):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT a.attendance_date, c.name as class_name,
               SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END) as present,
               SUM(CASE WHEN a.status='absent' THEN 1 ELSE 0 END) as absent
        FROM attendance a
        JOIN classes c ON c.id = a.class_id
        WHERE a.attendance_date >= ? AND a.attendance_date <= ?
        GROUP BY a.attendance_date, c.id
        ORDER BY a.attendance_date, c.sort_order
    """, (start_date, end_date))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows



# ---------- Audit ----------
def audit(user_id, action: str, detail: str = ""):
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.now().isoformat(timespec="seconds")
    cur.execute(
        "INSERT INTO audit_log (user_id, action, detail, created_at) VALUES (?,?,?,?)",
        (user_id, action, detail, now),
    )
    conn.commit()
    conn.close()

def get_audit_log(limit=100):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT a.*, u.full_name
        FROM audit_log a
        LEFT JOIN users u ON u.id = a.user_id
        ORDER BY a.created_at DESC
        LIMIT ?
    """, (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

# ---------- Announcements ----------
def add_announcement(title, body, user_id):
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.now().isoformat(timespec="seconds")
    cur.execute(
        "INSERT INTO announcements (title, body, created_by, created_at, active) VALUES (?,?,?,?,1)",
        (title.strip(), body.strip(), user_id, now),
    )
    conn.commit()
    aid = cur.lastrowid
    conn.close()
    return aid



def is_persistent_storage():
    """True if DB looks like it is on a mounted persistent volume."""
    p = os.path.abspath(DB_PATH)
    return p.startswith("/data/") or p.startswith("/var/data/") or bool(os.environ.get("ATTENDANCE_DB"))

def export_full_backup():
    """Export all critical tables to a JSON-serializable dict."""
    ensure_schema()
    conn = get_conn()
    cur = conn.cursor()
    data = {"version": 1, "exported_at": datetime.now().isoformat(timespec="seconds")}
    for table in ("classes", "users", "learners", "attendance", "daily_signatures",
                  "admin_signoff", "messages", "settings", "announcements", "audit_log", "reminder_log"):
        try:
            cur.execute(f"SELECT * FROM {table}")
            cols = [d[0] for d in cur.description]
            data[table] = [dict(zip(cols, row)) for row in cur.fetchall()]
        except Exception:
            data[table] = []
    conn.close()
    return data

def import_full_backup(data: dict, replace: bool = True):
    """Restore from export_full_backup(). replace=True clears tables first."""
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
                # delete in reverse dependency order
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
                placeholders = ",".join(["?"] * len(cols))
                col_list = ",".join(cols)
                for row in rows:
                    vals = [row.get(c) for c in cols]
                    try:
                        cur.execute(
                            f"INSERT OR REPLACE INTO {table} ({col_list}) VALUES ({placeholders})",
                            vals,
                        )
                    except Exception as e:
                        # try plain insert
                        try:
                            cur.execute(
                                f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})",
                                vals,
                            )
                        except Exception:
                            pass
            conn.commit()
        finally:
            conn.close()
    return _with_retry(_do)

def ensure_schema():
    """Create any missing tables/columns. Safe to call repeatedly."""
    conn = get_conn()
    cur = conn.cursor()
    tables = [
        """CREATE TABLE IF NOT EXISTS announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            created_by INTEGER,
            created_at TEXT NOT NULL,
            active INTEGER DEFAULT 1
        )""",
        """CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            detail TEXT,
            created_at TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_user INTEGER NOT NULL,
            to_user INTEGER,
            subject TEXT,
            body TEXT NOT NULL,
            created_at TEXT NOT NULL,
            read_at TEXT,
            is_broadcast INTEGER DEFAULT 0
        )""",
        """CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS admin_signoff (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            attendance_date TEXT NOT NULL UNIQUE,
            signed_by INTEGER NOT NULL,
            signed_at TEXT NOT NULL,
            notes TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS reminder_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            message TEXT,
            channel TEXT,
            created_at TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS daily_signatures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            attendance_date TEXT NOT NULL,
            class_id INTEGER NOT NULL,
            signed_by INTEGER,
            signed_at TEXT,
            UNIQUE(attendance_date, class_id)
        )""",
    ]
    for t in tables:
        try:
            cur.execute(t)
        except Exception:
            pass
    for stmt in [
        "ALTER TABLE classes ADD COLUMN theme TEXT DEFAULT 'ocean'",
        "ALTER TABLE users ADD COLUMN phone TEXT",
        "ALTER TABLE users ADD COLUMN active INTEGER DEFAULT 1",
        "ALTER TABLE attendance ADD COLUMN reason TEXT",
        "ALTER TABLE attendance ADD COLUMN status_detail TEXT",
    ]:
        try:
            cur.execute(stmt)
        except Exception:
            pass
    defaults = {
        "school_name": "Mispah Skool vir LSEN",
        "reminder_time": "07:30",
        "reminder_message": "Goeie more! Moet asseblief vandag se bywoning merk. Dankie.",
        "admin_display_name": "Administrator",
    }
    for k, v in defaults.items():
        try:
            cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?,?)", (k, v))
        except Exception:
            pass
    conn.commit()
    conn.close()


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
        rows = [dict(r) for r in cur.fetchall()]
    except Exception:
        rows = []
    conn.close()
    return rows

def deactivate_announcement(aid):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE announcements SET active=0 WHERE id=?", (aid,))
    conn.commit()
    conn.close()

# ---------- Enhanced attendance save with reason/late ----------
def save_attendance_v2(attendance_date: str, class_id: int, records: list, user_id: int):
    """records: list of {learner_id, status: present|late|absent, reason?: str}"""
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.now().isoformat(timespec="seconds")
    for rec in records:
        status = rec["status"]
        # Map late -> present for legacy counts but keep detail
        legacy = "absent" if status == "absent" else "present"
        reason = rec.get("reason") or ""
        cur.execute(
            """INSERT INTO attendance (attendance_date, class_id, learner_id, status, marked_by, marked_at, reason, status_detail)
               VALUES (?,?,?,?,?,?,?,?)
               ON CONFLICT(attendance_date, learner_id)
               DO UPDATE SET status=excluded.status, marked_by=excluded.marked_by, marked_at=excluded.marked_at,
                             reason=excluded.reason, status_detail=excluded.status_detail""",
            (attendance_date, class_id, rec["learner_id"], legacy, user_id, now, reason, status),
        )
    cur.execute(
        """INSERT INTO daily_signatures (attendance_date, class_id, signed_by, signed_at)
           VALUES (?,?,?,?)
           ON CONFLICT(attendance_date, class_id)
           DO UPDATE SET signed_by=excluded.signed_by, signed_at=excluded.signed_at""",
        (attendance_date, class_id, user_id, now),
    )
    conn.commit()
    conn.close()
    audit(user_id, "mark_attendance", f"class={class_id} date={attendance_date} n={len(records)}")

def get_class_attendance_detail_v2(attendance_date: str, class_id: int):
    learners = get_learners_by_class(class_id)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """SELECT learner_id, status, status_detail, reason FROM attendance
           WHERE attendance_date=? AND class_id=?""",
        (attendance_date, class_id),
    )
    att = {r["learner_id"]: dict(r) for r in cur.fetchall()}
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

def get_learner_history(learner_id: int, limit=60):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT a.*, c.name AS class_name
        FROM attendance a
        JOIN classes c ON c.id = a.class_id
        WHERE a.learner_id=?
        ORDER BY a.attendance_date DESC
        LIMIT ?
    """, (learner_id, limit))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def get_today_stats():
    today = date.today().isoformat()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT
          COALESCE(SUM(CASE WHEN status='present' THEN 1 ELSE 0 END), 0) AS present,
          COALESCE(SUM(CASE WHEN status='absent' THEN 1 ELSE 0 END), 0) AS absent,
          COUNT(*) AS marked
        FROM attendance WHERE attendance_date=?
    """, (today,))
    row = dict(cur.fetchone() or {})
    cur.execute("SELECT COUNT(*) as c FROM learners WHERE active=1")
    row["enrolled"] = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(DISTINCT class_id) as c FROM daily_signatures WHERE attendance_date=?", (today,))
    row["classes_submitted"] = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) as c FROM classes")
    row["classes_total"] = cur.fetchone()["c"]
    conn.close()
    return row

def search_learners(q: str):
    conn = get_conn()
    cur = conn.cursor()
    like = f"%{q.strip()}%"
    cur.execute("""
        SELECT l.*, c.name AS class_name FROM learners l
        JOIN classes c ON c.id = l.class_id
        WHERE l.active=1 AND (l.first_name LIKE ? OR l.last_name LIKE ? OR c.name LIKE ?)
        ORDER BY l.last_name, l.first_name LIMIT 40
    """, (like, like, like))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def export_register_csv(attendance_date: str):
    """Return CSV string of the daily register."""
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
    cur.execute("""
        SELECT a.attendance_date, c.name AS class_name, l.first_name, l.last_name, l.gender,
               a.status, COALESCE(a.status_detail, a.status) AS detail, COALESCE(a.reason,'') AS reason
        FROM attendance a
        JOIN learners l ON l.id = a.learner_id
        JOIN classes c ON c.id = a.class_id
        WHERE a.attendance_date >= date('now', ?)
        ORDER BY a.attendance_date DESC, c.sort_order, l.last_name
    """, (f"-{days} days",))
    rows = cur.fetchall()
    conn.close()
    lines = ["Datum,Klas,Voornaam,Van,Geslag,Status,Detail,Rede"]
    for r in rows:
        lines.append(
            f'{r["attendance_date"]},"{r["class_name"]}","{r["first_name"]}","{r["last_name"]}",{r["gender"]},{r["status"]},{r["detail"]},"{r["reason"]}"'
        )
    return "\n".join(lines)

if __name__ == "__main__":
    init_db()
    print("Done.")
