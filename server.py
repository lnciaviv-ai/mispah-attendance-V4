#!/usr/bin/env python3
"""
Mispah Skool – Digital Daily Attendance Register (Modern Edition)
"""

import json
import os
import mimetypes
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from http.cookies import SimpleCookie
from datetime import date, datetime
import secrets
import html

import db

SESSIONS = {}
PORT = int(os.environ.get("PORT", 8080))
HOST = "0.0.0.0"
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

def make_session(user_id: int) -> str:
    sid = secrets.token_hex(16)
    SESSIONS[sid] = user_id
    return sid

def get_session_user(cookie_header: str):
    if not cookie_header:
        return None
    cookie = SimpleCookie()
    try:
        cookie.load(cookie_header)
    except Exception:
        return None
    if "session" not in cookie:
        return None
    uid = SESSIONS.get(cookie["session"].value)
    if not uid:
        return None
    return db.get_user(uid)

def redirect(handler, location: str, status=302):
    handler.send_response(status)
    handler.send_header("Location", location)
    handler.end_headers()

def set_cookie(handler, name, value, max_age=86400*7):
    handler.send_header("Set-Cookie", f"{name}={value}; Path=/; HttpOnly; SameSite=Lax; Max-Age={max_age}")

def clear_cookie(handler, name):
    handler.send_header("Set-Cookie", f"{name}=; Path=/; Max-Age=0")

def html_escape(s):
    return html.escape(str(s) if s is not None else "")

def today_str():
    return date.today().isoformat()

def get_theme_css(theme_key: str = "ocean"):
    t = db.THEMES.get(theme_key, db.THEMES["ocean"])
    return f"""
:root {{
  --primary: {t['primary']};
  --primary-dark: {t['primary_dark']};
  --accent: {t['accent']};
  --bg: {t['bg']};
  --card: {t['card']};
  --text: {t['text']};
  --border: #d0d7de;
  --muted: #6b7280;
  --danger: #c0392b;
  --success: #27ae60;
}}
"""

BASE_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: 'Segoe UI', system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.55;
  min-height: 100vh;
}
header {
  background: linear-gradient(135deg, var(--primary), var(--primary-dark));
  color: white;
  padding: 0.75rem 1.5rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.75rem;
  box-shadow: 0 4px 20px rgba(0,0,0,0.12);
  position: sticky;
  top: 0;
  z-index: 100;
}
.header-brand {
  display: flex;
  align-items: center;
  gap: 0.85rem;
}
.header-brand img {
  height: 52px;
  width: auto;
  background: white;
  border-radius: 50%;
  padding: 3px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.2);
}
.header-brand h1 { font-size: 1.2rem; font-weight: 700; letter-spacing: -0.02em; }
.header-brand .sub { font-size: 0.78rem; opacity: 0.9; }
nav { display: flex; flex-wrap: wrap; gap: 0.35rem; }
nav a {
  color: white;
  text-decoration: none;
  font-size: 0.88rem;
  padding: 0.4rem 0.75rem;
  border-radius: 6px;
  transition: background 0.15s;
  font-weight: 500;
}
nav a:hover { background: rgba(255,255,255,0.18); }
.container { max-width: 1140px; margin: 1.5rem auto; padding: 0 1rem 2.5rem; }
.card {
  background: var(--card);
  border-radius: 14px;
  box-shadow: 0 4px 24px rgba(0,0,0,0.06);
  padding: 1.5rem 1.75rem;
  margin-bottom: 1.4rem;
  border: 1px solid rgba(0,0,0,0.04);
}
h2 { font-size: 1.25rem; margin-bottom: 1rem; color: var(--primary); font-weight: 700; }
h3 { font-size: 1.05rem; margin: 1.25rem 0 0.75rem; color: var(--primary-dark); }
label { display: block; font-weight: 600; margin-bottom: 0.3rem; font-size: 0.88rem; }
input[type=text], input[type=password], input[type=date], select, textarea {
  width: 100%;
  padding: 0.6rem 0.85rem;
  border: 1.5px solid var(--border);
  border-radius: 8px;
  font-size: 0.98rem;
  margin-bottom: 0.9rem;
  transition: border-color 0.15s, box-shadow 0.15s;
  background: #fff;
}
input:focus, select:focus, textarea:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(26,82,118,0.15);
}
button, .btn {
  display: inline-block;
  background: var(--primary);
  color: white;
  border: none;
  padding: 0.6rem 1.25rem;
  border-radius: 8px;
  font-size: 0.92rem;
  cursor: pointer;
  text-decoration: none;
  font-weight: 600;
  transition: transform 0.1s, background 0.15s, box-shadow 0.15s;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}
