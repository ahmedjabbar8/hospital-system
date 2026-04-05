import psycopg2
from psycopg2.extras import RealDictCursor
import sqlite3
import os
from flask import session, g
from datetime import datetime
import re

# ── Database Connection Settings (PostgreSQL) ──────────────────────────────
PG_HOST     = os.getenv('PGHOST',     'localhost')
PG_PORT     = os.getenv('PGPORT',     '5432')
PG_DB       = os.getenv('PGDATABASE', 'healthpro')
PG_USER     = os.getenv('PGUSER',     'postgres')
PG_PASSWORD = os.getenv('PGPASSWORD', 'postgres')

# ── Fallback SQLite Path ───────────────────────────────────────────────────
DB_PATH = os.path.join(os.path.dirname(__file__), 'HospitalSystem.db')

# ── PostgreSQL availability cache ─────────────────────────────────────────
# Checked once at startup; avoids 3-second timeout on every request
_PG_AVAILABLE = None

def _check_pg_available():
    global _PG_AVAILABLE
    if _PG_AVAILABLE is not None:
        return _PG_AVAILABLE
    try:
        c = psycopg2.connect(
            host=PG_HOST, port=PG_PORT,
            database=PG_DB, user=PG_USER,
            password=PG_PASSWORD, connect_timeout=2
        )
        c.close()
        _PG_AVAILABLE = True
    except Exception:
        _PG_AVAILABLE = False
    return _PG_AVAILABLE


# ══════════════════════════════════════════════════════════════════════════
#  Cursor Wrappers
# ══════════════════════════════════════════════════════════════════════════

class PostgresCursor:
    def __init__(self, cursor, dictionary=False):
        self.cursor     = cursor
        self.dictionary = dictionary
        self.lastrowid  = None

    def execute(self, query, params=None):
        query = query.replace('?', '%s')
        query = re.sub(r'NOW\(\)', 'CURRENT_TIMESTAMP', query, flags=re.I)
        query = query.replace("date('now')", 'CURRENT_DATE')
        if params is None:
            self.cursor.execute(query)
        else:
            self.cursor.execute(query, params)
        try:
            if "RETURNING" in query.upper():
                self.lastrowid = self.cursor.fetchone()[0]
        except Exception:
            pass

    def fetchone(self):  return self.cursor.fetchone()
    def fetchall(self):  return self.cursor.fetchall()
    def close(self):     self.cursor.close()

    def __getattr__(self, name):
        return getattr(self.cursor, name)


class SQLiteCursor:
    _CURDATE_RE = re.compile(r"CURDATE\(\)", re.I)
    _NOW_RE     = re.compile(r"NOW\(\)",     re.I)

    def __init__(self, cursor, dictionary=False):
        self.cursor     = cursor
        self.dictionary = dictionary
        self.lastrowid  = None

    def execute(self, query, params=None):
        query = query.replace('%s', '?')
        query = self._NOW_RE.sub('CURRENT_TIMESTAMP', query)
        query = self._CURDATE_RE.sub("date('now')", query)
        # MySQL date arithmetic  → SQLite
        query = query.replace("INTERVAL 1 DAY", "'+1 day'")
        query = query.replace("YEARWEEK(appointment_date, 1) = YEARWEEK(CURDATE(), 1)",
                              "strftime('%Y-%W', appointment_date) = strftime('%Y-%W', date('now'))")
        query = query.replace("MONTH(appointment_date) = MONTH(CURDATE()) AND YEAR(appointment_date) = YEAR(CURDATE())",
                              "strftime('%Y-%m', appointment_date) = strftime('%Y-%m', date('now'))")
        if params is None:
            self.cursor.execute(query)
        else:
            self.cursor.execute(query, params)
        self.lastrowid = self.cursor.lastrowid

    def _clean_row(self, row):
        if not row or not self.dictionary:
            return row
        d = dict(row)
        import datetime
        for k, v in d.items():
            if isinstance(v, str) and len(v) >= 10:
                # Try common ISO-ish formats
                parsed = None
                # Clean up string: remove trailing Z or +00:00 often found in ISO strings
                v_clean = v.split('+')[0].split('Z')[0].strip()
                
                if '-' in v_clean and ':' in v_clean:
                    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%S.%f'):
                        try:
                            parsed = datetime.datetime.strptime(v_clean, fmt)
                            break
                        except ValueError:
                            continue
                elif '-' in v_clean and len(v_clean) == 10:
                    try:
                        parsed = datetime.datetime.strptime(v_clean, '%Y-%m-%d')
                    except ValueError:
                        pass
                if parsed:
                    d[k] = parsed
        return d

    def __getattr__(self, name):
        return getattr(self.cursor, name)

    def fetchone(self):
        row = self.cursor.fetchone()
        return self._clean_row(row)

    def fetchall(self):
        rows = self.cursor.fetchall()
        return [self._clean_row(r) for r in rows]

    def close(self):
        self.cursor.close()


