"""
Lokaler Server für die Kunyu-Karte.
Serviert Deep Zoom Tiles + statische Dateien + passwortgeschützte Save-API.
"""

import hashlib
import http.server
import json
import os
import re
import secrets
import time
from urllib.parse import unquote

PORT = 8081
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TILES_DIR = os.path.join(BASE_DIR, 'tiles')
DATA_DIR = os.path.join(BASE_DIR, 'data')

ALLOWED_FILES = {'spots.json', 'header.json', 'modals.json', 'legend.json'}
BLOCKED_PREFIXES = ('.', '__')

# ── Auth ──
SESSIONS = {}  # token -> expiry timestamp
SESSION_DURATION = 3600 * 8  # 8 hours


def hash_password(pw):
    return hashlib.sha256(pw.encode('utf-8')).hexdigest()


def load_or_create_password():
    hash_file = os.path.join(BASE_DIR, '.admin_hash')
    if os.path.exists(hash_file):
        with open(hash_file, 'r') as f:
            return f.read().strip()
    # Generate random password on first run
    password = secrets.token_urlsafe(10)
    pw_hash = hash_password(password)
    with open(hash_file, 'w') as f:
        f.write(pw_hash)
    print()
    print(f"  ==========================================")
    print(f"    Admin-Passwort generiert:")
    print(f"    {password}")
    print(f"")
    print(f"    Bitte notieren!")
    print(f"    Zum Aendern: .admin_hash loeschen")
    print(f"  ==========================================")
    print()
    return pw_hash


ADMIN_HASH = load_or_create_password()


def create_session():
    token = secrets.token_urlsafe(32)
    SESSIONS[token] = time.time() + SESSION_DURATION
    # Clean expired sessions
    now = time.time()
    expired = [t for t, exp in SESSIONS.items() if exp < now]
    for t in expired:
        del SESSIONS[t]
    return token


def check_token(token):
    if not token:
        return False
    if token not in SESSIONS:
        return False
    if SESSIONS[token] < time.time():
        del SESSIONS[token]
        return False
    return True


class KunyuHandler(http.server.SimpleHTTPRequestHandler):
    """Serves static files + password-protected save API."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE_DIR, **kwargs)

    def do_GET(self):
        # Block access to dotfiles and hidden directories
        path = unquote(self.path).split('?')[0]
        parts = path.strip('/').split('/')
        for part in parts:
            if any(part.startswith(p) for p in BLOCKED_PREFIXES):
                self.send_error(403, 'Forbidden')
                return
        super().do_GET()

    def do_POST(self):
        path = unquote(self.path)

        # Login endpoint (no auth required)
        if path == '/api/login':
            self.handle_login()
            return

        # All other API endpoints require auth
        token = self.headers.get('Authorization', '').replace('Bearer ', '')
        if not check_token(token):
            self.send_response(401)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': 'Nicht autorisiert'}).encode())
            return

        # Save API: POST /api/save/{filename}
        match = re.match(r'/api/save/(\w+\.json)', path)
        if match:
            filename = match.group(1)
            if filename not in ALLOWED_FILES:
                self.send_error(403, f'Not allowed: {filename}')
                return
            self.handle_save(filename)
            return

        self.send_error(404, 'Not found')

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def handle_login(self):
        try:
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            data = json.loads(body)
            pw = data.get('password', '')

            if hash_password(pw) == ADMIN_HASH:
                token = create_session()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'ok': True, 'token': token}).encode())
                print(f"  [AUTH] Admin-Login erfolgreich")
            else:
                self.send_response(403)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'ok': False, 'error': 'Falsches Passwort'}).encode())
                print(f"  [AUTH] Fehlgeschlagener Login-Versuch")
        except Exception as e:
            self.send_error(400, str(e))

    def handle_save(self, filename):
        try:
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            data = json.loads(body)

            os.makedirs(DATA_DIR, exist_ok=True)
            filepath = os.path.join(DATA_DIR, filename)
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'ok': True, 'file': filename}).encode())
            print(f"  [SAVE] {filename} ({len(body)} bytes)")
        except Exception as e:
            self.send_error(500, str(e))

    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'SAMEORIGIN')
        super().end_headers()

    def log_message(self, format, *args):
        # Quieter logging — skip 200/304 for static files
        if len(args) >= 2 and args[1] in ('200', '304'):
            return
        super().log_message(format, *args)


def main():
    os.chdir(BASE_DIR)

    if not os.path.exists(os.path.join(TILES_DIR, 'kunyu.dzi')):
        print("WARNUNG: Tiles nicht gefunden! Erst 'python generate_tiles.py' ausfuehren.")
        print("Server startet trotzdem.\n")

    os.makedirs(DATA_DIR, exist_ok=True)

    handler = KunyuHandler
    with http.server.HTTPServer(('', PORT), handler) as httpd:
        print(f"  ========================================")
        print(f"    Kunyu Wanguo Quantu - Kartenserver")
        print(f"  ========================================")
        print(f"")
        print(f"  Viewer:  http://localhost:{PORT}")
        print(f"  Admin:   Ctrl+Shift+A (Passwort noetig)")
        print(f"  Daten:   {DATA_DIR}")
        print(f"")
        print(f"  Zum Beenden: Ctrl+C")
        print()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer gestoppt.")


if __name__ == '__main__':
    main()