button:hover, .btn:hover { background: var(--primary-dark); transform: translateY(-1px); }
.btn-success { background: var(--success); }
.btn-success:hover { background: #1e8449; }
.btn-danger { background: var(--danger); }
.btn-danger:hover { background: #922b21; }
.btn-outline {
  background: transparent;
  border: 1.5px solid var(--primary);
  color: var(--primary);
  box-shadow: none;
}
.btn-outline:hover { background: var(--primary); color: white; }
.btn-sm { padding: 0.35rem 0.7rem; font-size: 0.82rem; }
.btn-lg { padding: 0.75rem 1.5rem; font-size: 1.05rem; }
.alert {
  padding: 0.85rem 1.1rem;
  border-radius: 10px;
  margin-bottom: 1.1rem;
  font-size: 0.95rem;
}
.alert-success { background: #d5f5e3; color: #145a32; border: 1px solid #a9dfbf; }
.alert-error { background: #fadbd8; color: #922b21; border: 1px solid #f5b7b1; }
.alert-info { background: #d6eaf8; color: #1a5276; border: 1px solid #aed6f1; }
.alert-warning { background: #fef9e7; color: #7d6608; border: 1px solid #f9e79f; }
table { width: 100%; border-collapse: collapse; font-size: 0.93rem; }
th, td { padding: 0.7rem 0.85rem; text-align: left; border-bottom: 1px solid var(--border); }
th { background: color-mix(in srgb, var(--primary) 12%, white); font-weight: 700; color: var(--primary); }
tr:hover { background: color-mix(in srgb, var(--primary) 4%, white); }
.badge {
  display: inline-block;
  padding: 0.22rem 0.55rem;
  border-radius: 6px;
  font-size: 0.78rem;
  font-weight: 700;
}
.badge-present { background: #d5f5e3; color: #145a32; }
.badge-absent { background: #fadbd8; color: #922b21; }
.badge-unsigned { background: #fef9e7; color: #7d6608; }
.badge-signed { background: #d5f5e3; color: #145a32; }
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
.grid-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 1rem; }
@media (max-width: 750px) {
  .grid-2, .grid-3 { grid-template-columns: 1fr; }
  header { flex-direction: column; align-items: flex-start; }
  .header-brand img { height: 44px; }
}
.learner-row {
  display: flex;
  align-items: center;
  padding: 0.7rem 0.6rem;
  border-bottom: 1px solid var(--border);
  gap: 0.85rem;
  transition: background 0.1s;
}
.learner-row:hover { background: color-mix(in srgb, var(--primary) 5%, white); }
.learner-row label.name { margin: 0; flex: 1; cursor: pointer; font-weight: 500; }
.status-toggle { display: flex; gap: 0.4rem; }
.status-toggle input { display: none; }
.status-toggle span {
  padding: 0.35rem 0.8rem;
  border-radius: 6px;
  border: 1.5px solid var(--border);
  font-size: 0.84rem;
  cursor: pointer;
  user-select: none;
  font-weight: 600;
  transition: all 0.15s;
}
.status-toggle input:checked + span.present { background: #27ae60; color: white; border-color: #27ae60; }
.status-toggle input:checked + span.absent { background: #c0392b; color: white; border-color: #c0392b; }
.theme-picker {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 0.75rem;
  margin: 1rem 0;
}
.theme-option {
  border: 2px solid var(--border);
  border-radius: 10px;
  padding: 0.75rem;
  cursor: pointer;
  text-align: center;
  transition: all 0.15s;
  background: white;
}
.theme-option:hover { border-color: var(--primary); transform: translateY(-2px); }
.theme-option.selected { border-color: var(--primary); box-shadow: 0 0 0 3px color-mix(in srgb, var(--primary) 25%, transparent); }
.theme-swatch {
  height: 28px;
  border-radius: 6px;
  margin-bottom: 0.4rem;
}
.print-header {
  text-align: center;
  margin-bottom: 1.25rem;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
}
.print-header img {
  height: 90px;
  width: auto;
}
.print-header h1 { font-size: 1.5rem; color: #000; margin: 0; }
.print-header p { font-size: 0.95rem; margin: 0; }
.signoff-box {
  background: color-mix(in srgb, var(--success) 12%, white);
  border: 2px solid var(--success);
  border-radius: 12px;
  padding: 1.25rem;
  margin: 1.25rem 0;
}
.signoff-box.pending {
  background: color-mix(in srgb, #f39c12 12%, white);
  border-color: #f39c12;
}

body.dark {
  --bg: #1a1d23;
  --card: #252830;
  --text: #e8eaed;
  --border: #3a3f4b;
  --muted: #9aa0a6;
}
body.dark input, body.dark select, body.dark textarea {
  background: #1a1d23;
  color: var(--text);
  border-color: var(--border);
}
body.dark th { background: #2c313c; }
body.dark tr:hover { background: #2c313c; }

@media print {
  header, nav, .no-print { display: none !important; }
  body { background: white; }
  .card { box-shadow: none; border: 1px solid #ccc; }
  table { font-size: 11pt; }
  .print-header img { height: 70px; }
}
"""

def page(title: str, body: str, user=None, theme_key="ocean", extra_head=""):
    theme_css = get_theme_css(theme_key)
    nav = ""
    if user:
        admin_links = ""
        if user["role"] == "admin":
            admin_links = """
              <a href="/admin">Register</a>
              <a href="/admin/learners">Leerders</a>
              <a href="/admin/teachers">Onderwysers</a>
              <a href="/admin/classes">Klasse</a>
              <a href="/admin/trends">Neigings</a>
              <a href="/admin/reminders">Herinneringe</a>
              <a href="/admin/settings">Instellings</a>
              <a href="/admin/announcements">Aankondigings</a>
              <a href="/admin/audit">Oudit</a>
              <a href="/admin/audit">Oudit</a>
            """
        nav = f"""
        <nav>
          <a href="/">Tuis</a>
          {admin_links}
          <a href="/messages">Boodskappe</a>
          <a href="/logout">Teken uit</a>
        </nav>
        """
    logo = '<img src="/static/logo.png" alt="Mispah Skool logo">'
    return f"""<!DOCTYPE html>
<html lang="af">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html_escape(title)} – Mispah Skool</title>
  <style>{theme_css}{BASE_CSS}</style>
  {extra_head}
</head>
<body>
  <header>
    <div class="header-brand">
      {logo}
      <div>
        <h1>Mispah Skool</h1>
        <div class="sub">Daaglikse Bywoningsregister · Elim</div>
      </div>
    </div>
    {nav}
  </header>
  <div class="container">
    {body}
  </div>
</body>
</html>"""

def login_page(error=None):
    err = f'<div class="alert alert-error">{html_escape(error)}</div>' if error else ""
    body = f"""
    <div class="card" style="max-width:440px;margin:3rem auto;">
      <div style="text-align:center;margin-bottom:1.5rem;">
        <img src="/static/logo.png" alt="Logo" style="height:100px;margin-bottom:0.75rem;">
        <h2 style="margin:0;">Teken in</h2>
        <p style="color:var(--muted);font-size:0.9rem;">Daaglikse Bywoningsregister</p>
      </div>
      {err}
      <form method="POST" action="/login">
        <label>Gebruikersnaam</label>
        <input type="text" name="username" required autofocus placeholder="bv. admin of maree">
        <label>Wagwoord</label>
        <input type="password" name="password" required>
        <button type="submit" class="btn-lg" style="width:100%;margin-top:0.5rem;">Teken in</button>
      </form>
      <p style="margin-top:1.5rem;font-size:0.82rem;color:var(--muted);text-align:center;">
        Demo: <code>admin</code> / <code>admin123</code> · Onderwysers: <code>maree</code> e.a. / <code>teacher123</code>
      </p>
    </div>
    """
    return page("Teken in", body)

def teacher_home(user, msg=None):
    classes = db.get_all_classes()
    my_class = db.get_class(user["class_id"]) if user.get("class_id") else None
    theme = my_class["theme"] if my_class else "ocean"
    msg_html = f'<div class="alert alert-success">{html_escape(msg)}</div>' if msg else ""

    stats = db.get_today_stats()
    present = stats.get("present") or 0
    absent = stats.get("absent") or 0
    submitted = stats.get("classes_submitted") or 0
    total_c = stats.get("classes_total") or 0
    pct = round(100 * present / (present + absent), 1) if (present + absent) else 0

    anns = db.get_active_announcements()
    ann_html = ""
    for a in anns:
        ann_html += (
            '<div class="alert alert-info" style="margin-bottom:0.6rem;">'
            f'<strong>{html_escape(a["title"])}</strong><br>{html_escape(a["body"])}'
            f'<div style="font-size:0.8rem;color:var(--muted);margin-top:0.3rem;">'
            f'{html_escape(a.get("full_name") or "")} · {html_escape((a.get("created_at") or "")[:16])}</div></div>'
        )

    own = ""
    if my_class:
        own = f"""
        <div class="card" style="border-left:5px solid var(--accent);">
          <h2>Jou klas</h2>
          <p style="margin-bottom:1rem;font-size:1.05rem;">
            <strong>{html_escape(my_class['name'])}</strong><br>
            <span style="color:var(--muted);">{html_escape(my_class['teacher_name'])}</span>
          </p>
          <a class="btn btn-success btn-lg" href="/mark?class_id={my_class['id']}&date={today_str()}">Merk bywoning vandag</a>
          <a class="btn btn-outline" href="/theme?class_id={my_class['id']}" style="margin-left:0.5rem;">Kies tema</a>
        </div>
        """

    rows = ""
    for c in classes:
        rows += f"""
        <tr>
          <td><strong>{html_escape(c['name'])}</strong><br><small style="color:var(--muted)">{html_escape(c['teacher_name'])}</small></td>
          <td>
            <a class="btn btn-sm" href="/mark?class_id={c['id']}&date={today_str()}">Merk</a>
            <a class="btn btn-sm btn-outline" href="/view?class_id={c['id']}&date={today_str()}">Sien</a>
          </td>
        </tr>"""

    body = f"""
    {msg_html}
    <div class="grid-3" style="margin-bottom:1.4rem;">
      <div class="card" style="margin:0;text-align:center;padding:1.2rem;">
        <div style="font-size:1.8rem;font-weight:800;color:var(--success);">{present}</div>
        <div style="font-size:0.85rem;color:var(--muted);">Teenwoordig vandag</div>
      </div>
      <div class="card" style="margin:0;text-align:center;padding:1.2rem;">
        <div style="font-size:1.8rem;font-weight:800;color:var(--danger);">{absent}</div>
        <div style="font-size:0.85rem;color:var(--muted);">Afwesig vandag</div>
      </div>
      <div class="card" style="margin:0;text-align:center;padding:1.2rem;">
        <div style="font-size:1.8rem;font-weight:800;color:var(--primary);">{submitted}/{total_c}</div>
        <div style="font-size:0.85rem;color:var(--muted);">Klasse ingedien · {pct}%</div>
      </div>
    </div>
    {ann_html}
    <div class="card">
      <h2>Welkom, {html_escape(user['full_name'])}</h2>
      <p style="color:var(--muted);">Kies 'n klas om bywoning te merk of te bekyk.</p>
      <form method="GET" action="/search" style="margin-top:0.75rem;display:flex;gap:0.5rem;flex-wrap:wrap;">
        <input type="text" name="q" placeholder="Soek leerder..." style="margin:0;flex:1;min-width:180px;">
        <button type="submit" class="btn-sm">Soek</button>
      </form>
    </div>
    {own}
    <div class="card">
      <h2>Alle klasse</h2>
      <table>
        <thead><tr><th>Klas</th><th>Aksie</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
    """
    return page("Tuis", body, user, theme)


def mark_page(user, class_id: int, attendance_date: str, msg=None, error=None):
    cls = db.get_class(class_id)
    if not cls:
        return page("Fout", '<div class="alert alert-error">Klas nie gevind nie.</div>', user)
    theme = cls.get("theme") or "ocean"
    learners = db.get_class_attendance_detail_v2(attendance_date, class_id)
    msg_html = ""
    if msg:
        msg_html = f'<div class="alert alert-success">{html_escape(msg)}</div>'
    if error:
        msg_html = f'<div class="alert alert-error">{html_escape(error)}</div>'

    rows = ""
    for l in learners:
        st = l.get("status")
        present_c = "checked" if st in ("present", None) else ""
        late_c = "checked" if st == "late" else ""
        absent_c = "checked" if st == "absent" else ""
        reason = html_escape(l.get("reason") or "")
        rows += f"""
        <div class="learner-row" style="flex-wrap:wrap;">
          <label class="name" style="min-width:140px;">{html_escape(l['first_name'])} {html_escape(l['last_name'])}
            <span style="color:var(--muted);font-size:0.8rem;font-weight:400;">({l['gender']})</span>
          </label>
          <div class="status-toggle">
            <label>
              <input type="radio" name="status_{l['id']}" value="present" {present_c}>
              <span class="present">Teenwoordig</span>
            </label>
            <label>
              <input type="radio" name="status_{l['id']}" value="late" {late_c}>
              <span class="present" style="border-color:#f39c12;">Laat</span>
            </label>
            <label>
              <input type="radio" name="status_{l['id']}" value="absent" {absent_c}>
              <span class="absent">Afwesig</span>
            </label>
          </div>
          <input type="text" name="reason_{l['id']}" value="{reason}" placeholder="Rede (opsioneel)"
                 style="flex:1;min-width:120px;margin:0;padding:0.35rem 0.6rem;font-size:0.85rem;">
        </div>
        """

    if not learners:
        rows = '<p class="alert alert-info">Geen aktiewe leerders in hierdie klas nie.</p>'

    body = f"""
    {msg_html}
    <div class="card">
      <h2>Merk bywoning – {html_escape(cls['name'])}</h2>
      <p style="margin-bottom:1rem;color:var(--muted);">
        Opvoeder: {html_escape(cls['teacher_name'])} · Datum: <strong>{html_escape(attendance_date)}</strong>
      </p>
      <form method="POST" action="/mark" id="markForm">
        <input type="hidden" name="class_id" value="{class_id}">
        <input type="hidden" name="date" value="{html_escape(attendance_date)}">
        <div style="margin-bottom:1rem;display:flex;flex-wrap:wrap;gap:0.75rem;align-items:center;" class="no-print">
          <div>
            <label style="display:inline;">Datum</label>
            <input type="date" value="{html_escape(attendance_date)}"
                   onchange="window.location='/mark?class_id={class_id}&date='+this.value"
                   style="width:auto;display:inline-block;margin-left:0.4rem;margin-bottom:0;">
          </div>
          <button type="button" class="btn btn-sm btn-success" onclick="markAll('present')">✓ Almal teenwoordig</button>
          <button type="button" class="btn btn-sm btn-outline" onclick="markAll('absent')">Almal afwesig</button>
        </div>
        <div style="border:1px solid var(--border);border-radius:10px;overflow:hidden;margin-bottom:1.25rem;">
          {rows}
        </div>
        <button type="submit" class="btn-success btn-lg">Stoor bywoning &amp; teken</button>
        <a href="/" class="btn btn-outline" style="margin-left:0.5rem;">Terug</a>
      </form>
    </div>
    <script>
    function markAll(status) {{
      document.querySelectorAll('#markForm input[type=radio]').forEach(r => {{
        if (r.value === status) r.checked = true;
      }});
    }}
    // style late when checked
    document.querySelectorAll('input[value=late]').forEach(inp => {{
      inp.addEventListener('change', () => {{
        if (inp.checked) inp.nextElementSibling.style.background = '#f39c12';
      }});
    }});
    </script>
    """
    return page(f"Merk – {cls['name']}", body, user, theme)


def view_class_page(user, class_id: int, attendance_date: str):
    cls = db.get_class(class_id)
    if not cls:
        return page("Fout", '<div class="alert alert-error">Klas nie gevind nie.</div>', user)
    theme = cls.get("theme") or "ocean"
    learners = db.get_class_attendance_detail(attendance_date, class_id)
    rows = ""
    present = absent = 0
    for l in learners:
        st = l.get("status")
        if st == "present":
            present += 1
            badge = '<span class="badge badge-present">Teenwoordig</span>'
        elif st == "absent":
            absent += 1
            badge = '<span class="badge badge-absent">Afwesig</span>'
        else:
            badge = '<span class="badge badge-unsigned">Nog nie gemerk</span>'
        rows += f"""
        <tr>
          <td>{html_escape(l['first_name'])} {html_escape(l['last_name'])}</td>
          <td>{l['gender']}</td>
          <td>{badge}</td>
        </tr>"""

    body = f"""
    <div class="card">
      <h2>{html_escape(cls['name'])} – {html_escape(attendance_date)}</h2>
      <p>Teenwoordig: <strong>{present}</strong> · Afwesig: <strong>{absent}</strong></p>
      <table style="margin-top:1rem;">
        <thead><tr><th>Leerder</th><th>Geslag</th><th>Status</th></tr></thead>
        <tbody>{rows or '<tr><td colspan=3>Geen data</td></tr>'}</tbody>
      </table>
      <p style="margin-top:1.25rem;">
        <a class="btn" href="/mark?class_id={class_id}&date={attendance_date}">Wysig</a>
        <a class="btn btn-outline" href="/">Terug</a>
      </p>
    </div>
    """
    return page("Sien bywoning", body, user, theme)

def theme_page(user, class_id: int, msg=None):
    cls = db.get_class(class_id)
    if not cls:
        return page("Fout", '<div class="alert alert-error">Klas nie gevind nie.</div>', user)
    # Only allow teacher of this class or admin
    if user["role"] != "admin" and user.get("class_id") != class_id:
        return page("Fout", '<div class="alert alert-error">Geen toegang.</div>', user)
    current = cls.get("theme") or "ocean"
    msg_html = f'<div class="alert alert-success">{html_escape(msg)}</div>' if msg else ""

    options = ""
    for key, t in db.THEMES.items():
        sel = "selected" if key == current else ""
        options += f"""
        <label class="theme-option {sel}">
          <input type="radio" name="theme" value="{key}" {"checked" if key==current else ""} style="display:none;">
          <div class="theme-swatch" style="background:linear-gradient(90deg,{t['primary']},{t['accent']});"></div>
          <strong>{html_escape(t['name'])}</strong>
        </label>
        """

    body = f"""
    {msg_html}
    <div class="card">
      <h2>Kies tema vir {html_escape(cls['name'])}</h2>
      <p style="color:var(--muted);margin-bottom:1rem;">Die tema verander die kleure van jou klas se bladsye.</p>
      <form method="POST" action="/theme">
        <input type="hidden" name="class_id" value="{class_id}">
        <div class="theme-picker">{options}</div>
        <button type="submit" class="btn-success">Stoor tema</button>
        <a href="/" class="btn btn-outline" style="margin-left:0.5rem;">Terug</a>
      </form>
    </div>
    <script>
      document.querySelectorAll('.theme-option').forEach(el => {{
        el.addEventListener('click', () => {{
          document.querySelectorAll('.theme-option').forEach(o => o.classList.remove('selected'));
          el.classList.add('selected');
          el.querySelector('input').checked = true;
        }});
      }});
    </script>
    """
    return page("Tema", body, user, current)

def admin_dashboard(user, attendance_date: str = None):
    if not attendance_date:
        attendance_date = today_str()

    persist_ok = db.is_persistent_storage()
    persist_html = ""
    if not persist_ok:
        persist_html = """
        <div class="alert alert-error no-print">
          <strong>Belangrik – data kan verdwyn!</strong><br>
          Hierdie diens hardloop sonder permanente berging. Op Render se gratis plan word die databasis
          uitgevee wanneer die diens slaap (na ~15 min stilte) of herbegin.<br><br>
          <strong>Oplossing:</strong> Sit ’n Persistent Disk by op Render (mount pad <code>/data</code>)
          en stel environment variable <code>ATTENDANCE_DB=/data/attendance.db</code>.
          Of laai gereeld ’n rugsteun af onder <a href="/admin/settings">Instellings</a>.
        </div>
        """

    register = db.get_full_daily_register(attendance_date)
    signoff = db.get_admin_signoff(attendance_date)

    total_seuns = total_dogters = total_all = 0
    all_signed = True
    for r in register:
        if r["seuns"] is not None:
            total_seuns += r["seuns"]
            total_dogters += r["dogters"]
            total_all += r["totaal"]
        if not r["signed"]:
            all_signed = False

    rows = ""
    for r in register:
        cls = r["class"]
        if r["seuns"] is None:
            seuns = dogters = totaal = "—"
            absent = "—"
            signed = '<span class="badge badge-unsigned">Nie ingedien</span>'
        else:
            seuns = r["seuns"]
            dogters = r["dogters"]
            totaal = r["totaal"]
            absent = ", ".join(r["absent_names"]) if r["absent_names"] else "—"
            signed = '<span class="badge badge-signed">Geteken</span>' if r["signed"] else '<span class="badge badge-unsigned">Nie geteken</span>'

        rows += f"""
        <tr>
          <td>{html_escape(cls['name'])}<br><small style="color:var(--muted)">{html_escape(cls['teacher_name'])}</small></td>
          <td style="text-align:center;">{seuns}</td>
          <td style="text-align:center;">{dogters}</td>
          <td style="text-align:center;font-weight:700;">{totaal}</td>
          <td style="font-size:0.88rem;">{html_escape(absent)}</td>
          <td>{signed}</td>
          <td class="no-print">
            <a class="btn btn-sm" href="/mark?class_id={cls['id']}&date={attendance_date}">Merk</a>
          </td>
        </tr>"""

    # Sign-off section
    if signoff:
        signoff_html = f"""
        <div class="signoff-box">
          <strong>✓ Register geteken deur admin</strong><br>
          <span style="font-size:1.1rem;font-weight:700;">{html_escape(db.get_setting("admin_display_name") or signoff["full_name"])}</span><br>
          {html_escape(signoff['full_name'])} · {html_escape(signoff['signed_at'][:16].replace('T',' '))}
          {f"<br><em>{html_escape(signoff.get('notes') or '')}</em>" if signoff.get('notes') else ""}
        </div>
        <button type="button" class="btn btn-lg no-print" onclick="window.print()">🖨 Druk finale register</button>
        """
    else:
        signoff_html = f"""
        <div class="signoff-box pending no-print">
          <strong>Admin moet die register teken voor druk</strong>
          <form method="POST" action="/admin/signoff" style="margin-top:0.75rem;">
            <input type="hidden" name="date" value="{html_escape(attendance_date)}">
            <label>Notas (opsioneel)</label>
            <textarea name="notes" rows="2" placeholder="Enige opmerkings..."></textarea>
            <button type="submit" class="btn-success btn-lg">✓ Teken register af</button>
          </form>
        </div>
        <p class="no-print" style="color:var(--muted);font-size:0.9rem;">Druk word eers beskikbaar nadat jy die register geteken het.</p>
        """

    body = f"""
    {persist_html}
    <div class="card no-print">
      <h2>Admin – Daaglikse register</h2>
      <form method="GET" action="/admin" style="display:flex;gap:0.75rem;align-items:flex-end;flex-wrap:wrap;">
        <div>
          <label>Datum</label>
          <input type="date" name="date" value="{html_escape(attendance_date)}" style="margin:0;width:auto;">
        </div>
        <button type="submit">Wys</button>
        <a class="btn btn-outline" href="/admin/learners">Leerders</a>
        <a class="btn btn-outline" href="/admin/export?kind=register&date={html_escape(attendance_date)}">CSV Register</a>
        <a class="btn btn-outline" href="/admin/export?kind=all">CSV 90 dae</a>
        <a class="btn btn-outline" href="/admin/teachers">Onderwysers</a>
      </form>
    </div>

    <div class="card">
      <div class="print-header">
        <img src="/static/logo.png" alt="Mispah Skool logo">
        <h1>{html_escape(db.get_setting("school_name", "MISPAH SKOOL VIR LSEN"))}</h1>
        <p>Daaglikse Leerder Bywoningsregister</p>
        <p><strong>Datum: {html_escape(attendance_date)}</strong></p>
      </div>
      <table>
        <thead>
          <tr>
            <th>KLAS</th>
            <th style="text-align:center;">SEUNS</th>
            <th style="text-align:center;">DOGTERS</th>
            <th style="text-align:center;">TOTAAL</th>
            <th>NAME VAN LEERDERS AFWESIG</th>
            <th>OPVOEDER</th>
            <th class="no-print">Aksie</th>
          </tr>
        </thead>
        <tbody>
          {rows}
          <tr style="font-weight:700;background:color-mix(in srgb, var(--primary) 10%, white);">
            <td>TOTAAL</td>
            <td style="text-align:center;">{total_seuns}</td>
            <td style="text-align:center;">{total_dogters}</td>
            <td style="text-align:center;">{total_all}</td>
            <td colspan="3"></td>
          </tr>
        </tbody>
      </table>
      {signoff_html}
    </div>
    """
    return page("Admin Register", body, user)

def learners_admin_page(user, msg=None, error=None):
    learners = db.get_all_learners(active_only=False)
    classes = db.get_all_classes()
    msg_html = ""
    if msg:
        msg_html = f'<div class="alert alert-success">{html_escape(msg)}</div>'
    if error:
        msg_html = f'<div class="alert alert-error">{html_escape(error)}</div>'

    class_options = "".join(f'<option value="{c["id"]}">{html_escape(c["name"])}</option>' for c in classes)

    rows = ""
    for l in learners:
        status = "Aktief" if l["active"] else "Gedeaktiveer"
        rows += f"""
        <tr>
          <td>{html_escape(l['first_name'])} {html_escape(l['last_name'])}</td>
          <td>{html_escape(l['class_name'])}</td>
          <td>{l['gender']}</td>
          <td>{status}</td>
          <td>
            <a class="btn btn-sm btn-outline" href="/admin/learners?edit={l['id']}">Wysig</a>
            {"<a class='btn btn-sm' href='/admin/learners?deactivate=" + str(l['id']) + "'>Deaktiveer</a>" if l["active"] else ""}
            <a class="btn btn-sm btn-danger" href="/admin/learners?delete={l['id']}"
               onclick="return confirm('PERMANENT uitvee? Hierdie aksie kan nie ontdoen word nie.')">Verwyder</a>
          </td>
        </tr>"""

    body = f"""
    {msg_html}
    <div class="card">
      <h2>Bestuur leerders</h2>
      <p style="color:var(--muted);margin-bottom:1rem;">
        Voeg nuwe leerders by of verwyder hulle permanent. Deaktiveer as die leerder die skool verlaat het maar jy die geskiedenis wil behou.
      </p>
      <h3>Voeg nuwe leerder by</h3>
      <form method="POST" action="/admin/learners" class="grid-2">
        <input type="hidden" name="action" value="add">
        <div>
          <label>Voornaam</label>
          <input type="text" name="first_name" required>
        </div>
        <div>
          <label>Van</label>
          <input type="text" name="last_name" required>
        </div>
        <div>
          <label>Klas</label>
          <select name="class_id" required>{class_options}</select>
        </div>
        <div>
          <label>Geslag</label>
          <select name="gender" required>
            <option value="seun">Seun</option>
            <option value="dogter">Dogter</option>
          </select>
        </div>
<div style="grid-column:1/-1;">
          <button type="submit" class="btn-success">Voeg leerder by</button>
        </div>
      </form>
    </div>
    <div class="card">
      <h2>Alle leerders</h2>
      <table>
        <thead><tr><th>Naam</th><th>Klas</th><th>Geslag</th><th>Status</th><th>Aksie</th></tr></thead>
        <tbody>{rows or '<tr><td colspan=5>Geen leerders nie</td></tr>'}</tbody>
      </table>
    </div>
    <p><a class="btn btn-outline" href="/admin">← Terug na register</a></p>
    """
    return page("Leerders", body, user)

def edit_learner_page(user, learner_id: int):
    learners = db.get_all_learners(active_only=False)
    learner = next((l for l in learners if l["id"] == learner_id), None)
    if not learner:
        return learners_admin_page(user, error="Leerder nie gevind nie.")
    classes = db.get_all_classes()
    class_options = "".join(
        f'<option value="{c["id"]}" {"selected" if c["id"]==learner["class_id"] else ""}>{html_escape(c["name"])}</option>'
        for c in classes
    )
    body = f"""
    <div class="card" style="max-width:520px;">
      <h2>Wysig leerder</h2>
      <form method="POST" action="/admin/learners">
        <input type="hidden" name="action" value="edit">
        <input type="hidden" name="learner_id" value="{learner_id}">
        <label>Voornaam</label>
        <input type="text" name="first_name" value="{html_escape(learner['first_name'])}" required>
        <label>Van</label>
        <input type="text" name="last_name" value="{html_escape(learner['last_name'])}" required>
        <label>Klas</label>
        <select name="class_id" required>{class_options}</select>
        <label>Geslag</label>
        <select name="gender" required>
          <option value="seun" {"selected" if learner["gender"]=="seun" else ""}>Seun</option>
          <option value="dogter" {"selected" if learner["gender"]=="dogter" else ""}>Dogter</option>
        </select>
        <label>Aktief</label>
        <select name="active">
          <option value="1" {"selected" if learner["active"] else ""}>Ja</option>
          <option value="0" {"selected" if not learner["active"] else ""}>Nee</option>
        </select>
        <button type="submit" class="btn-success">Stoor</button>
        <a href="/admin/learners" class="btn btn-outline" style="margin-left:0.5rem;">Kanselleer</a>
      </form>
    </div>
    """
    return page("Wysig leerder", body, user)

def teachers_admin_page(user, msg=None, error=None):
    teachers = db.get_all_teachers()
    classes = db.get_all_classes()
    msg_html = ""
    if msg:
        msg_html = f'<div class="alert alert-success">{html_escape(msg)}</div>'
    if error:
        msg_html = f'<div class="alert alert-error">{html_escape(error)}</div>'

    class_options = "".join(f'<option value="{c["id"]}">{html_escape(c["name"])}</option>' for c in classes)

    rows = ""
    for t in teachers:
        rows += f"""
        <tr>
          <td>{html_escape(t['full_name'])}</td>
          <td><code>{html_escape(t['username'])}</code></td>
          <td>{html_escape(t.get('class_name') or '—')}</td>
          <td>
            <a class="btn btn-sm btn-outline" href="/admin/teachers?edit={t['id']}">Wysig</a>
            <a class="btn btn-sm btn-danger" href="/admin/teachers?delete={t['id']}"
               onclick="return confirm('Verwyder onderwyser {html_escape(t['full_name'])}?')">Verwyder</a>
          </td>
        </tr>"""

    body = f"""
    {msg_html}
    <div class="card">
      <h2>Bestuur onderwysers</h2>
      <p style="color:var(--muted);margin-bottom:1rem;">
        Voeg nuwe onderwysers by of verwyder bestaande. Elke onderwyser word aan een klas gekoppel.
      </p>
      <h3>Voeg nuwe onderwyser by</h3>
      <form method="POST" action="/admin/teachers" class="grid-2">
        <input type="hidden" name="action" value="add">
        <div>
          <label>Volle naam</label>
          <input type="text" name="full_name" required placeholder="bv. Mev. A. Nuwe">
        </div>
        <div>
          <label>Gebruikersnaam</label>
          <input type="text" name="username" required placeholder="bv. nuwe">
        </div>
        <div>
          <label>Wagwoord</label>
          <input type="text" name="password" required placeholder="Tydelike wagwoord">
        </div>
        <div>
          <label>Klas</label>
          <select name="class_id" required>{class_options}</select>
        </div>
        <div style="grid-column:1/-1;">
          <button type="submit" class="btn-success">Voeg onderwyser by</button>
        </div>
      </form>
    </div>
    <div class="card">
      <h2>Huidige onderwysers</h2>
      <table>
        <thead><tr><th>Naam</th><th>Gebruikersnaam</th><th>Klas</th><th>Aksie</th></tr></thead>
        <tbody>{rows or '<tr><td colspan=4>Geen onderwysers nie</td></tr>'}</tbody>
      </table>
    </div>
    <p><a class="btn btn-outline" href="/admin">← Terug na register</a></p>
    """
    return page("Onderwysers", body, user)


def classes_admin_page(user, msg=None, error=None):
    classes = db.get_all_classes()
    msg_html = ""
    if msg: msg_html = f'<div class="alert alert-success">{html_escape(msg)}</div>'
    if error: msg_html = f'<div class="alert alert-error">{html_escape(error)}</div>'

    class_opts = "".join(
        f'<option value="{c["id"]}">{html_escape(c["name"])} ({db.count_active_learners(c["id"])} leerders)</option>'
        for c in classes
    )

    rows = ""
    for c in classes:
        n = db.count_active_learners(c["id"])
        rows += f"""
        <tr>
          <td>{html_escape(c['name'])}</td>
          <td>{html_escape(c['teacher_name'])}</td>
          <td>{n}</td>
          <td>{html_escape(c.get('theme') or 'ocean')}</td>
          <td>
            <a class="btn btn-sm btn-outline" href="/admin/classes?edit={c['id']}">Wysig</a>
            <a class="btn btn-sm btn-danger" href="/admin/classes?delete={c['id']}"
               onclick="return confirm('Verwyder hierdie klas?')">Verwyder</a>
          </td>
        </tr>"""

    body = f"""
    {msg_html}
    <div class="card" style="border-left:5px solid var(--accent);">
      <h2>Bevorder / skuif leerders na volgende graad</h2>
      <p style="color:var(--muted);margin-bottom:1rem;">
        Aan die einde van die jaar: kies die ou klas en die nuwe klas.
        <strong>Skuif</strong> beweeg al die name (geskiedenis bly behoue).
        <strong>Kopieer</strong> maak nuwe rekords in die teikenklas (ou klas bly onveranderd).
      </p>
      <form method="POST" action="/admin/classes" class="grid-2">
        <input type="hidden" name="action" value="transfer">
        <div>
          <label>Van klas (huidige graad)</label>
          <select name="from_class_id" required>{class_opts}</select>
        </div>
        <div>
          <label>Na klas (volgende graad)</label>
          <select name="to_class_id" required>{class_opts}</select>
        </div>
        <div>
          <label>Aksie</label>
          <select name="mode">
            <option value="move">Skuif leerders (aanbeveel vir nuwe jaar)</option>
            <option value="copy">Kopieer leerders (hou ou klas ook)</option>
          </select>
        </div>
        <div style="display:flex;align-items:flex-end;">
          <button type="submit" class="btn-success"
            onclick="return confirm('Is jy seker? Dit raak alle aktiewe leerders in die bronklas.')">
            Voer oor
          </button>
        </div>
      </form>
    </div>

    <div class="card">
      <h2>Voeg nuwe klas / graad by</h2>
      <form method="POST" action="/admin/classes" class="grid-2">
        <input type="hidden" name="action" value="add">
        <div><label>Klasnaam</label><input type="text" name="name" required placeholder="bv. Multi-Graad 6"></div>
        <div><label>Opvoeder naam</label><input type="text" name="teacher_name" placeholder="bv. Mev. X"></div>
        <div><label>Volgorde</label><input type="text" name="sort_order" value="99"></div>
        <div><label>Tema</label>
          <select name="theme">
            {"".join(f'<option value="{k}">{html_escape(v["name"])}</option>' for k,v in db.THEMES.items())}
          </select>
        </div>
        <div style="grid-column:1/-1;"><button type="submit" class="btn-success">Voeg klas by</button></div>
      </form>
    </div>

    <div class="card">
      <h2>Huidige klasse</h2>
      <table>
        <thead><tr><th>Naam</th><th>Opvoeder</th><th>Leerders</th><th>Tema</th><th>Aksie</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
    <p><a class="btn btn-outline" href="/admin">← Terug</a></p>
    """
    return page("Klasse", body, user)


def edit_class_page(user, class_id):
    cls = db.get_class(class_id)
    if not cls:
        return classes_admin_page(user, error="Klas nie gevind nie.")
    theme_opts = "".join(
        f'<option value="{k}" {"selected" if k==cls.get("theme") else ""}>{html_escape(v["name"])}</option>'
        for k,v in db.THEMES.items()
    )
    body = f"""
    <div class="card" style="max-width:520px;">
      <h2>Wysig klas</h2>
      <form method="POST" action="/admin/classes">
        <input type="hidden" name="action" value="edit">
        <input type="hidden" name="class_id" value="{class_id}">
        <label>Klasnaam</label>
        <input type="text" name="name" value="{html_escape(cls['name'])}" required>
        <label>Opvoeder naam (vertoon op register)</label>
        <input type="text" name="teacher_name" value="{html_escape(cls['teacher_name'])}">
        <label>Volgorde</label>
        <input type="text" name="sort_order" value="{cls.get('sort_order',0)}">
        <label>Tema</label>
        <select name="theme">{theme_opts}</select>
        <button type="submit" class="btn-success">Stoor</button>
        <a href="/admin/classes" class="btn btn-outline" style="margin-left:0.5rem;">Kanselleer</a>
      </form>
    </div>
    """
    return page("Wysig klas", body, user)

def edit_teacher_page(user, teacher_id):
    teachers = db.get_all_teachers()
    t = next((x for x in teachers if x["id"]==teacher_id), None)
    if not t:
        return teachers_admin_page(user, error="Onderwyser nie gevind nie.")
    classes = db.get_all_classes()
    class_opts = "".join(
        f'<option value="{c["id"]}" {"selected" if c["id"]==t.get("class_id") else ""}>{html_escape(c["name"])}</option>'
        for c in classes
    )
    body = f"""
    <div class="card" style="max-width:520px;">
      <h2>Wysig onderwyser</h2>
      <form method="POST" action="/admin/teachers">
        <input type="hidden" name="action" value="edit">
        <input type="hidden" name="teacher_id" value="{teacher_id}">
        <label>Volle naam</label>
        <input type="text" name="full_name" value="{html_escape(t['full_name'])}" required>
        <label>Gebruikersnaam</label>
        <input type="text" value="{html_escape(t['username'])}" disabled style="opacity:0.7;">
        <label>Klas</label>
        <select name="class_id" required>{class_opts}</select>
        <label>Selfoonnommer (vir herinneringe)</label>
        <input type="text" name="phone" value="{html_escape(t.get('phone') or '')}" placeholder="bv. 0821234567">
        <label>Nuwe wagwoord (los leeg om nie te verander nie)</label>
        <input type="text" name="password" placeholder="Opsioneel">
        <button type="submit" class="btn-success">Stoor</button>
        <a href="/admin/teachers" class="btn btn-outline" style="margin-left:0.5rem;">Kanselleer</a>
      </form>
    </div>
    """
    return page("Wysig onderwyser", body, user)

def trends_page(user, days=30):
    data = db.get_attendance_trends(days)
    daily_rows = ""
    for d in data["daily"]:
        pct = round(100 * d["present"] / d["total"], 1) if d["total"] else 0
        bar = int(pct)
        daily_rows += f"""
        <tr>
          <td>{html_escape(d['attendance_date'])}</td>
          <td>{d['present']}</td>
          <td>{d['absent']}</td>
          <td>{d['total']}</td>
          <td>
            <div style="background:#eee;border-radius:4px;height:18px;width:120px;display:inline-block;vertical-align:middle;">
              <div style="background:var(--success);height:100%;width:{bar}%;border-radius:4px;"></div>
            </div>
            {pct}%
          </td>
        </tr>"""
    class_rows = ""
    for c in data["by_class"]:
        pct = round(100 * c["present"] / c["total"], 1) if c["total"] else 0
        class_rows += f"""
        <tr>
          <td>{html_escape(c['class_name'])}</td>
          <td>{c['present']}</td>
          <td>{c['absent']}</td>
          <td>{pct}%</td>
        </tr>"""
    absent_rows = ""
    for a in data["frequent_absent"]:
        absent_rows += f"""
        <tr>
          <td>{html_escape(a['first_name'])} {html_escape(a['last_name'])}</td>
          <td>{html_escape(a['class_name'])}</td>
          <td><strong>{a['absent_count']}</strong></td>
        </tr>"""
    body = f"""
    <div class="card">
      <h2>Bywoningsneigings (laaste {days} dae)</h2>
      <form method="GET" action="/admin/trends" class="no-print" style="margin-bottom:1rem;">
        <label style="display:inline;">Dae</label>
        <select name="days" onchange="this.form.submit()" style="width:auto;display:inline-block;margin-left:0.5rem;">
          <option value="7" {"selected" if days==7 else ""}>7</option>
          <option value="14" {"selected" if days==14 else ""}>14</option>
          <option value="30" {"selected" if days==30 else ""}>30</option>
          <option value="90" {"selected" if days==90 else ""}>90</option>
        </select>
      </form>
      <h3>Daaglikse opsomming</h3>
      <table>
        <thead><tr><th>Datum</th><th>Teenwoordig</th><th>Afwesig</th><th>Totaal</th><th>% Teenwoordig</th></tr></thead>
        <tbody>{daily_rows or '<tr><td colspan=5>Nog geen data vir hierdie periode nie</td></tr>'}</tbody>
      </table>
      <h3>Per klas</h3>
      <table>
        <thead><tr><th>Klas</th><th>Teenwoordig</th><th>Afwesig</th><th>%</th></tr></thead>
        <tbody>{class_rows or '<tr><td colspan=4>Geen data</td></tr>'}</tbody>
      </table>
      <h3>Leerders met 3+ afwesighede</h3>
      <table>
        <thead><tr><th>Leerder</th><th>Klas</th><th>Afwesighede</th></tr></thead>
        <tbody>{absent_rows or '<tr><td colspan=3>Geen</td></tr>'}</tbody>
      </table>
    </div>
    <p><a class="btn btn-outline" href="/admin">← Terug</a></p>
    """
    return page("Neigings", body, user)

def messages_page(user, msg=None):
    messages = db.get_conversation(80)
    users = [u for u in db.get_all_users() if u["id"] != user["id"]]
    user_opts = '<option value="">Almal (kennisgewingbord)</option>' + "".join(
        f'<option value="{u["id"]}">{html_escape(u["full_name"])} ({u["role"]})</option>' for u in users
    )
    msg_html = f'<div class="alert alert-success">{html_escape(msg)}</div>' if msg else ""
    feed = ""
    for m in messages:
        to_label = "Almal" if m.get("is_broadcast") or not m.get("to_user") else html_escape(m.get("to_name") or "")
        feed += f"""
        <div style="border-bottom:1px solid var(--border);padding:0.85rem 0;">
          <div style="font-size:0.82rem;color:var(--muted);">
            <strong>{html_escape(m['from_name'])}</strong> → {to_label}
            · {html_escape(m['created_at'][:16].replace('T',' '))}
          </div>
          {f'<div style="font-weight:600;margin-top:0.2rem;">{html_escape(m.get("subject") or "")}</div>' if m.get("subject") else ""}
          <div style="margin-top:0.3rem;">{html_escape(m['body'])}</div>
        </div>
        """
    body = f"""
    {msg_html}
    <div class="card">
      <h2>Boodskappe &amp; kennisgewings</h2>
      <p style="color:var(--muted);margin-bottom:1rem;">Vra vrae, stuur boodskappe aan die admin of aan mekaar.</p>
      <form method="POST" action="/messages">
        <label>Aan</label>
        <select name="to_user">{user_opts}</select>
        <label>Onderwerp (opsioneel)</label>
        <input type="text" name="subject" placeholder="bv. Vraag oor leerder">
        <label>Boodskap</label>
        <textarea name="body" rows="3" required placeholder="Skryf jou boodskap hier..."></textarea>
        <button type="submit" class="btn-success">Stuur</button>
      </form>
    </div>
    <div class="card">
      <h2>Onlangse boodskappe</h2>
      {feed or '<p style="color:var(--muted)">Nog geen boodskappe nie.</p>'}
    </div>
    """
    return page("Boodskappe", body, user)

def reminders_page(user, msg=None):
    teachers = db.get_teachers_with_phones()
    settings = db.get_all_settings()
    msg_html = f'<div class="alert alert-success">{html_escape(msg)}</div>' if msg else ""
    rows = ""
    for t in teachers:
        phone = t.get("phone") or "—"
        wa_link = ""
        if t.get("phone"):
            # WhatsApp click-to-chat (user must click, not automated)
            text = urllib.parse.quote(settings.get("reminder_message", "Merk asseblief bywoning"))
            num = "".join(c for c in t["phone"] if c.isdigit())
            if num.startswith("0"):
                num = "27" + num[1:]
            wa_link = f'<a class="btn btn-sm btn-success" target="_blank" href="https://wa.me/{num}?text={text}">WhatsApp</a>'
        rows += f"""
        <tr>
          <td>{html_escape(t['full_name'])}</td>
          <td>{html_escape(t.get('class_name') or '—')}</td>
          <td>{html_escape(phone)}</td>
          <td class="no-print">{wa_link}</td>
        </tr>"""
    body = f"""
    {msg_html}
    <div class="card">
      <h2>Herinneringe aan onderwysers</h2>
      <div class="alert alert-info">
        <strong>Hoe dit werk:</strong> Die stelsel stoor selfoonnommers en kan WhatsApp-skakels oopmaak.
        Volledige outomatiese WhatsApp/SMS-stuur vereis 'n betaalde diens (Twilio / WhatsApp Business API).
        Hier kan jy een-klik WhatsApp-boodskappe stuur, of nommers kopieer.
      </div>
      <p><strong>Standaard boodskap:</strong> {html_escape(settings.get('reminder_message',''))}</p>
      <p><strong>Voorgestelde tyd:</strong> {html_escape(settings.get('reminder_time','07:30'))}</p>
      <form method="POST" action="/admin/reminders" style="margin:1rem 0;">
        <input type="hidden" name="action" value="broadcast_inapp">
        <button type="submit" class="btn-success">Stuur in-app herinnering aan alle onderwysers</button>
      </form>
    </div>
    <div class="card">
      <h2>Onderwysers &amp; nommers</h2>
      <p style="color:var(--muted);font-size:0.9rem;">Sit selfoonnommers by via Onderwysers → Wysig.</p>
      <table>
        <thead><tr><th>Naam</th><th>Klas</th><th>Selfoon</th><th class="no-print">Stuur</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
    <p><a class="btn btn-outline" href="/admin">← Terug</a></p>
    """
    return page("Herinneringe", body, user)

def settings_page(user, msg=None):
    s = db.get_all_settings()
    msg_html = f'<div class="alert alert-success">{html_escape(msg)}</div>' if msg else ""
    body = f"""
    {msg_html}
    <div class="card" style="max-width:560px;">
      <h2>Stelsel-instellings</h2>
      <p style="color:var(--muted);margin-bottom:1rem;">Hierdie instellings bly behoue — jy hoef nie 'n nuwe webwerf te skep nie.</p>
      <form method="POST" action="/admin/settings">
        <label>Skoolnaam (op drukvorm)</label>
        <input type="text" name="school_name" value="{html_escape(s.get('school_name',''))}">
        <label>Admin se naam op finale register (wanneer jy afteken)</label>
        <input type="text" name="admin_display_name" value="{html_escape(s.get('admin_display_name',''))}"
               placeholder="bv. Mev. C. Koopman">
        <label>Herinneringstyd (voorstel)</label>
        <input type="text" name="reminder_time" value="{html_escape(s.get('reminder_time','07:30'))}">
        <label>Standaard herinnering-boodskap</label>
        <textarea name="reminder_message" rows="3">{html_escape(s.get('reminder_message',''))}</textarea>
        <button type="submit" class="btn-success">Stoor instellings</button>
      </form>
    </div>
    <div class="card" style="max-width:560px;">
      <h2>Jou admin-profiel</h2>
      <form method="POST" action="/admin/settings">
        <input type="hidden" name="action" value="profile">
        <label>Jou volle naam</label>
        <input type="text" name="full_name" value="{html_escape(user['full_name'])}">
        <label>Selfoonnommer</label>
        <input type="text" name="phone" value="{html_escape(user.get('phone') or '')}">
        <label>Nuwe wagwoord (los leeg om nie te verander nie)</label>
        <input type="password" name="password">
        <button type="submit" class="btn">Stoor profiel</button>
      </form>
    </div>

    <div class="card">
      <h2>Rugsteun &amp; herstel (teen dataverlies)</h2>
      <p style="color:var(--muted);margin-bottom:1rem;">
        Laai gereeld ’n rugsteun af. As Render die data uitvee, kan jy dit hier teruglaai.
      </p>
      <p>
        <a class="btn btn-success" href="/admin/backup">⬇ Laai volle rugsteun af (JSON)</a>
      </p>
      <form method="POST" action="/admin/restore" enctype="multipart/form-data" style="margin-top:1.25rem;"
            onsubmit="return confirm('Dit vervang HUIDIGE data met die rugsteun. Is jy seker?')">
        <label>Herstel vanaf rugsteun-lêer</label>
        <input type="file" name="backup_file" accept=".json,application/json" required>
        <button type="submit" class="btn-danger">Herstel data</button>
      </form>
      <p style="margin-top:1rem;font-size:0.9rem;color:var(--muted);">
        Databasis-pad: <code>{html_escape(db.DB_PATH)}</code><br>
        Permanente berging: <strong>{"Ja" if db.is_persistent_storage() else "Nee – risiko van dataverlies"}</strong>
      </p>
    </div>

    <p><a class="btn btn-outline" href="/admin">← Terug</a></p>
    """
    return page("Instellings", body, user)



def search_page(user, q=""):
    results = db.search_learners(q) if q else []
    rows = ""
    for l in results:
        rows += f"""
        <tr>
          <td>{html_escape(l['first_name'])} {html_escape(l['last_name'])}</td>
          <td>{html_escape(l['class_name'])}</td>
          <td>{l['gender']}</td>
          <td><a class="btn btn-sm" href="/learner?id={l['id']}">Geskiedenis</a></td>
        </tr>"""
    body = f"""
    <div class="card">
      <h2>Soek leerders</h2>
      <form method="GET" action="/search" style="display:flex;gap:0.5rem;margin-bottom:1rem;">
        <input type="text" name="q" value="{html_escape(q)}" placeholder="Naam..." style="margin:0;flex:1;" autofocus>
        <button type="submit">Soek</button>
      </form>
      <table>
        <thead><tr><th>Naam</th><th>Klas</th><th>Geslag</th><th></th></tr></thead>
        <tbody>{rows or '<tr><td colspan=4>Geen resultate</td></tr>'}</tbody>
      </table>
    </div>
    """
    return page("Soek", body, user)

def learner_history_page(user, learner_id):
    learners = db.get_all_learners(active_only=False)
    learner = next((l for l in learners if l["id"] == learner_id), None)
    if not learner:
        return page("Fout", '<div class="alert alert-error">Leerder nie gevind.</div>', user)
    hist = db.get_learner_history(learner_id)
    rows = ""
    for h in hist:
        detail = h.get("status_detail") or h.get("status")
        badge = {"present":"badge-present","late":"badge-unsigned","absent":"badge-absent"}.get(detail, "badge-unsigned")
        rows += f"""
        <tr>
          <td>{html_escape(h['attendance_date'])}</td>
          <td>{html_escape(h.get('class_name',''))}</td>
          <td><span class="badge {badge}">{html_escape(detail)}</span></td>
          <td>{html_escape(h.get('reason') or '—')}</td>
        </tr>"""
    body = f"""
    <div class="card">
      <h2>{html_escape(learner['first_name'])} {html_escape(learner['last_name'])}</h2>
      <p style="color:var(--muted);">{html_escape(learner.get('class_name',''))} · {learner['gender']}</p>
      <table style="margin-top:1rem;">
        <thead><tr><th>Datum</th><th>Klas</th><th>Status</th><th>Rede</th></tr></thead>
        <tbody>{rows or '<tr><td colspan=4>Geen rekords</td></tr>'}</tbody>
      </table>
      <p style="margin-top:1rem;"><a class="btn btn-outline" href="/">Terug</a></p>
    </div>
    """
    return page("Leerder geskiedenis", body, user)

def announcements_page(user, msg=None):
    anns = db.get_active_announcements()
    msg_html = f'<div class="alert alert-success">{html_escape(msg)}</div>' if msg else ""
    rows = ""
    for a in anns:
        rows += f"""
        <tr>
          <td><strong>{html_escape(a['title'])}</strong><br>{html_escape(a['body'])}</td>
          <td>{html_escape(a.get('full_name') or '')}<br><small>{html_escape((a.get('created_at') or '')[:16])}</small></td>
          <td><a class="btn btn-sm btn-danger" href="/admin/announcements?deactivate={a['id']}">Deaktiveer</a></td>
        </tr>"""
    body = f"""
    {msg_html}
    <div class="card">
      <h2>Aankondigings</h2>
      <p style="color:var(--muted);">Verskyn bo-aan almal se tuisskerm.</p>
      <form method="POST" action="/admin/announcements">
        <label>Titel</label>
        <input type="text" name="title" required>
        <label>Boodskap</label>
        <textarea name="body" rows="3" required></textarea>
        <button type="submit" class="btn-success">Plaas aankondiging</button>
      </form>
    </div>
    <div class="card">
      <h2>Aktiewe aankondigings</h2>
      <table>
        <thead><tr><th>Inhoud</th><th>Deur</th><th></th></tr></thead>
        <tbody>{rows or '<tr><td colspan=3>Geen</td></tr>'}</tbody>
      </table>
    </div>
    """
    return page("Aankondigings", body, user)

def audit_page(user):
    logs = db.get_audit_log(80)
    rows = ""
    for a in logs:
        rows += f"""
        <tr>
          <td>{html_escape((a.get('created_at') or '')[:19])}</td>
          <td>{html_escape(a.get('full_name') or '—')}</td>
          <td>{html_escape(a.get('action') or '')}</td>
          <td style="font-size:0.85rem;">{html_escape(a.get('detail') or '')}</td>
        </tr>"""
    body = f"""
    <div class="card">
      <h2>Oudit-logboek</h2>
      <p style="color:var(--muted);">Wie het wat gedoen — belangrik vir rekordhouding oor jare.</p>
      <table>
        <thead><tr><th>Tyd</th><th>Gebruiker</th><th>Aksie</th><th>Besonderhede</th></tr></thead>
        <tbody>{rows or '<tr><td colspan=4>Nog leeg</td></tr>'}</tbody>
      </table>
    </div>
    """
    return page("Oudit", body, user)



def parse_multipart(handler, body=None):
    """Parse multipart form; returns (fields dict, files dict of name->bytes)."""
    ctype = handler.headers.get("Content-Type", "")
    if body is None:
        length = int(handler.headers.get("Content-Length", 0))
        body = handler.rfile.read(length) if length else b""
    fields, files = {}, {}
    if "multipart/form-data" not in ctype:
        qs = urllib.parse.parse_qs(body.decode("utf-8", errors="replace"))
        return {k: v[0] if len(v)==1 else v for k,v in qs.items()}, files
    # boundary
    boundary = None
    for part in ctype.split(";"):
        part = part.strip()
        if part.startswith("boundary="):
            boundary = part.split("=", 1)[1].strip().strip('"')
    if not boundary:
        return fields, files
    sep = b"--" + boundary.encode()
    for chunk in body.split(sep):
        if not chunk or chunk in (b"--", b"--\r\n", b"\r\n"):
            continue
        if chunk.startswith(b"\r\n"):
            chunk = chunk[2:]
        if chunk.endswith(b"\r\n"):
            chunk = chunk[:-2]
        if chunk == b"--":
            continue
        header_end = chunk.find(b"\r\n\r\n")
        if header_end < 0:
            continue
        headers_raw = chunk[:header_end].decode("utf-8", errors="replace")
        data = chunk[header_end+4:]
        if data.endswith(b"\r\n"):
            data = data[:-2]
        name = None
        filename = None
        for line in headers_raw.split("\r\n"):
            if line.lower().startswith("content-disposition:"):
                for bit in line.split(";"):
                    bit = bit.strip()
                    if bit.startswith("name="):
                        name = bit.split("=",1)[1].strip().strip('"')
                    if bit.startswith("filename="):
                        filename = bit.split("=",1)[1].strip().strip('"')
        if not name:
            continue
        if filename is not None:
            files[name] = data
        else:
            fields[name] = data.decode("utf-8", errors="replace")
    return fields, files


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {args[0]}")

    def parse_qs(self, data: bytes):
        return urllib.parse.parse_qs(data.decode("utf-8", errors="replace"))

    def get_user(self):
        return get_session_user(self.headers.get("Cookie", ""))

    def require_login(self):
        user = self.get_user()
        if not user:
            redirect(self, "/login")
            return None
        return user

    def require_admin(self):
        user = self.require_login()
        if not user:
            return None
        if user["role"] != "admin":
            self.send_error(403, "Slegs administrateurs")
            return None
        return user

    def send_html(self, content: str, status=200):
        data = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def serve_static(self, path):
        # path like /static/logo.png
        rel = path[len("/static/"):]
        filepath = os.path.join(STATIC_DIR, rel)
        if not os.path.isfile(filepath) or ".." in rel:
            self.send_error(404)
            return
        ctype = mimetypes.guess_type(filepath)[0] or "application/octet-stream"
        with open(filepath, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "public, max-age=86400")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        if path.startswith("/static/"):
            self.serve_static(path)
            return

        if path == "/login":
            if self.get_user():
                redirect(self, "/")
                return
            self.send_html(login_page())
            return

        if path == "/logout":
            cookie = SimpleCookie()
            try:
                cookie.load(self.headers.get("Cookie", ""))
            except Exception:
                pass
            if "session" in cookie:
                SESSIONS.pop(cookie["session"].value, None)
            self.send_response(302)
            clear_cookie(self, "session")
            self.send_header("Location", "/login")
            self.end_headers()
            return

        user = self.require_login()
        if not user:
            return

        if path in ("/", "/index"):
            msg = qs.get("msg", [None])[0]
            self.send_html(teacher_home(user, msg=msg))
            return

        if path == "/mark":
            class_id = int(qs.get("class_id", [0])[0])
            att_date = qs.get("date", [today_str()])[0]
            msg = qs.get("msg", [None])[0]
            if qs.get("copy_prev", [None])[0]:
                prev_date, prev_recs = db.get_previous_attendance(class_id, att_date)
                if prev_recs:
                    records = [{"learner_id": r["learner_id"], "status": r["status"], "reason": r.get("reason") or ""} for r in prev_recs]
                    db.save_attendance_v2(att_date, class_id, records, user["id"])
                    msg = f"Gekopieer vanaf {prev_date}"
                else:
                    msg = "Geen vorige bywoning gevind om te kopieer nie"
            self.send_html(mark_page(user, class_id, att_date, msg=msg))
            return

        if path == "/view":
            class_id = int(qs.get("class_id", [0])[0])
            att_date = qs.get("date", [today_str()])[0]
            self.send_html(view_class_page(user, class_id, att_date))
            return

        if path == "/theme":
            class_id = int(qs.get("class_id", [0])[0])
            msg = qs.get("msg", [None])[0]
            self.send_html(theme_page(user, class_id, msg=msg))
            return

        if path == "/admin":
            att_date = qs.get("date", [today_str()])[0]
            self.send_html(admin_dashboard(user, att_date))
            return

        if path == "/admin/learners":
            admin = self.require_admin()
            if not admin:
                return
            if "edit" in qs:
                self.send_html(edit_learner_page(admin, int(qs["edit"][0])))
                return
            if "deactivate" in qs:
                db.deactivate_learner(int(qs["deactivate"][0]))
                redirect(self, "/admin/learners?msg=Leerder+gedeaktiveer")
                return
            if "delete" in qs:
                db.delete_learner_permanently(int(qs["delete"][0]))
                redirect(self, "/admin/learners?msg=Leerder+permanent+verwyder")
                return
            msg = qs.get("msg", [None])[0]
            self.send_html(learners_admin_page(admin, msg=msg))
            return

        if path == "/admin/teachers":
            admin = self.require_admin()
            if not admin:
                return
            if "edit" in qs:
                self.send_html(edit_teacher_page(admin, int(qs["edit"][0])))
                return
            if "delete" in qs:
                try:
                    db.delete_teacher(int(qs["delete"][0]))
                    redirect(self, "/admin/teachers?msg=Onderwyser+verwyder")
                except Exception as e:
                    self.send_html(teachers_admin_page(admin, error=str(e)))
                return
            msg = qs.get("msg", [None])[0]
            self.send_html(teachers_admin_page(admin, msg=msg))
            return


        if path == "/admin/classes":
            admin = self.require_admin()
            if not admin: return
            if "edit" in qs:
                self.send_html(edit_class_page(admin, int(qs["edit"][0])))
                return
            if "delete" in qs:
                try:
                    db.delete_class(int(qs["delete"][0]))
                    redirect(self, "/admin/classes?msg=Klas+verwyder")
                except Exception as e:
                    self.send_html(classes_admin_page(admin, error=str(e)))
                return
            msg = qs.get("msg", [None])[0]
            self.send_html(classes_admin_page(admin, msg=msg))
            return

        if path == "/admin/trends":
            admin = self.require_admin()
            if not admin: return
            days = int(qs.get("days", ["30"])[0])
            self.send_html(trends_page(admin, days))
            return

        if path == "/admin/reminders":
            admin = self.require_admin()
            if not admin: return
            msg = qs.get("msg", [None])[0]
            self.send_html(reminders_page(admin, msg=msg))
            return

        if path == "/admin/settings":
            admin = self.require_admin()
            if not admin: return
            msg = qs.get("msg", [None])[0]
            self.send_html(settings_page(admin, msg=msg))
            return

        if path == "/messages":
            msg = qs.get("msg", [None])[0]
            self.send_html(messages_page(user, msg=msg))
            return


        if path == "/search":
            admin = self.require_admin()
            if not admin: return
            q = qs.get("q", [""])[0]
            results = db.search_learners(q) if q.strip() else []
            rows = ""
            for l in results:
                rows += f"""<tr>
                  <td>{html_escape(l['first_name'])} {html_escape(l['last_name'])}</td>
                  <td>{html_escape(l['class_name'])}</td>
                  <td>{l['gender']}</td>
                  <td><a class="btn btn-sm btn-outline" href="/admin/learners?edit={l['id']}">Wysig</a></td>
                </tr>"""
            body = f"""
            <div class="card">
              <h2>Soek leerders</h2>
              <form method="GET" action="/search" style="display:flex;gap:0.5rem;margin-bottom:1rem;">
                <input type="text" name="q" value="{html_escape(q)}" placeholder="Naam..." style="flex:1;margin:0;" autofocus>
                <button type="submit">Soek</button>
              </form>
              <table>
                <thead><tr><th>Naam</th><th>Klas</th><th>Geslag</th><th>Status</th><th>Aksie</th></tr></thead>
                <tbody>{rows or '<tr><td colspan=6>Geen resultate</td></tr>'}</tbody>
              </table>
            </div>
            <p><a class="btn btn-outline" href="/">← Tuis</a></p>
            """
            self.send_html(page("Soek", body, admin))
            return

        if path == "/admin/audit":
            admin = self.require_admin()
            if not admin: return
            logs = db.get_audit_log(150)
            rows = "".join(
                f"<tr><td>{html_escape(l['created_at'][:19].replace('T',' '))}</td>"
                f"<td>{html_escape(l.get('full_name') or '—')}</td>"
                f"<td>{html_escape(l['action'])}</td>"
                f"<td style='font-size:0.85rem;'>{html_escape(l.get('detail') or '')}</td></tr>"
                for l in logs
            )
            body = f"""
            <div class="card">
              <h2>Oudit-log (wie het wat gedoen)</h2>
              <table>
                <thead><tr><th>Tyd</th><th>Gebruiker</th><th>Aksie</th><th>Besonderhede</th></tr></thead>
                <tbody>{rows or '<tr><td colspan=4>Nog leeg</td></tr>'}</tbody>
              </table>
            </div>
            <p><a class="btn btn-outline" href="/admin">← Terug</a></p>
            """
            self.send_html(page("Oudit", body, admin))
            return

        if path == "/export/csv":
            admin = self.require_admin()
            if not admin: return
            att_date = qs.get("date", [today_str()])[0]
            csv_data = db.export_register_csv(att_date)
            data = csv_data.encode("utf-8-sig")  # BOM for Excel
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition", f'attachment; filename="bywoning_{att_date}.csv"')
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        if path == "/export/backup":
            admin = self.require_admin()
            if not admin: return
            import shutil
            db_path = db.DB_PATH
            with open(db_path, "rb") as f:
                data = f.read()
            fname = f"mispah_backup_{today_str()}.db"
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Disposition", f'attachment; filename="{fname}"')
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            db.log_audit(admin["id"], "backup_download", fname)
            return


        if path == "/search":
            q = qs.get("q", [""])[0]
            self.send_html(search_page(user, q))
            return
        if path == "/learner":
            lid = int(qs.get("id", [0])[0])
            self.send_html(learner_history_page(user, lid))
            return
        if path == "/admin/announcements":
            admin = self.require_admin()
            if not admin: return
            if "deactivate" in qs:
                db.deactivate_announcement(int(qs["deactivate"][0]))
                redirect(self, "/admin/announcements?msg=Gedeaktiveer")
                return
            msg = qs.get("msg", [None])[0]
            self.send_html(announcements_page(admin, msg=msg))
            return
        if path == "/admin/audit":
            admin = self.require_admin()
            if not admin: return
            self.send_html(audit_page(admin))
            return
        if path == "/admin/export":
            admin = self.require_admin()
            if not admin: return
            kind = qs.get("kind", ["register"])[0]
            att_date = qs.get("date", [today_str()])[0]
            if kind == "register":
                csv_data = db.export_register_csv(att_date)
                fname = f"register_{att_date}.csv"
            else:
                csv_data = db.export_all_attendance_csv(90)
                fname = "attendance_export.csv"
            data = ("\ufeff" + csv_data).encode("utf-8")  # BOM for Excel
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition", f'attachment; filename="{fname}"')
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        if path == "/admin/backup":
            admin = self.require_admin()
            if not admin: return
            import json as _json
            data = db.export_full_backup()
            raw = _json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
            fname = f"mispah_backup_{today_str()}.json"
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Disposition", f'attachment; filename="{fname}"')
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        self.send_error(404, "Bladsy nie gevind nie")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b""

        # File upload restore must use multipart (before form parse)
        if path == "/admin/restore":
            admin = self.require_admin()
            if not admin: return
            import json as _json
            try:
                fields, files = parse_multipart(self, body=body)
                raw = files.get("backup_file") or b""
                if not raw:
                    self.send_html(page("Fout", '<div class="alert alert-error">Geen lêer ontvang nie.</div><a class="btn" href="/admin/settings">Terug</a>', admin))
                    return
                data = _json.loads(raw.decode("utf-8"))
                db.import_full_backup(data, replace=True)
                try:
                    db.audit(admin["id"], "restore_backup", "full")
                except Exception:
                    pass
                redirect(self, "/admin/settings?msg=Data+hersteld+van+rugsteun")
            except Exception as e:
                self.send_html(page("Fout", f'<div class="alert alert-error">Herstel misluk: {html_escape(str(e))}</div><a class="btn" href="/admin/settings">Terug</a>', admin))
            return

        form = self.parse_qs(body)

        if path == "/login":
            username = form.get("username", [""])[0]
            password = form.get("password", [""])[0]
            user = db.authenticate(username, password)
            if not user:
                self.send_html(login_page(error="Verkeerde gebruikersnaam of wagwoord."))
                return
            sid = make_session(user["id"])
            self.send_response(302)
            set_cookie(self, "session", sid)
            self.send_header("Location", "/")
            self.end_headers()
            return

        user = self.require_login()
        if not user:
            return

        if path == "/mark":
            class_id = int(form.get("class_id", [0])[0])
            att_date = form.get("date", [today_str()])[0]
            records = []
            for key, vals in form.items():
                if key.startswith("status_"):
                    lid = int(key.split("_", 1)[1])
                    status = vals[0]
                    if status in ("present", "absent"):
                        reason = form.get(f"reason_{lid}", [""])[0]
                        records.append({"learner_id": lid, "status": status, "reason": reason if status=="absent" else ""})
            if records:
                db.save_attendance_v2(att_date, class_id, records, user["id"])
                db.log_audit(user["id"], "mark_attendance", f"class={class_id} date={att_date} n={len(records)}")
                redirect(self, f"/mark?class_id={class_id}&date={att_date}&msg=Bywoning+gestoor")
            else:
                self.send_html(mark_page(user, class_id, att_date, error="Geen leerders gemerk nie."))
            return

        if path == "/theme":
            class_id = int(form.get("class_id", [0])[0])
            theme = form.get("theme", ["ocean"])[0]
            if user["role"] == "admin" or user.get("class_id") == class_id:
                db.set_class_theme(class_id, theme)
                redirect(self, f"/theme?class_id={class_id}&msg=Tema+gestoor")
            else:
                self.send_error(403)
            return

        if path == "/admin/signoff":
            admin = self.require_admin()
            if not admin:
                return
            att_date = form.get("date", [today_str()])[0]
            notes = form.get("notes", [""])[0]
            db.admin_sign_off(att_date, admin["id"], notes)
            redirect(self, f"/admin?date={att_date}")
            return

        if path == "/admin/learners":
            admin = self.require_admin()
            if not admin:
                return
            action = form.get("action", [""])[0]
            if action == "add":
                try:
                    db.add_learner(
                        int(form["class_id"][0]),
                        form["first_name"][0],
                        form["last_name"][0],
                        form["gender"][0],
                    )
                    db.log_audit(admin["id"], "add_learner", form["first_name"][0] + " " + form["last_name"][0])
                    redirect(self, "/admin/learners?msg=Leerder+bygevoeg")
                except Exception as e:
                    self.send_html(learners_admin_page(admin, error=str(e)))
                return
            if action == "edit":
                try:
                    db.update_learner(
                        int(form["learner_id"][0]),
                        int(form["class_id"][0]),
                        form["first_name"][0],
                        form["last_name"][0],
                        form["gender"][0],
                        int(form.get("active", ["1"])[0]),
                    )
                    redirect(self, "/admin/learners?msg=Leerder+opgedateer")
                except Exception as e:
                    self.send_html(learners_admin_page(admin, error=str(e)))
                return

        if path == "/admin/teachers":
            admin = self.require_admin()
            if not admin:
                return
            action = form.get("action", [""])[0]
            if action == "edit":
                try:
                    tid = int(form["teacher_id"][0])
                    db.update_teacher(
                        tid,
                        form["full_name"][0],
                        int(form["class_id"][0]),
                        form.get("password", [""])[0] or None,
                    )
                    phone = form.get("phone", [""])[0]
                    if phone is not None:
                        db.update_user_profile(tid, phone=phone)
                    redirect(self, "/admin/teachers?msg=Onderwyser+opgedateer")
                except Exception as e:
                    self.send_html(teachers_admin_page(admin, error=str(e)))
                return
            if action == "add":
                try:
                    db.add_teacher(
                        form["username"][0],
                        form["password"][0],
                        form["full_name"][0],
                        int(form["class_id"][0]),
                    )
                    redirect(self, "/admin/teachers?msg=Onderwyser+bygevoeg")
                except Exception as e:
                    self.send_html(teachers_admin_page(admin, error=str(e)))
                return


        if path == "/admin/classes":
            admin = self.require_admin()
            if not admin: return
            action = form.get("action", [""])[0]
            if action == "transfer":
                try:
                    from_id = int(form["from_class_id"][0])
                    to_id = int(form["to_class_id"][0])
                    mode = form.get("mode", ["move"])[0]
                    n = db.transfer_learners(from_id, to_id, mode)
                    db.audit(admin["id"], "transfer_learners", f"from={from_id} to={to_id} mode={mode} n={n}")
                    word = "geskuif" if mode == "move" else "gekopieer"
                    redirect(self, f"/admin/classes?msg={n}+leerders+{word}")
                except Exception as e:
                    self.send_html(classes_admin_page(admin, error=str(e)))
                return
            if action == "add":
                try:
                    db.add_class(
                        form["name"][0],
                        form.get("teacher_name", [""])[0],
                        int(form.get("sort_order", ["99"])[0] or 99),
                        form.get("theme", ["ocean"])[0],
                    )
                    redirect(self, "/admin/classes?msg=Klas+bygevoeg")
                except Exception as e:
                    self.send_html(classes_admin_page(admin, error=str(e)))
                return
            if action == "edit":
                try:
                    db.update_class(
                        int(form["class_id"][0]),
                        form["name"][0],
                        form.get("teacher_name", [""])[0],
                        int(form.get("sort_order", ["0"])[0] or 0),
                        form.get("theme", ["ocean"])[0],
                    )
                    redirect(self, "/admin/classes?msg=Klas+opgedateer")
                except Exception as e:
                    self.send_html(classes_admin_page(admin, error=str(e)))
                return

        if path == "/admin/settings":
            admin = self.require_admin()
            if not admin: return
            action = form.get("action", [""])[0]
            if action == "profile":
                db.update_user_profile(
                    admin["id"],
                    full_name=form.get("full_name", [None])[0],
                    phone=form.get("phone", [None])[0],
                    password=form.get("password", [""])[0] or None,
                )
                redirect(self, "/admin/settings?msg=Profiel+gestoor")
                return
            for key in ("school_name", "admin_display_name", "reminder_time", "reminder_message"):
                if key in form:
                    db.set_setting(key, form[key][0])
            redirect(self, "/admin/settings?msg=Instellings+gestoor")
            return

        if path == "/admin/reminders":
            admin = self.require_admin()
            if not admin: return
            action = form.get("action", [""])[0]
            if action == "broadcast_inapp":
                msg_text = db.get_setting("reminder_message", "Merk asseblief vandag se bywoning.")
                teachers = db.get_all_teachers()
                for t in teachers:
                    db.send_message(admin["id"], msg_text, to_user=t["id"], subject="Herinnering: Bywoning")
                    db.log_reminder(t["id"], msg_text, "in-app")
                redirect(self, "/admin/reminders?msg=In-app+herinneringe+gestuur")
                return

        if path == "/messages":
            body_text = form.get("body", [""])[0]
            subject = form.get("subject", [""])[0]
            to_raw = form.get("to_user", [""])[0]
            to_user = int(to_raw) if to_raw else None
            is_broadcast = to_user is None
            if body_text.strip():
                db.send_message(user["id"], body_text, to_user=to_user, subject=subject, is_broadcast=is_broadcast)
            redirect(self, "/messages?msg=Boodskap+gestuur")
            return

        
        if path == "/admin/announcements":
            admin = self.require_admin()
            if not admin: return
            title = form.get("title", [""])[0]
            body = form.get("body", [""])[0]
            if title and body:
                db.add_announcement(title, body, admin["id"])
                db.audit(admin["id"], "announcement", title)
            redirect(self, "/admin/announcements?msg=Aankondiging+geplaas")
            return

        