# ══════════════════════════════════════════════════════════════════════════
#  DB Wrapper
# ══════════════════════════════════════════════════════════════════════════

class DBWrapper:
    def __init__(self, conn, is_pg=False):
        self.conn  = conn
        self.is_pg = is_pg
        if not is_pg:
            self.conn.row_factory = sqlite3.Row

    def cursor(self, dictionary=False):
        if self.is_pg:
            factory = RealDictCursor if dictionary else None
            return PostgresCursor(self.conn.cursor(cursor_factory=factory), dictionary)
        return SQLiteCursor(self.conn.cursor(), dictionary)

    def commit(self):  self.conn.commit()
    def close(self):   self.conn.close()


# ══════════════════════════════════════════════════════════════════════════
#  Public API
# ══════════════════════════════════════════════════════════════════════════

def get_db():
    """Return a DB connection.  Tries blueprint g-cache first, then connects."""
    # ── 1. Return already-opened connection for this request ──────────────
    try:
        db = getattr(g, '_db', None)
        if db is not None:
            return db
    except RuntimeError:
        pass  # outside app context (e.g. init_db.py)

    # ── 2. Try PostgreSQL if known to be available ─────────────────────────
    if _check_pg_available():
        try:
            conn    = psycopg2.connect(
                host=PG_HOST, port=PG_PORT, database=PG_DB,
                user=PG_USER, password=PG_PASSWORD, connect_timeout=2
            )
            wrapper = DBWrapper(conn, is_pg=True)
            _store_g(wrapper)
            return wrapper
        except Exception:
            pass  # fall through to SQLite

    # ── 3. SQLite fallback ─────────────────────────────────────────────────
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30.0)
        # WAL mode: allows concurrent reads without locking
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=-32000")   # 32 MB page cache
        conn.execute("PRAGMA temp_store=MEMORY")
        wrapper = DBWrapper(conn, is_pg=False)
        _store_g(wrapper)
        return wrapper
    except Exception as e:
        print(f"[DB] Connection error: {e}")
        return None


def _store_g(wrapper):
    """Store wrapper in Flask g so the same connection is reused per request."""
    try:
        g._db = wrapper
    except RuntimeError:
        pass  # outside app context – fine


def update_last_activity(user_id):
    """Update last_activity at most once every 60 s per user (non-blocking)."""
    import time
    cache_key = f'_lact_{user_id}'
    now = time.time()
    try:
        last = getattr(g, cache_key, 0)
        if now - last < 60:          # throttle: max once per minute
            return
        setattr(g, cache_key, now)
    except RuntimeError:
        pass

    db = get_db()
    if not db:
        return
    try:
        cur = db.cursor()
        cur.execute(
            "UPDATE users SET last_activity = %s WHERE user_id = %s",
            (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user_id)
        )
        db.commit()
        cur.close()
    except Exception:
        pass


def can_access(permission_needed):
    if not session or 'user_id' not in session:
        return False
    role = session.get('role', '')
    if role == 'admin':
        return True
    user_perms = session.get('permissions', [])
    if permission_needed in user_perms:
        return True
    role_map = {
        'registration': ['receptionist', 'reception'],
        'triage':       ['nurse'],
        'doctor':       ['doctor'],
        'lab':          ['lab_tech', 'lab'],
        'radiology':    ['radiologist', 'rad'],
        'pharmacy':     ['pharmacist', 'pharmacy'],
        'invoices':     ['accountant'],
        'settings':     [],
        'nursing':      ['nurse', 'lab_tech', 'lab'],
    }
    if permission_needed in role_map and role in role_map[permission_needed]:
        return True
    return False
