"""
DiariCore database layer — same pattern as AnemoCheck: PostgreSQL on Railway
(via DATABASE_URL) or SQLite locally.
"""

import os
import json
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

from werkzeug.security import generate_password_hash, check_password_hash

USE_POSTGRES = bool(os.environ.get("DATABASE_URL"))
SQLITE_PATH = os.environ.get("DATABASE_PATH", "diaricore.db")

# Columns for auth-related user reads (includes TOTP secrets — never expose to client except via app serializers).
_USER_AUTH_SELECT = (
    "id, nickname, email, password_hash, first_name, last_name, gender, birthday, created_at, avatar_data_url, "
    "totp_secret, totp_enabled, totp_setup_secret, totp_setup_expires, ui_preferences_json, is_disabled, last_login"
)
_USER_PUBLIC_SELECT = (
    "id, nickname, email, first_name, last_name, gender, birthday, created_at, avatar_data_url, totp_enabled, "
    "ui_preferences_json, is_disabled, last_login"
)


def _connect_postgres():
    import psycopg2
    from psycopg2.extras import RealDictCursor

    url = os.environ["DATABASE_URL"]
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return psycopg2.connect(url, cursor_factory=RealDictCursor)


def _connect_sqlite():
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_conn():
    if USE_POSTGRES:
        return _connect_postgres()
    return _connect_sqlite()


def _ensure_journal_all_probs_column(cur):
    """Add all_probs_json to journal_entries on existing deployments."""
    if USE_POSTGRES:
        cur.execute("ALTER TABLE journal_entries ADD COLUMN IF NOT EXISTS all_probs_json TEXT")
    else:
        cur.execute("PRAGMA table_info(journal_entries)")
        cols = [r[1] for r in cur.fetchall()]
        if "all_probs_json" not in cols:
            cur.execute("ALTER TABLE journal_entries ADD COLUMN all_probs_json TEXT")


def _ensure_journal_entry_extras_columns(cur):
    """Add title/image_urls_json/entry_datetime_utc to journal_entries on existing deployments."""
    if USE_POSTGRES:
        cur.execute("ALTER TABLE journal_entries ADD COLUMN IF NOT EXISTS title TEXT")
        cur.execute("ALTER TABLE journal_entries ADD COLUMN IF NOT EXISTS image_urls_json TEXT")
        cur.execute("ALTER TABLE journal_entries ADD COLUMN IF NOT EXISTS entry_datetime_utc TEXT")
    else:
        cur.execute("PRAGMA table_info(journal_entries)")
        cols = {str(r[1]).lower() for r in (cur.fetchall() or [])}
        if "title" not in cols:
            cur.execute("ALTER TABLE journal_entries ADD COLUMN title TEXT")
        if "image_urls_json" not in cols:
            cur.execute("ALTER TABLE journal_entries ADD COLUMN image_urls_json TEXT")
        if "entry_datetime_utc" not in cols:
            cur.execute("ALTER TABLE journal_entries ADD COLUMN entry_datetime_utc TEXT")


def _ensure_journal_updated_at_column(cur):
    """Add updated_at to journal_entries; set on every UPDATE from application code."""
    if USE_POSTGRES:
        cur.execute(
            "ALTER TABLE journal_entries ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP"
        )
    else:
        cur.execute("PRAGMA table_info(journal_entries)")
        cols = {str(r[1]).lower() for r in (cur.fetchall() or [])}
        if "updated_at" not in cols:
            cur.execute("ALTER TABLE journal_entries ADD COLUMN updated_at TEXT")


def _ensure_user_tags_icon_column(cur):
    """Add icon_name to user_tags on existing deployments."""
    if USE_POSTGRES:
        cur.execute("ALTER TABLE user_tags ADD COLUMN IF NOT EXISTS icon_name TEXT")
    else:
        cur.execute("PRAGMA table_info(user_tags)")
        cols = [r[1] for r in cur.fetchall()]
        if "icon_name" not in cols:
            cur.execute("ALTER TABLE user_tags ADD COLUMN icon_name TEXT")


def _ensure_user_avatar_column(cur):
    """Add avatar_data_url (JPEG/PNG data URL) to users on existing deployments."""
    if USE_POSTGRES:
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_data_url TEXT")
    else:
        cur.execute("PRAGMA table_info(users)")
        cols = [r[1] for r in cur.fetchall()]
        if "avatar_data_url" not in cols:
            cur.execute("ALTER TABLE users ADD COLUMN avatar_data_url TEXT")


def _ensure_users_privacy_agreed_at_column(cur):
    """Privacy notice consent timestamp (set at signup after user agrees in modal)."""
    if USE_POSTGRES:
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS privacy_agreed_at TIMESTAMP")
    else:
        cur.execute("PRAGMA table_info(users)")
        cols = {str(r[1]).lower() for r in (cur.fetchall() or [])}
        if "privacy_agreed_at" not in cols:
            cur.execute("ALTER TABLE users ADD COLUMN privacy_agreed_at TEXT")


def _ensure_pending_registrations_privacy_agreed_at_column(cur):
    """Carry consent time from signup request through OTP verification to users row."""
    if USE_POSTGRES:
        cur.execute(
            "ALTER TABLE pending_registrations ADD COLUMN IF NOT EXISTS privacy_agreed_at TIMESTAMP"
        )
    else:
        cur.execute("PRAGMA table_info(pending_registrations)")
        cols = {str(r[1]).lower() for r in (cur.fetchall() or [])}
        if "privacy_agreed_at" not in cols:
            cur.execute("ALTER TABLE pending_registrations ADD COLUMN privacy_agreed_at TEXT")


def _ensure_user_ui_preferences_column(cur):
    """JSON blob for cross-device UI: theme (light|dark) and paletteId (theme-1 … theme-10)."""
    if USE_POSTGRES:
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS ui_preferences_json TEXT")
    else:
        cur.execute("PRAGMA table_info(users)")
        cols = {str(r[1]).lower() for r in (cur.fetchall() or [])}
        if "ui_preferences_json" not in cols:
            cur.execute("ALTER TABLE users ADD COLUMN ui_preferences_json TEXT")


def _ensure_user_totp_columns(cur):
    """TOTP (Google Authenticator) storage on users."""
    if USE_POSTGRES:
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS totp_secret TEXT")
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS totp_enabled BOOLEAN NOT NULL DEFAULT FALSE")
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS totp_setup_secret TEXT")
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS totp_setup_expires TIMESTAMP")
    else:
        cur.execute("PRAGMA table_info(users)")
        cols = {str(r[1]).lower() for r in (cur.fetchall() or [])}
        if "totp_secret" not in cols:
            cur.execute("ALTER TABLE users ADD COLUMN totp_secret TEXT")
        if "totp_enabled" not in cols:
            cur.execute("ALTER TABLE users ADD COLUMN totp_enabled INTEGER NOT NULL DEFAULT 0")
        if "totp_setup_secret" not in cols:
            cur.execute("ALTER TABLE users ADD COLUMN totp_setup_secret TEXT")
        if "totp_setup_expires" not in cols:
            cur.execute("ALTER TABLE users ADD COLUMN totp_setup_expires TEXT")


def _ensure_login_totp_challenges_table(cur):
    if USE_POSTGRES:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS login_totp_challenges (
                token VARCHAR(128) PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                expires_at TIMESTAMP NOT NULL
            );
            """
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_login_totp_challenges_user_id ON login_totp_challenges (user_id);"
        )
    else:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS login_totp_challenges (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_login_totp_challenges_user_id ON login_totp_challenges (user_id);")


def _ensure_login_lockouts_table(cur):
    """Persist login failures so lockouts survive process restarts and deploys."""
    if USE_POSTGRES:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS login_lockouts (
                account_key VARCHAR(128) PRIMARY KEY,
                attempts_json TEXT NOT NULL DEFAULT '[]',
                locked_until TEXT,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
    else:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS login_lockouts (
                account_key TEXT PRIMARY KEY,
                attempts_json TEXT NOT NULL DEFAULT '[]',
                locked_until TEXT,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )


OTP_RESEND_LIMIT_TABLES = {
    "register_resend": "otp_resend_limits_register_resend",
    "login_recovery": "otp_resend_limits_login_recovery",
    "email_change": "otp_resend_limits_email_change",
    "password_change": "otp_resend_limits_password_change",
    "forgot": "otp_resend_limits_forgot",
}


def _resolve_otp_resend_limit_table(flow: str) -> str:
    return OTP_RESEND_LIMIT_TABLES.get(str(flow or ""), "otp_resend_limits")


def _ensure_otp_resend_limits_tables(cur):
    """Persist per-flow OTP resend rate limits so they survive restarts and deploys."""
    for table_name in OTP_RESEND_LIMIT_TABLES.values():
        if USE_POSTGRES:
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    account_key VARCHAR(256) PRIMARY KEY,
                    attempts_json TEXT NOT NULL DEFAULT '[]',
                    locked_until TEXT,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
        else:
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    account_key TEXT PRIMARY KEY,
                    attempts_json TEXT NOT NULL DEFAULT '[]',
                    locked_until TEXT,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            )


def _ensure_login_totp_recovery_otps_table(cur):
    """One-time email codes to recover sign-in when authenticator app access is lost."""
    if USE_POSTGRES:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS login_totp_recovery_otps (
                challenge_token VARCHAR(256) PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                code VARCHAR(12) NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_login_totp_recovery_otps_user_id ON login_totp_recovery_otps (user_id);"
        )
    else:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS login_totp_recovery_otps (
                challenge_token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                code TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
            """
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_login_totp_recovery_otps_user_id ON login_totp_recovery_otps (user_id);"
        )


def _ensure_user_password_change_challenges_table(cur):
    """Email OTP while changing password from Profile (logged-in)."""
    if USE_POSTGRES:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS user_password_change_challenges (
                user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                otp_code VARCHAR(12) NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
    else:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS user_password_change_challenges (
                user_id INTEGER PRIMARY KEY,
                otp_code TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
            """
        )


def _ensure_user_profile_email_change_challenges_table(cur):
    """Email OTP + JSON payload before applying profile update when email changes (logged-in)."""
    if USE_POSTGRES:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS user_profile_email_change_challenges (
                user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                otp_code VARCHAR(12) NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                pending_payload TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
    else:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS user_profile_email_change_challenges (
                user_id INTEGER PRIMARY KEY,
                otp_code TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                pending_payload TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
            """
        )


def _ensure_user_status_columns(cur):
    """Account status (active vs disabled) and last login tracking."""
    if USE_POSTGRES:
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_disabled BOOLEAN NOT NULL DEFAULT FALSE")
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login TIMESTAMP")
    else:
        cur.execute("PRAGMA table_info(users)")
        cols = {str(r[1]).lower() for r in (cur.fetchall() or [])}
        if "is_disabled" not in cols:
            cur.execute("ALTER TABLE users ADD COLUMN is_disabled INTEGER NOT NULL DEFAULT 0")
        if "last_login" not in cols:
            cur.execute("ALTER TABLE users ADD COLUMN last_login TEXT")


def _ensure_admin_audit_logs_table(cur):
    """Audit log records for administrative activities."""
    if USE_POSTGRES:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS admin_audit_logs (
                id SERIAL PRIMARY KEY,
                admin_email VARCHAR(255) NOT NULL,
                action VARCHAR(64) NOT NULL,
                details_json TEXT,
                ip_address VARCHAR(64),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_admin_audit_logs_created ON admin_audit_logs(created_at DESC);")
    else:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS admin_audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_email TEXT NOT NULL,
                action TEXT NOT NULL,
                details_json TEXT,
                ip_address TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_admin_audit_logs_created ON admin_audit_logs(created_at DESC);")


def _ensure_push_subscriptions_table(cur):
    if USE_POSTGRES:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS push_subscriptions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                endpoint TEXT NOT NULL UNIQUE,
                subscription_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_push_subscriptions_user_id ON push_subscriptions (user_id);"
        )
    else:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS push_subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                endpoint TEXT NOT NULL UNIQUE,
                subscription_json TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            """
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_push_subscriptions_user_id ON push_subscriptions (user_id);"
        )


def _parse_expires_at(val):
    if val is None:
        return None
    if isinstance(val, datetime):
        dt = val
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    s = str(val).strip()
    if not s:
        return None
    if s.endswith("Z") or s.endswith("z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def row_to_dict(row):
    if row is None:
        return None
    if isinstance(row, dict):
        return row
    return dict(row)


def _fetchcount(cur):
    """Safely fetch a COUNT(*) scalar from a cursor that may return a dict row (RealDictCursor) or tuple row (sqlite3)."""
    row = cur.fetchone()
    if row is None:
        return 0
    if isinstance(row, dict):
        # psycopg2 RealDictCursor — grab the first (and only) value
        return int(list(row.values())[0] or 0)
    try:
        return int(row[0] or 0)
    except (IndexError, TypeError):
        return 0


def _fetchscalar(cur):
    """Fetch a single scalar value from any cursor type."""
    return _fetchcount(cur)


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    try:
        if USE_POSTGRES:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    nickname VARCHAR(64) NOT NULL UNIQUE,
                    email VARCHAR(255) NOT NULL UNIQUE,
                    password_hash VARCHAR(256) NOT NULL,
                    first_name VARCHAR(64),
                    last_name VARCHAR(64),
                    gender VARCHAR(32),
                    birthday DATE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS pending_registrations (
                    email VARCHAR(255) PRIMARY KEY,
                    nickname VARCHAR(64) NOT NULL,
                    password_hash VARCHAR(256) NOT NULL,
                    first_name VARCHAR(64),
                    last_name VARCHAR(64),
                    gender VARCHAR(32),
                    birthday DATE,
                    otp_code VARCHAR(6) NOT NULL,
                    otp_expires_at TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS password_resets (
                    email VARCHAR(255) PRIMARY KEY,
                    reset_code VARCHAR(6) NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS journal_entries (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    title TEXT,
                    entry_datetime_utc TEXT,
                    text_content TEXT NOT NULL,
                    tags_json TEXT,
                    sentiment_label VARCHAR(32) NOT NULL,
                    sentiment_score REAL NOT NULL,
                    emotion_label VARCHAR(32) NOT NULL,
                    emotion_score REAL NOT NULL,
                    all_probs_json TEXT,
                    image_urls_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS user_tags (
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    tag VARCHAR(128) NOT NULL,
                    icon_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, tag)
                );
                """
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_user_tags_user_id ON user_tags (user_id);"
            )
        else:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nickname TEXT NOT NULL UNIQUE,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    first_name TEXT,
                    last_name TEXT,
                    gender TEXT,
                    birthday TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS pending_registrations (
                    email TEXT PRIMARY KEY,
                    nickname TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    first_name TEXT,
                    last_name TEXT,
                    gender TEXT,
                    birthday TEXT,
                    otp_code TEXT NOT NULL,
                    otp_expires_at TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS password_resets (
                    email TEXT PRIMARY KEY,
                    reset_code TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS journal_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    title TEXT,
                    entry_datetime_utc TEXT,
                    text_content TEXT NOT NULL,
                    tags_json TEXT,
                    sentiment_label TEXT NOT NULL,
                    sentiment_score REAL NOT NULL,
                    emotion_label TEXT NOT NULL,
                    emotion_score REAL NOT NULL,
                    all_probs_json TEXT,
                    image_urls_json TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS user_tags (
                    user_id INTEGER NOT NULL,
                    tag TEXT NOT NULL,
                    icon_name TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, tag),
                    FOREIGN KEY(user_id) REFERENCES users(id)
                );
                """
            )
            cur.execute("CREATE INDEX IF NOT EXISTS idx_user_tags_user_id ON user_tags (user_id);")
        _ensure_journal_all_probs_column(cur)
        _ensure_journal_entry_extras_columns(cur)
        _ensure_journal_updated_at_column(cur)
        _ensure_user_tags_icon_column(cur)
        _ensure_user_avatar_column(cur)
        _ensure_users_privacy_agreed_at_column(cur)
        _ensure_pending_registrations_privacy_agreed_at_column(cur)
        _ensure_user_ui_preferences_column(cur)
        _ensure_user_totp_columns(cur)
        _ensure_login_totp_challenges_table(cur)
        _ensure_login_lockouts_table(cur)
        _ensure_otp_resend_limits_tables(cur)
        _ensure_login_totp_recovery_otps_table(cur)
        _ensure_user_password_change_challenges_table(cur)
        _ensure_user_profile_email_change_challenges_table(cur)
        _ensure_user_status_columns(cur)
        _ensure_admin_audit_logs_table(cur)
        _ensure_push_subscriptions_table(cur)
        if USE_POSTGRES:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS system_settings (
                    key VARCHAR(128) PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
        else:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS system_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
        conn.commit()
    finally:
        conn.close()


def _normalize_tag_value(tag: str) -> str:
    s = str(tag or "").strip()
    s = " ".join(s.split())
    return s[:128]


def list_user_tags(user_id: int):
    conn = get_conn()
    cur = conn.cursor()
    try:
        if USE_POSTGRES:
            cur.execute(
                """
                SELECT tag, icon_name, created_at
                FROM user_tags
                WHERE user_id = %s
                ORDER BY created_at ASC, tag ASC
                """,
                (user_id,),
            )
        else:
            cur.execute(
                """
                SELECT tag, icon_name, created_at
                FROM user_tags
                WHERE user_id = ?
                ORDER BY datetime(created_at) ASC, tag ASC
                """,
                (user_id,),
            )
        return [row_to_dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def add_user_tag(*, user_id: int, tag: str, icon_name: str | None = None) -> bool:
    t = _normalize_tag_value(tag)
    icon = str(icon_name or "").strip().lower()[:96] or None
    if not t or user_id <= 0:
        return False
    conn = get_conn()
    cur = conn.cursor()
    try:
        if USE_POSTGRES:
            cur.execute(
                """
                INSERT INTO user_tags (user_id, tag, icon_name)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id, tag) DO UPDATE SET
                    icon_name = COALESCE(EXCLUDED.icon_name, user_tags.icon_name)
                """,
                (user_id, t, icon),
            )
        else:
            cur.execute(
                """
                INSERT INTO user_tags (user_id, tag, icon_name, created_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id, tag) DO UPDATE SET
                    icon_name = COALESCE(excluded.icon_name, user_tags.icon_name)
                """,
                (user_id, t, icon),
            )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()


def delete_user_tag(*, user_id: int, tag: str) -> bool:
    t = _normalize_tag_value(tag)
    if not t or user_id <= 0:
        return False
    t_key = t.lower()
    conn = get_conn()
    cur = conn.cursor()
    try:
        if USE_POSTGRES:
            cur.execute(
                "SELECT id, tags_json FROM journal_entries WHERE user_id = %s",
                (user_id,),
            )
        else:
            cur.execute(
                "SELECT id, tags_json FROM journal_entries WHERE user_id = ?",
                (user_id,),
            )
        rows = [row_to_dict(r) for r in cur.fetchall()]
        for row in rows:
            eid = int(row["id"])
            raw = row.get("tags_json") or "[]"
            try:
                parsed = json.loads(raw)
            except Exception:
                continue
            if not isinstance(parsed, list):
                continue
            new_tags = [x for x in parsed if str(x or "").strip().lower() != t_key]
            if len(new_tags) == len(parsed):
                continue
            new_json = json.dumps(new_tags)
            if USE_POSTGRES:
                cur.execute(
                    """
                    UPDATE journal_entries
                    SET tags_json = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s AND user_id = %s
                    """,
                    (new_json, eid, user_id),
                )
            else:
                cur.execute(
                    """
                    UPDATE journal_entries
                    SET tags_json = ?, updated_at = datetime('now')
                    WHERE id = ? AND user_id = ?
                    """,
                    (new_json, eid, user_id),
                )

        if USE_POSTGRES:
            cur.execute(
                "DELETE FROM user_tags WHERE user_id = %s AND tag = %s",
                (user_id, t),
            )
        else:
            cur.execute(
                "DELETE FROM user_tags WHERE user_id = ? AND tag = ?",
                (user_id, t),
            )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()


def get_user_by_email(email: str):
    conn = get_conn()
    cur = conn.cursor()
    try:
        if USE_POSTGRES:
            cur.execute(
                "SELECT "
                + _USER_AUTH_SELECT
                + " FROM users WHERE lower(trim(email)) = lower(trim(%s))",
                (email,),
            )
        else:
            cur.execute(
                "SELECT " + _USER_AUTH_SELECT + " FROM users WHERE lower(email) = ?",
                (email.lower().strip(),),
            )
        return row_to_dict(cur.fetchone())
    finally:
        conn.close()


def get_user_by_nickname(nickname: str):
    conn = get_conn()
    cur = conn.cursor()
    try:
        if USE_POSTGRES:
            cur.execute(
                "SELECT " + _USER_AUTH_SELECT + " FROM users WHERE lower(nickname) = %s",
                (nickname.lower().strip(),),
            )
        else:
            cur.execute(
                "SELECT " + _USER_AUTH_SELECT + " FROM users WHERE lower(nickname) = ?",
                (nickname.lower().strip(),),
            )
        return row_to_dict(cur.fetchone())
    finally:
        conn.close()


def get_user_by_username(username: str):
    return get_user_by_nickname(username)


def get_login_lockout_key(identifier: str) -> str:
    """Return one stable lockout key for either sign-in identifier of an account."""
    normalized = (identifier or "").strip().lower()
    user = get_user_by_email(normalized) if "@" in normalized else None
    if not user:
        user = get_user_by_username(normalized)
    if user:
        return f"user:{int(user['id'])}"
    return f"identifier:{normalized}"


def _parse_lockout_timestamp(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def get_login_lockout(account_key: str):
    conn = get_conn()
    cur = conn.cursor()
    try:
        placeholder = "%s" if USE_POSTGRES else "?"
        cur.execute(
            f"SELECT attempts_json, locked_until FROM login_lockouts WHERE account_key = {placeholder}",
            (account_key,),
        )
        row = row_to_dict(cur.fetchone())
        if not row:
            return [], None
        try:
            attempts = json.loads(row.get("attempts_json") or "[]")
            attempts = [str(attempt) for attempt in attempts if isinstance(attempt, str)]
        except (TypeError, ValueError):
            attempts = []
        return attempts, _parse_lockout_timestamp(row.get("locked_until"))
    finally:
        conn.close()


def save_login_lockout(account_key: str, attempts: list[str], locked_until) -> bool:
    conn = get_conn()
    cur = conn.cursor()
    try:
        attempts_json = json.dumps(attempts, separators=(",", ":"))
        locked_value = locked_until.isoformat() if locked_until else None
        if USE_POSTGRES:
            cur.execute(
                """
                INSERT INTO login_lockouts (account_key, attempts_json, locked_until, updated_at)
                VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (account_key) DO UPDATE SET
                    attempts_json = EXCLUDED.attempts_json,
                    locked_until = EXCLUDED.locked_until,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (account_key, attempts_json, locked_value),
            )
        else:
            cur.execute(
                """
                INSERT INTO login_lockouts (account_key, attempts_json, locked_until, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(account_key) DO UPDATE SET
                    attempts_json = excluded.attempts_json,
                    locked_until = excluded.locked_until,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (account_key, attempts_json, locked_value),
            )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()


def clear_login_lockout(account_key: str) -> None:
    conn = get_conn()
    cur = conn.cursor()
    try:
        placeholder = "%s" if USE_POSTGRES else "?"
        cur.execute(f"DELETE FROM login_lockouts WHERE account_key = {placeholder}", (account_key,))
        conn.commit()
    finally:
        conn.close()


def get_otp_resend_limit(flow: str, account_key: str):
    conn = get_conn()
    cur = conn.cursor()
    try:
        table_name = _resolve_otp_resend_limit_table(flow)
        placeholder = "%s" if USE_POSTGRES else "?"
        cur.execute(
            f"SELECT attempts_json, locked_until FROM {table_name} WHERE account_key = {placeholder}",
            (account_key,),
        )
        row = row_to_dict(cur.fetchone())
        if not row:
            return [], None
        try:
            attempts = json.loads(row.get("attempts_json") or "[]")
            attempts = [str(a) for a in attempts if isinstance(a, str)]
        except (TypeError, ValueError):
            attempts = []
        return attempts, _parse_lockout_timestamp(row.get("locked_until"))
    finally:
        conn.close()


def save_otp_resend_limit(flow: str, account_key: str, attempts: list[str], locked_until) -> bool:
    conn = get_conn()
    cur = conn.cursor()
    try:
        table_name = _resolve_otp_resend_limit_table(flow)
        attempts_json = json.dumps(attempts, separators=(",", ":"))
        locked_value = locked_until.isoformat() if locked_until else None
        if USE_POSTGRES:
            cur.execute(
                f"""
                INSERT INTO {table_name} (account_key, attempts_json, locked_until, updated_at)
                VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (account_key) DO UPDATE SET
                    attempts_json = EXCLUDED.attempts_json,
                    locked_until = EXCLUDED.locked_until,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (account_key, attempts_json, locked_value),
            )
        else:
            cur.execute(
                f"""
                INSERT INTO {table_name} (account_key, attempts_json, locked_until, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(account_key) DO UPDATE SET
                    attempts_json = excluded.attempts_json,
                    locked_until = excluded.locked_until,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (account_key, attempts_json, locked_value),
            )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()


def get_user_by_id(user_id: int):
    conn = get_conn()
    cur = conn.cursor()
    try:
        if USE_POSTGRES:
            cur.execute(
                "SELECT " + _USER_AUTH_SELECT + " FROM users WHERE id = %s",
                (user_id,),
            )
        else:
            cur.execute(
                "SELECT " + _USER_AUTH_SELECT + " FROM users WHERE id = ?",
                (user_id,),
            )
        return row_to_dict(cur.fetchone())
    finally:
        conn.close()


def update_user_avatar_data_url(user_id: int, avatar_data_url: str | None) -> bool:
    """Persist profile photo as a data URL (or NULL to clear)."""
    if not isinstance(user_id, int) or user_id <= 0:
        return False
    val = None
    if isinstance(avatar_data_url, str) and avatar_data_url.strip():
        val = avatar_data_url.strip()
    conn = get_conn()
    cur = conn.cursor()
    try:
        if USE_POSTGRES:
            cur.execute(
                "UPDATE users SET avatar_data_url = %s WHERE id = %s",
                (val, user_id),
            )
        else:
            cur.execute(
                "UPDATE users SET avatar_data_url = ? WHERE id = ?",
                (val, user_id),
            )
        conn.commit()
        return cur.rowcount > 0
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()


def update_user_ui_preferences(user_id: int, theme: str | None, palette_id: str | None) -> bool:
    """
    Merge theme (light|dark) and/or paletteId into users.ui_preferences_json.
    Pass None to leave that key unchanged.
    """
    if not isinstance(user_id, int) or user_id <= 0:
        return False
    row = get_user_by_id(user_id)
    if not row:
        return False
    cur: dict = {}
    raw = row.get("ui_preferences_json")
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                cur = parsed
        except Exception:
            cur = {}
    if theme in ("light", "dark"):
        cur["theme"] = theme
    if palette_id and isinstance(palette_id, str) and palette_id.strip():
        cur["paletteId"] = palette_id.strip()
    blob = json.dumps(cur, separators=(",", ":"))

    conn = get_conn()
    cur_sql = conn.cursor()
    try:
        if USE_POSTGRES:
            cur_sql.execute(
                "UPDATE users SET ui_preferences_json = %s WHERE id = %s",
                (blob, user_id),
            )
        else:
            cur_sql.execute(
                "UPDATE users SET ui_preferences_json = ? WHERE id = ?",
                (blob, user_id),
            )
        conn.commit()
        return cur_sql.rowcount > 0
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()


def update_user_profile(
    user_id: int,
    first_name: str,
    last_name: str,
    nickname: str,
    email: str,
    gender: str | None,
    birthday: str | None,
) -> tuple[bool, str | None, str | None]:
    """
    Persist personal profile fields. Returns (True, None, None) on success,
    or (False, field_key, error_message) on validation/unique conflict.
    field_key is 'nickname' or 'email' for uniqueness errors.
    """
    if not isinstance(user_id, int) or user_id <= 0:
        return False, None, "Invalid user."
    fn = (first_name or "").strip()
    ln = (last_name or "").strip()
    nick = (nickname or "").strip()
    em = (email or "").strip().lower()
    if not fn or not ln:
        return False, None, "First and last name are required."
    if not nick or len(nick) < 4 or len(nick) > 64:
        return False, "nickname", "Username must be between 4 and 64 characters."
    if not em or "@" not in em:
        return False, "email", "A valid email is required."
    g = (gender or "").strip() or None
    bday = (birthday or "").strip() or None

    conn = get_conn()
    cur = conn.cursor()
    try:
        if USE_POSTGRES:
            cur.execute(
                """
                UPDATE users
                SET first_name = %s, last_name = %s, nickname = %s, email = %s, gender = %s, birthday = %s
                WHERE id = %s
                """,
                (fn, ln, nick, em, g, bday, user_id),
            )
        else:
            cur.execute(
                """
                UPDATE users
                SET first_name = ?, last_name = ?, nickname = ?, email = ?, gender = ?, birthday = ?
                WHERE id = ?
                """,
                (fn, ln, nick, em, g, bday, user_id),
            )
        if cur.rowcount <= 0:
            conn.rollback()
            return False, None, "User not found."
        conn.commit()
        return True, None, None
    except Exception as e:
        conn.rollback()
        err = str(e).lower()
        if any(s in err for s in ("unique", "duplicate", "integrity")):
            if "nickname" in err:
                return False, "nickname", "Username already exists."
            if "email" in err:
                return False, "email", "Email already exists."
        return False, None, "Could not save profile. Please try again."
    finally:
        conn.close()


def create_user(
    nickname: str,
    email: str,
    password: str,
    first_name: str,
    last_name: str,
    gender: str,
    birthday: str,
):
    """Returns (True, user_dict) or (False, field_id, error_message)."""
    password_hash = generate_password_hash(password)
    email_norm = email.lower().strip()
    nickname_norm = nickname.strip()

    conn = get_conn()
    cur = conn.cursor()
    try:
        if USE_POSTGRES:
            cur.execute(
                """
                INSERT INTO users (nickname, email, password_hash, first_name, last_name, gender, birthday)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id, nickname, email, first_name, last_name, gender, birthday, created_at, avatar_data_url, totp_enabled, ui_preferences_json
                """,
                (nickname_norm, email_norm, password_hash, first_name.strip(), last_name.strip(), gender, birthday),
            )
            row = cur.fetchone()
            conn.commit()
            u = row_to_dict(row)
            u.pop("password_hash", None)
            return True, u
        else:
            cur.execute(
                """
                INSERT INTO users (nickname, email, password_hash, first_name, last_name, gender, birthday)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    nickname_norm,
                    email_norm,
                    password_hash,
                    first_name.strip(),
                    last_name.strip(),
                    gender,
                    birthday,
                ),
            )
            uid = cur.lastrowid
            conn.commit()
            cur.execute(
                "SELECT " + _USER_PUBLIC_SELECT + " FROM users WHERE id = ?",
                (uid,),
            )
            u = row_to_dict(cur.fetchone())
            return True, u
    except Exception as e:
        conn.rollback()
        err = str(e).lower()
        if any(s in err for s in ("unique", "duplicate", "already exists")):
            if "nickname" in err:
                return False, "nickname", "Username already exists."
            if "email" in err:
                return False, "signUpEmail", "Email already exists."
        return False, None, "Could not create account. Please try again."
    finally:
        conn.close()


def store_pending_registration(
    *,
    nickname: str,
    email: str,
    password: str,
    first_name: str,
    last_name: str,
    gender: str,
    birthday: str,
    otp_code: str,
    otp_expires_at,
    privacy_agreed_at=None,
):
    email_norm = email.lower().strip()
    nickname_norm = nickname.strip()
    password_hash = generate_password_hash(password)

    conn = get_conn()
    cur = conn.cursor()
    try:
        if USE_POSTGRES:
            cur.execute(
                """
                INSERT INTO pending_registrations
                (email, nickname, password_hash, first_name, last_name, gender, birthday, otp_code, otp_expires_at, privacy_agreed_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (email) DO UPDATE SET
                    nickname = EXCLUDED.nickname,
                    password_hash = EXCLUDED.password_hash,
                    first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name,
                    gender = EXCLUDED.gender,
                    birthday = EXCLUDED.birthday,
                    otp_code = EXCLUDED.otp_code,
                    otp_expires_at = EXCLUDED.otp_expires_at,
                    privacy_agreed_at = EXCLUDED.privacy_agreed_at,
                    created_at = CURRENT_TIMESTAMP
                """,
                (
                    email_norm,
                    nickname_norm,
                    password_hash,
                    first_name.strip(),
                    last_name.strip(),
                    gender,
                    birthday,
                    otp_code,
                    otp_expires_at,
                    privacy_agreed_at,
                ),
            )
        else:
            pa_sqlite = privacy_agreed_at
            if pa_sqlite is not None and not isinstance(pa_sqlite, str):
                try:
                    pa_sqlite = pa_sqlite.isoformat()
                except Exception:
                    pa_sqlite = str(pa_sqlite)
            cur.execute(
                """
                INSERT INTO pending_registrations
                (email, nickname, password_hash, first_name, last_name, gender, birthday, otp_code, otp_expires_at, privacy_agreed_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(email) DO UPDATE SET
                    nickname = excluded.nickname,
                    password_hash = excluded.password_hash,
                    first_name = excluded.first_name,
                    last_name = excluded.last_name,
                    gender = excluded.gender,
                    birthday = excluded.birthday,
                    otp_code = excluded.otp_code,
                    otp_expires_at = excluded.otp_expires_at,
                    privacy_agreed_at = excluded.privacy_agreed_at,
                    created_at = CURRENT_TIMESTAMP
                """,
                (
                    email_norm,
                    nickname_norm,
                    password_hash,
                    first_name.strip(),
                    last_name.strip(),
                    gender,
                    birthday,
                    otp_code,
                    str(otp_expires_at),
                    pa_sqlite,
                ),
            )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()


def get_pending_registration(email: str):
    email_norm = email.lower().strip()
    conn = get_conn()
    cur = conn.cursor()
    try:
        if USE_POSTGRES:
            cur.execute("SELECT * FROM pending_registrations WHERE email = %s", (email_norm,))
        else:
            cur.execute("SELECT * FROM pending_registrations WHERE lower(email) = ?", (email_norm,))
        return row_to_dict(cur.fetchone())
    finally:
        conn.close()


def update_pending_otp(email: str, otp_code: str, otp_expires_at):
    email_norm = email.lower().strip()
    conn = get_conn()
    cur = conn.cursor()
    try:
        if USE_POSTGRES:
            cur.execute(
                "UPDATE pending_registrations SET otp_code = %s, otp_expires_at = %s WHERE email = %s",
                (otp_code, otp_expires_at, email_norm),
            )
        else:
            cur.execute(
                "UPDATE pending_registrations SET otp_code = ?, otp_expires_at = ? WHERE lower(email) = ?",
                (otp_code, str(otp_expires_at), email_norm),
            )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def delete_pending_registration(email: str):
    email_norm = email.lower().strip()
    conn = get_conn()
    cur = conn.cursor()
    try:
        if USE_POSTGRES:
            cur.execute("DELETE FROM pending_registrations WHERE email = %s", (email_norm,))
        else:
            cur.execute("DELETE FROM pending_registrations WHERE lower(email) = ?", (email_norm,))
        conn.commit()
    finally:
        conn.close()


def _privacy_agreed_at_from_pending(pending: dict):
    raw = pending.get("privacy_agreed_at")
    if raw is None:
        return None
    if isinstance(raw, datetime):
        dt = raw
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def create_user_from_pending(pending: dict):
    conn = get_conn()
    cur = conn.cursor()
    try:
        privacy_at = _privacy_agreed_at_from_pending(pending)
        if USE_POSTGRES:
            cur.execute(
                """
                INSERT INTO users (nickname, email, password_hash, first_name, last_name, gender, birthday, privacy_agreed_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, nickname, email, first_name, last_name, gender, birthday, created_at, avatar_data_url, totp_enabled, ui_preferences_json
                """,
                (
                    (pending.get("nickname") or "").strip(),
                    (pending.get("email") or "").lower().strip(),
                    pending.get("password_hash"),
                    (pending.get("first_name") or "").strip(),
                    (pending.get("last_name") or "").strip(),
                    pending.get("gender"),
                    pending.get("birthday"),
                    privacy_at,
                ),
            )
            row = cur.fetchone()
            conn.commit()
            return True, row_to_dict(row)
        pa_sqlite = None
        if privacy_at is not None:
            try:
                pa_sqlite = privacy_at.isoformat()
            except Exception:
                pa_sqlite = str(privacy_at)
        cur.execute(
            """
            INSERT INTO users (nickname, email, password_hash, first_name, last_name, gender, birthday, privacy_agreed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                (pending.get("nickname") or "").strip(),
                (pending.get("email") or "").lower().strip(),
                pending.get("password_hash"),
                (pending.get("first_name") or "").strip(),
                (pending.get("last_name") or "").strip(),
                pending.get("gender"),
                pending.get("birthday"),
                pa_sqlite,
            ),
        )
        uid = cur.lastrowid
        conn.commit()
        cur.execute(
            "SELECT " + _USER_PUBLIC_SELECT + " FROM users WHERE id = ?",
            (uid,),
        )
        return True, row_to_dict(cur.fetchone())
    except Exception as e:
        conn.rollback()
        err = str(e).lower()
        if "nickname" in err:
            return False, ("nickname", "Username already exists.")
        if "email" in err:
            return False, ("signUpEmail", "Email already exists.")
        return False, (None, "Could not create account. Please try again.")
    finally:
        conn.close()


def get_system_setting(key: str, default=None):
    conn = get_conn()
    cur = conn.cursor()
    try:
        if USE_POSTGRES:
            cur.execute("SELECT value FROM system_settings WHERE key = %s", (key,))
        else:
            cur.execute("SELECT value FROM system_settings WHERE key = ?", (key,))
        row = cur.fetchone()
        if not row:
            return default
        if isinstance(row, dict):
            return row.get("value", default)
        return row[0] if row[0] is not None else default
    finally:
        conn.close()


def set_system_setting(key: str, value: str):
    conn = get_conn()
    cur = conn.cursor()
    try:
        if USE_POSTGRES:
            cur.execute(
                """
                INSERT INTO system_settings (key, value, updated_at)
                VALUES (%s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (key) DO UPDATE SET
                    value = EXCLUDED.value,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (key, value),
            )
        else:
            cur.execute(
                """
                INSERT INTO system_settings (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (key, value),
            )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()


def verify_user_password_by_id(user_id: int, password: str) -> bool:
    if not isinstance(user_id, int) or user_id <= 0 or not password:
        return False
    user = get_user_by_id(user_id)
    if not user or not user.get("password_hash"):
        return False
    return check_password_hash(user["password_hash"], password)


def create_login_totp_challenge(user_id: int) -> str | None:
    if not isinstance(user_id, int) or user_id <= 0:
        return None
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(minutes=5)
    conn = get_conn()
    cur = conn.cursor()
    try:
        if USE_POSTGRES:
            cur.execute("DELETE FROM login_totp_challenges WHERE user_id = %s", (user_id,))
            cur.execute(
                "INSERT INTO login_totp_challenges (token, user_id, expires_at) VALUES (%s, %s, %s)",
                (token, user_id, expires),
            )
        else:
            cur.execute("DELETE FROM login_totp_challenges WHERE user_id = ?", (user_id,))
            cur.execute(
                "INSERT INTO login_totp_challenges (token, user_id, expires_at) VALUES (?, ?, ?)",
                (token, user_id, expires.isoformat()),
            )
        conn.commit()
        return token
    except Exception:
        conn.rollback()
        return None
    finally:
        conn.close()


def peek_login_totp_challenge_user_id(token: str) -> int | None:
    raw = (token or "").strip()
    if len(raw) < 8:
        return None
    conn = get_conn()
    cur = conn.cursor()
    try:
        if USE_POSTGRES:
            cur.execute(
                "SELECT user_id, expires_at FROM login_totp_challenges WHERE token = %s",
                (raw,),
            )
        else:
            cur.execute(
                "SELECT user_id, expires_at FROM login_totp_challenges WHERE token = ?",
                (raw,),
            )
        row = row_to_dict(cur.fetchone())
        if not row:
            return None
        exp = _parse_expires_at(row.get("expires_at"))
        now = datetime.now(timezone.utc)
        if exp is None or now > exp:
            if USE_POSTGRES:
                cur.execute("DELETE FROM login_totp_challenges WHERE token = %s", (raw,))
            else:
                cur.execute("DELETE FROM login_totp_challenges WHERE token = ?", (raw,))
            conn.commit()
            return None
        uid = int(row["user_id"])
        return uid if uid > 0 else None
    finally:
        conn.close()


def delete_login_totp_challenge(token: str) -> None:
    raw = (token or "").strip()
    if not raw:
        return
    conn = get_conn()
    cur = conn.cursor()
    try:
        if USE_POSTGRES:
            cur.execute("DELETE FROM login_totp_challenges WHERE token = %s", (raw,))
        else:
            cur.execute("DELETE FROM login_totp_challenges WHERE token = ?", (raw,))
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        conn.close()


def clear_login_totp_challenges_for_user(user_id: int) -> None:
    """Remove any in-progress login TOTP challenges for this user (e.g. after admin 2FA reset)."""
    if not isinstance(user_id, int) or user_id <= 0:
        return
    conn = get_conn()
    cur = conn.cursor()
    try:
        if USE_POSTGRES:
            cur.execute("DELETE FROM login_totp_challenges WHERE user_id = %s", (user_id,))
        else:
            cur.execute("DELETE FROM login_totp_challenges WHERE user_id = ?", (user_id,))
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        conn.close()


def delete_login_totp_recovery_otp_for_challenge(challenge_token: str) -> None:
    raw = (challenge_token or "").strip()
    if not raw:
        return
    conn = get_conn()
    cur = conn.cursor()
    try:
        if USE_POSTGRES:
            cur.execute("DELETE FROM login_totp_recovery_otps WHERE challenge_token = %s", (raw,))
        else:
            cur.execute("DELETE FROM login_totp_recovery_otps WHERE challenge_token = ?", (raw,))
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        conn.close()


def get_login_totp_recovery_otp_row(challenge_token: str):
    raw = (challenge_token or "").strip()
    if not raw:
        return None
    conn = get_conn()
    cur = conn.cursor()
    try:
        if USE_POSTGRES:
            cur.execute(
                """
                SELECT challenge_token, user_id, code, expires_at, created_at
                FROM login_totp_recovery_otps
                WHERE challenge_token = %s
                """,
                (raw,),
            )
        else:
            cur.execute(
                """
                SELECT challenge_token, user_id, code, expires_at, created_at
                FROM login_totp_recovery_otps
                WHERE challenge_token = ?
                """,
                (raw,),
            )
        return row_to_dict(cur.fetchone())
    finally:
        conn.close()


def upsert_login_totp_recovery_otp(challenge_token: str, user_id: int, code: str, expires_at: datetime) -> bool:
    raw_tok = (challenge_token or "").strip()
    if not raw_tok or not isinstance(user_id, int) or user_id <= 0:
        return False
    code_s = "".join(ch for ch in str(code or "") if ch.isdigit())[:6]
    if len(code_s) != 6:
        return False
    conn = get_conn()
    cur = conn.cursor()
    try:
        if USE_POSTGRES:
            cur.execute(
                """
                INSERT INTO login_totp_recovery_otps (challenge_token, user_id, code, expires_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (challenge_token) DO UPDATE SET
                    user_id = EXCLUDED.user_id,
                    code = EXCLUDED.code,
                    expires_at = EXCLUDED.expires_at,
                    created_at = CURRENT_TIMESTAMP
                """,
                (raw_tok, user_id, code_s, expires_at),
            )
        else:
            cur.execute("DELETE FROM login_totp_recovery_otps WHERE challenge_token = ?", (raw_tok,))
            cur.execute(
                """
                INSERT INTO login_totp_recovery_otps (challenge_token, user_id, code, expires_at, created_at)
                VALUES (?, ?, ?, ?, datetime('now'))
                """,
                (raw_tok, user_id, code_s, expires_at.isoformat()),
            )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()


def set_totp_setup_pending(user_id: int, secret: str) -> bool:
    if not isinstance(user_id, int) or user_id <= 0 or not secret:
        return False
    expires = datetime.now(timezone.utc) + timedelta(minutes=15)
    conn = get_conn()
    cur = conn.cursor()
    try:
        if USE_POSTGRES:
            cur.execute(
                """
                UPDATE users
                SET totp_setup_secret = %s, totp_setup_expires = %s
                WHERE id = %s
                """,
                (secret.strip(), expires, user_id),
            )
        else:
            cur.execute(
                """
                UPDATE users
                SET totp_setup_secret = ?, totp_setup_expires = ?
                WHERE id = ?
                """,
                (secret.strip(), expires.isoformat(), user_id),
            )
        conn.commit()
        return cur.rowcount > 0
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()


def clear_totp_setup_pending(user_id: int) -> bool:
    if not isinstance(user_id, int) or user_id <= 0:
        return False
    conn = get_conn()
    cur = conn.cursor()
    try:
        if USE_POSTGRES:
            cur.execute(
                "UPDATE users SET totp_setup_secret = NULL, totp_setup_expires = NULL WHERE id = %s",
                (user_id,),
            )
        else:
            cur.execute(
                "UPDATE users SET totp_setup_secret = NULL, totp_setup_expires = NULL WHERE id = ?",
                (user_id,),
            )
        conn.commit()
        return cur.rowcount > 0
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()


def get_totp_setup_pending_secret(user_id: int) -> str | None:
    u = get_user_by_id(user_id)
    if not u:
        return None
    sec = u.get("totp_setup_secret")
    if not sec or not str(sec).strip():
        return None
    exp = _parse_expires_at(u.get("totp_setup_expires"))
    now = datetime.now(timezone.utc)
    if exp is None or now > exp:
        clear_totp_setup_pending(user_id)
        return None
    return str(sec).strip()


def commit_totp_secret_enabled(user_id: int, secret: str) -> bool:
    if not isinstance(user_id, int) or user_id <= 0 or not secret:
        return False
    s = secret.strip()
    conn = get_conn()
    cur = conn.cursor()
    try:
        if USE_POSTGRES:
            cur.execute(
                """
                UPDATE users
                SET totp_secret = %s, totp_enabled = TRUE,
                    totp_setup_secret = NULL, totp_setup_expires = NULL
                WHERE id = %s
                """,
                (s, user_id),
            )
        else:
            cur.execute(
                """
                UPDATE users
                SET totp_secret = ?, totp_enabled = 1,
                    totp_setup_secret = NULL, totp_setup_expires = NULL
                WHERE id = ?
                """,
                (s, user_id),
            )
        conn.commit()
        return cur.rowcount > 0
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()


def disable_totp_for_user(user_id: int) -> bool:
    if not isinstance(user_id, int) or user_id <= 0:
        return False
    conn = get_conn()
    cur = conn.cursor()
    try:
        if USE_POSTGRES:
            cur.execute(
                """
                UPDATE users
                SET totp_secret = NULL, totp_enabled = FALSE,
                    totp_setup_secret = NULL, totp_setup_expires = NULL
                WHERE id = %s
                """,
                (user_id,),
            )
        else:
            cur.execute(
                """
                UPDATE users
                SET totp_secret = NULL, totp_enabled = 0,
                    totp_setup_secret = NULL, totp_setup_expires = NULL
                WHERE id = ?
                """,
                (user_id,),
            )
        conn.commit()
        return cur.rowcount > 0
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()


def verify_login(identifier: str, password: str):
    """Returns (True, user_dict, None) or (False, error_message, reason).

    reason is one of 'not_found', 'bad_password', 'disabled', or None on success.
    Only 'bad_password' should count toward the failed-attempt lockout, so callers
    can show the attempt counter for real accounts while keeping a plain message
    for usernames/emails that do not exist.
    """
    raw = (identifier or "").strip()
    if not raw:
        return False, "Incorrect username or password.", "not_found"

    user = None
    if "@" in raw:
        user = get_user_by_email(raw)
    if not user:
        user = get_user_by_username(raw)
    if not user:
        return False, "Incorrect username or password.", "not_found"
    if not check_password_hash(user["password_hash"], password):
        return False, "Incorrect username or password.", "bad_password"
    if user.get("is_disabled") in (True, 1, "true", "1"):
        return False, "Your account has been deactivated by an administrator.", "disabled"
    out = {k: v for k, v in user.items() if k != "password_hash"}
    return True, out, None


def store_password_reset(email: str, reset_code: str, expires_at):
    email_norm = (email or "").strip().lower()
    conn = get_conn()
    cur = conn.cursor()
    try:
        if USE_POSTGRES:
            cur.execute(
                """
                INSERT INTO password_resets (email, reset_code, expires_at, created_at)
                VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (email) DO UPDATE SET
                    reset_code = EXCLUDED.reset_code,
                    expires_at = EXCLUDED.expires_at,
                    created_at = CURRENT_TIMESTAMP
                """,
                (email_norm, reset_code, expires_at),
            )
        else:
            cur.execute(
                """
                INSERT INTO password_resets (email, reset_code, expires_at, created_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(email) DO UPDATE SET
                    reset_code = excluded.reset_code,
                    expires_at = excluded.expires_at,
                    created_at = CURRENT_TIMESTAMP
                """,
                (email_norm, reset_code, str(expires_at)),
            )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()


def get_password_reset(email: str):
    email_norm = (email or "").strip().lower()
    conn = get_conn()
    cur = conn.cursor()
    try:
        if USE_POSTGRES:
            cur.execute("SELECT * FROM password_resets WHERE email = %s", (email_norm,))
        else:
            cur.execute("SELECT * FROM password_resets WHERE lower(email) = ?", (email_norm,))
        return row_to_dict(cur.fetchone())
    finally:
        conn.close()


def delete_password_reset(email: str):
    email_norm = (email or "").strip().lower()
    conn = get_conn()
    cur = conn.cursor()
    try:
        if USE_POSTGRES:
            cur.execute("DELETE FROM password_resets WHERE email = %s", (email_norm,))
        else:
            cur.execute("DELETE FROM password_resets WHERE lower(email) = ?", (email_norm,))
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()


def update_user_password_by_email(email: str, password: str):
    email_norm = (email or "").strip().lower()
    password_hash = generate_password_hash(password)
    conn = get_conn()
    cur = conn.cursor()
    try:
        if USE_POSTGRES:
            cur.execute(
                "UPDATE users SET password_hash = %s WHERE email = %s",
                (password_hash, email_norm),
            )
        else:
            cur.execute(
                "UPDATE users SET password_hash = ? WHERE lower(email) = ?",
                (password_hash, email_norm),
            )
        conn.commit()
        return cur.rowcount > 0
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()


def update_user_password_by_id(user_id: int, password: str) -> bool:
    if not isinstance(user_id, int) or user_id <= 0 or not password:
        return False
    password_hash = generate_password_hash(password)
    conn = get_conn()
    cur = conn.cursor()
    try:
        if USE_POSTGRES:
            cur.execute("UPDATE users SET password_hash = %s WHERE id = %s", (password_hash, user_id))
        else:
            cur.execute("UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id))
        conn.commit()
        return cur.rowcount > 0
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()


def store_user_password_change_challenge(user_id: int, otp_code: str, expires_at) -> bool:
    if not isinstance(user_id, int) or user_id <= 0 or not (otp_code or "").strip():
        return False
    code = (otp_code or "").strip()
    conn = get_conn()
    cur = conn.cursor()
    try:
        if USE_POSTGRES:
            cur.execute(
                """
                INSERT INTO user_password_change_challenges (user_id, otp_code, expires_at, created_at)
                VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (user_id) DO UPDATE SET
                    otp_code = EXCLUDED.otp_code,
                    expires_at = EXCLUDED.expires_at,
                    created_at = CURRENT_TIMESTAMP
                """,
                (user_id, code, expires_at),
            )
        else:
            cur.execute(
                """
                INSERT INTO user_password_change_challenges (user_id, otp_code, expires_at, created_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    otp_code = excluded.otp_code,
                    expires_at = excluded.expires_at,
                    created_at = CURRENT_TIMESTAMP
                """,
                (user_id, code, str(expires_at)),
            )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()


def get_user_password_change_challenge(user_id: int):
    if not isinstance(user_id, int) or user_id <= 0:
        return None
    conn = get_conn()
    cur = conn.cursor()
    try:
        if USE_POSTGRES:
            cur.execute(
                "SELECT user_id, otp_code, expires_at, created_at FROM user_password_change_challenges WHERE user_id = %s",
                (user_id,),
            )
        else:
            cur.execute(
                "SELECT user_id, otp_code, expires_at, created_at FROM user_password_change_challenges WHERE user_id = ?",
                (user_id,),
            )
        return row_to_dict(cur.fetchone())
    finally:
        conn.close()


def delete_user_password_change_challenge(user_id: int) -> bool:
    if not isinstance(user_id, int) or user_id <= 0:
        return False
    conn = get_conn()
    cur = conn.cursor()
    try:
        if USE_POSTGRES:
            cur.execute("DELETE FROM user_password_change_challenges WHERE user_id = %s", (user_id,))
        else:
            cur.execute("DELETE FROM user_password_change_challenges WHERE user_id = ?", (user_id,))
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()


def store_user_profile_email_change_challenge(user_id: int, otp_code: str, expires_at, pending_payload: str) -> bool:
    if not isinstance(user_id, int) or user_id <= 0 or not (otp_code or "").strip():
        return False
    code = (otp_code or "").strip()
    payload = (pending_payload or "").strip()
    if not payload:
        return False
    conn = get_conn()
    cur = conn.cursor()
    try:
        if USE_POSTGRES:
            cur.execute(
                """
                INSERT INTO user_profile_email_change_challenges (user_id, otp_code, expires_at, pending_payload, created_at)
                VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (user_id) DO UPDATE SET
                    otp_code = EXCLUDED.otp_code,
                    expires_at = EXCLUDED.expires_at,
                    pending_payload = EXCLUDED.pending_payload,
                    created_at = CURRENT_TIMESTAMP
                """,
                (user_id, code, expires_at, payload),
            )
        else:
            cur.execute(
                """
                INSERT INTO user_profile_email_change_challenges (user_id, otp_code, expires_at, pending_payload, created_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    otp_code = excluded.otp_code,
                    expires_at = excluded.expires_at,
                    pending_payload = excluded.pending_payload,
                    created_at = CURRENT_TIMESTAMP
                """,
                (user_id, code, str(expires_at), payload),
            )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()


def get_user_profile_email_change_challenge(user_id: int):
    if not isinstance(user_id, int) or user_id <= 0:
        return None
    conn = get_conn()
    cur = conn.cursor()
    try:
        if USE_POSTGRES:
            cur.execute(
                """
                SELECT user_id, otp_code, expires_at, pending_payload, created_at
                FROM user_profile_email_change_challenges
                WHERE user_id = %s
                """,
                (user_id,),
            )
        else:
            cur.execute(
                """
                SELECT user_id, otp_code, expires_at, pending_payload, created_at
                FROM user_profile_email_change_challenges
                WHERE user_id = ?
                """,
                (user_id,),
            )
        return row_to_dict(cur.fetchone())
    finally:
        conn.close()


def delete_user_profile_email_change_challenge(user_id: int) -> bool:
    if not isinstance(user_id, int) or user_id <= 0:
        return False
    conn = get_conn()
    cur = conn.cursor()
    try:
        if USE_POSTGRES:
            cur.execute("DELETE FROM user_profile_email_change_challenges WHERE user_id = %s", (user_id,))
        else:
            cur.execute("DELETE FROM user_profile_email_change_challenges WHERE user_id = ?", (user_id,))
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()


def create_journal_entry(
    *,
    user_id: int,
    text_content: str,
    tags_json: str,
    sentiment_label: str,
    sentiment_score: float,
    emotion_label: str,
    emotion_score: float,
    all_probs_json: str | None = None,
    title: str | None = None,
    image_urls_json: str | None = None,
    entry_datetime_utc: str | None = None,
):
    probs = all_probs_json if all_probs_json is not None else "{}"
    title_clean = str(title or "").strip()[:180] or None
    images_clean = image_urls_json if image_urls_json is not None else "[]"
    entry_dt_clean = str(entry_datetime_utc or "").strip()[:40] or None
    conn = get_conn()
    cur = conn.cursor()
    try:
        if USE_POSTGRES:
            cur.execute(
                """
                INSERT INTO journal_entries
                (user_id, title, entry_datetime_utc, text_content, tags_json, sentiment_label, sentiment_score, emotion_label, emotion_score, all_probs_json, image_urls_json)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, user_id, title, entry_datetime_utc, text_content, tags_json, sentiment_label, sentiment_score, emotion_label, emotion_score, all_probs_json, image_urls_json, created_at, updated_at
                """,
                (user_id, title_clean, entry_dt_clean, text_content, tags_json, sentiment_label, sentiment_score, emotion_label, emotion_score, probs, images_clean),
            )
            row = cur.fetchone()
            conn.commit()
            return row_to_dict(row)

        cur.execute(
            """
            INSERT INTO journal_entries
            (user_id, title, entry_datetime_utc, text_content, tags_json, sentiment_label, sentiment_score, emotion_label, emotion_score, all_probs_json, image_urls_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, title_clean, entry_dt_clean, text_content, tags_json, sentiment_label, sentiment_score, emotion_label, emotion_score, probs, images_clean),
        )
        entry_id = cur.lastrowid
        conn.commit()
        cur.execute(
            """
            SELECT id, user_id, title, entry_datetime_utc, text_content, tags_json, sentiment_label, sentiment_score, emotion_label, emotion_score, all_probs_json, image_urls_json, created_at, updated_at
            FROM journal_entries
            WHERE id = ?
            """,
            (entry_id,),
        )
        return row_to_dict(cur.fetchone())
    finally:
        conn.close()


def _load_ui_preferences_blob(user_id: int) -> dict:
    row = get_user_by_id(user_id)
    if not row:
        return {}
    raw = row.get("ui_preferences_json")
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
    return {}


def merge_user_ui_preferences_json(user_id: int, patch: dict) -> bool:
    """Deep-merge patch into users.ui_preferences_json (push prefs, pushState, theme, etc.)."""
    if not isinstance(user_id, int) or user_id <= 0 or not isinstance(patch, dict):
        return False
    cur_blob = _load_ui_preferences_blob(user_id)
    for key, val in patch.items():
        if isinstance(val, dict) and isinstance(cur_blob.get(key), dict):
            merged = dict(cur_blob[key])
            merged.update(val)
            cur_blob[key] = merged
        else:
            cur_blob[key] = val
    blob = json.dumps(cur_blob, separators=(",", ":"))
    conn = get_conn()
    cur_sql = conn.cursor()
    try:
        if USE_POSTGRES:
            cur_sql.execute(
                "UPDATE users SET ui_preferences_json = %s WHERE id = %s",
                (blob, user_id),
            )
        else:
            cur_sql.execute(
                "UPDATE users SET ui_preferences_json = ? WHERE id = ?",
                (blob, user_id),
            )
        conn.commit()
        return cur_sql.rowcount > 0
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()


def upsert_push_subscription(
    user_id: int, subscription: dict, vapid_public_key: str | None = None
) -> bool:
    if not isinstance(user_id, int) or user_id <= 0 or not isinstance(subscription, dict):
        return False
    endpoint = str(subscription.get("endpoint") or "").strip()
    if not endpoint:
        return False
    sub = dict(subscription)
    sub.pop("_fcmFailCount", None)
    vp = str(vapid_public_key or "").strip()
    if vp:
        sub["_vapidPublicKey"] = vp
    blob = json.dumps(sub, separators=(",", ":"))
    conn = get_conn()
    cur = conn.cursor()
    try:
        if USE_POSTGRES:
            cur.execute(
                """
                INSERT INTO push_subscriptions (user_id, endpoint, subscription_json, updated_at)
                VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (endpoint) DO UPDATE SET
                    user_id = EXCLUDED.user_id,
                    subscription_json = EXCLUDED.subscription_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (user_id, endpoint, blob),
            )
        else:
            cur.execute(
                """
                INSERT INTO push_subscriptions (user_id, endpoint, subscription_json, updated_at)
                VALUES (?, ?, ?, datetime('now'))
                ON CONFLICT(endpoint) DO UPDATE SET
                    user_id = excluded.user_id,
                    subscription_json = excluded.subscription_json,
                    updated_at = datetime('now')
                """,
                (user_id, endpoint, blob),
            )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()


def increment_push_subscription_fcm_failures(endpoint: str) -> int:
    """Bump FCM failure counter stored in subscription_json; returns new count."""
    endpoint = str(endpoint or "").strip()
    if not endpoint:
        return 0
    conn = get_conn()
    cur = conn.cursor()
    try:
        if USE_POSTGRES:
            cur.execute(
                "SELECT subscription_json FROM push_subscriptions WHERE endpoint = %s",
                (endpoint,),
            )
        else:
            cur.execute(
                "SELECT subscription_json FROM push_subscriptions WHERE endpoint = ?",
                (endpoint,),
            )
        row = cur.fetchone()
        if not row:
            return 0
        d = row_to_dict(row)
        try:
            sub = json.loads(d.get("subscription_json") or "{}")
        except Exception:
            sub = {}
        if not isinstance(sub, dict):
            sub = {}
        count = int(sub.get("_fcmFailCount") or 0) + 1
        sub["_fcmFailCount"] = count
        blob = json.dumps(sub, separators=(",", ":"))
        if USE_POSTGRES:
            cur.execute(
                """
                UPDATE push_subscriptions
                SET subscription_json = %s, updated_at = CURRENT_TIMESTAMP
                WHERE endpoint = %s
                """,
                (blob, endpoint),
            )
        else:
            cur.execute(
                """
                UPDATE push_subscriptions
                SET subscription_json = ?, updated_at = datetime('now')
                WHERE endpoint = ?
                """,
                (blob, endpoint),
            )
        conn.commit()
        return count
    except Exception:
        conn.rollback()
        return 0
    finally:
        conn.close()


def delete_push_subscription(user_id: int, endpoint: str) -> bool:
    if not isinstance(user_id, int) or user_id <= 0:
        return False
    endpoint = str(endpoint or "").strip()
    if not endpoint:
        return False
    conn = get_conn()
    cur = conn.cursor()
    try:
        if USE_POSTGRES:
            cur.execute(
                "DELETE FROM push_subscriptions WHERE user_id = %s AND endpoint = %s",
                (user_id, endpoint),
            )
        else:
            cur.execute(
                "DELETE FROM push_subscriptions WHERE user_id = ? AND endpoint = ?",
                (user_id, endpoint),
            )
        conn.commit()
        return cur.rowcount > 0
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()


def delete_push_subscription_by_endpoint(endpoint: str) -> bool:
    endpoint = str(endpoint or "").strip()
    if not endpoint:
        return False
    conn = get_conn()
    cur = conn.cursor()
    try:
        if USE_POSTGRES:
            cur.execute("DELETE FROM push_subscriptions WHERE endpoint = %s", (endpoint,))
        else:
            cur.execute("DELETE FROM push_subscriptions WHERE endpoint = ?", (endpoint,))
        conn.commit()
        return cur.rowcount > 0
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()


def list_push_subscriptions_for_user(user_id: int) -> list[dict]:
    """Subscriptions for one user, newest updated_at first."""
    if not isinstance(user_id, int) or user_id <= 0:
        return []
    conn = get_conn()
    cur = conn.cursor()
    try:
        if USE_POSTGRES:
            cur.execute(
                """
                SELECT subscription_json, endpoint, updated_at
                FROM push_subscriptions
                WHERE user_id = %s
                ORDER BY updated_at DESC, id DESC
                """,
                (user_id,),
            )
        else:
            cur.execute(
                """
                SELECT subscription_json, endpoint, updated_at
                FROM push_subscriptions
                WHERE user_id = ?
                ORDER BY datetime(updated_at) DESC, id DESC
                """,
                (user_id,),
            )
        out = []
        for row in cur.fetchall():
            d = row_to_dict(row)
            try:
                sub = json.loads(d.get("subscription_json") or "{}")
            except Exception:
                continue
            if isinstance(sub, dict) and sub.get("endpoint"):
                sub["_endpoint"] = d.get("endpoint")
                sub["_updatedAt"] = d.get("updated_at")
                out.append(sub)
        return out
    finally:
        conn.close()


def delete_push_subscriptions_for_user_except(user_id: int, keep_endpoint: str) -> int:
    """Remove every push row for this user except the current device endpoint."""
    if not isinstance(user_id, int) or user_id <= 0:
        return 0
    keep = str(keep_endpoint or "").strip()
    if not keep:
        return 0
    subs = list_push_subscriptions_for_user(user_id)
    removed = 0
    for sub in subs:
        ep = str(sub.get("endpoint") or sub.get("_endpoint") or "").strip()
        if not ep or ep == keep:
            continue
        if delete_push_subscription(user_id, ep):
            removed += 1
    return removed


def prune_push_subscriptions_for_user(
    user_id: int, *, keep_endpoint: str | None = None, max_keep: int = 2
) -> int:
    """Delete old device registrations; always keep keep_endpoint if set."""
    if not isinstance(user_id, int) or user_id <= 0:
        return 0
    keep = str(keep_endpoint or "").strip()
    if keep:
        return delete_push_subscriptions_for_user_except(user_id, keep)
    max_keep = max(1, int(max_keep))
    subs = list_push_subscriptions_for_user(user_id)
    if len(subs) <= max_keep:
        return 0
    keep_eps = [
        str(sub.get("endpoint") or sub.get("_endpoint") or "").strip()
        for sub in subs[:max_keep]
        if sub.get("endpoint") or sub.get("_endpoint")
    ]
    conn = get_conn()
    cur = conn.cursor()
    removed = 0
    try:
        for sub in subs:
            ep = str(sub.get("endpoint") or sub.get("_endpoint") or "").strip()
            if not ep or ep in keep_eps:
                continue
            if USE_POSTGRES:
                cur.execute(
                    "DELETE FROM push_subscriptions WHERE user_id = %s AND endpoint = %s",
                    (user_id, ep),
                )
            else:
                cur.execute(
                    "DELETE FROM push_subscriptions WHERE user_id = ? AND endpoint = ?",
                    (user_id, ep),
                )
            removed += cur.rowcount
        conn.commit()
        return removed
    except Exception:
        conn.rollback()
        return removed
    finally:
        conn.close()


def list_user_ids_with_daily_reminders_enabled() -> list[int]:
    """User ids with notifications.dailyEnabled in ui_preferences_json (for cron diagnostics)."""
    conn = get_conn()
    cur = conn.cursor()
    out: list[int] = []
    try:
        cur.execute("SELECT id, ui_preferences_json FROM users")
        for row in cur.fetchall():
            d = row_to_dict(row)
            uid = int(d.get("id") or 0)
            if uid <= 0:
                continue
            raw = d.get("ui_preferences_json")
            if not isinstance(raw, str) or not raw.strip():
                out.append(uid)
                continue
            try:
                blob = json.loads(raw)
                n = blob.get("notifications") if isinstance(blob, dict) else {}
                if not isinstance(n, dict) or n.get("dailyEnabled", True) is not False:
                    out.append(uid)
            except Exception:
                out.append(uid)
        return out
    finally:
        conn.close()


def list_push_subscriptions_grouped_by_user():
    """Return {user_id: [subscription_dict, ...]} newest device first."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        if USE_POSTGRES:
            cur.execute(
                """
                SELECT user_id, subscription_json, endpoint, updated_at
                FROM push_subscriptions
                ORDER BY user_id, updated_at DESC, id DESC
                """
            )
        else:
            cur.execute(
                """
                SELECT user_id, subscription_json, endpoint, updated_at
                FROM push_subscriptions
                ORDER BY user_id, datetime(updated_at) DESC, id DESC
                """
            )
        grouped: dict[int, list] = {}
        for row in cur.fetchall():
            d = row_to_dict(row)
            uid = int(d.get("user_id") or 0)
            if uid <= 0:
                continue
            try:
                sub = json.loads(d.get("subscription_json") or "{}")
            except Exception:
                continue
            if isinstance(sub, dict) and sub.get("endpoint"):
                sub["_endpoint"] = d.get("endpoint")
                sub["_updatedAt"] = d.get("updated_at")
                grouped.setdefault(uid, []).append(sub)
        return grouped
    finally:
        conn.close()


def get_journal_entries_by_user(user_id: int):
    conn = get_conn()
    cur = conn.cursor()
    try:
        if USE_POSTGRES:
            cur.execute(
                """
                SELECT id, user_id, text_content, tags_json, sentiment_label, sentiment_score, emotion_label, emotion_score, all_probs_json, created_at
                , title, image_urls_json, entry_datetime_utc, updated_at
                FROM journal_entries
                WHERE user_id = %s
                ORDER BY created_at DESC
                """,
                (user_id,),
            )
        else:
            cur.execute(
                """
                SELECT id, user_id, text_content, tags_json, sentiment_label, sentiment_score, emotion_label, emotion_score, all_probs_json, created_at
                , title, image_urls_json, entry_datetime_utc, updated_at
                FROM journal_entries
                WHERE user_id = ?
                ORDER BY datetime(created_at) DESC
                """,
                (user_id,),
            )
        return [row_to_dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_journal_entry_sync_stamps(user_id: int):
    """Entry id + timestamps only (sync revision / SSE; no text or images)."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        if USE_POSTGRES:
            cur.execute(
                """
                SELECT id, updated_at, created_at
                FROM journal_entries
                WHERE user_id = %s
                ORDER BY id ASC
                """,
                (user_id,),
            )
        else:
            cur.execute(
                """
                SELECT id, updated_at, created_at
                FROM journal_entries
                WHERE user_id = ?
                ORDER BY id ASC
                """,
                (user_id,),
            )
        return [row_to_dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_journal_entry_by_id(entry_id: int, user_id: int):
    conn = get_conn()
    cur = conn.cursor()
    try:
        if USE_POSTGRES:
            cur.execute(
                """
                SELECT id, user_id, text_content, tags_json, sentiment_label, sentiment_score, emotion_label, emotion_score, all_probs_json, created_at
                , title, image_urls_json, entry_datetime_utc, updated_at
                FROM journal_entries
                WHERE id = %s AND user_id = %s
                LIMIT 1
                """,
                (entry_id, user_id),
            )
        else:
            cur.execute(
                """
                SELECT id, user_id, text_content, tags_json, sentiment_label, sentiment_score, emotion_label, emotion_score, all_probs_json, created_at
                , title, image_urls_json, entry_datetime_utc, updated_at
                FROM journal_entries
                WHERE id = ? AND user_id = ?
                LIMIT 1
                """,
                (entry_id, user_id),
            )
        row = cur.fetchone()
        return row_to_dict(row) if row else None
    finally:
        conn.close()


def update_journal_entry(
    entry_id: int,
    user_id: int,
    *,
    title: str | None,
    text_content: str,
    tags_json: str,
    sentiment_label: str,
    sentiment_score: float,
    emotion_label: str,
    emotion_score: float,
    all_probs_json: str | None = None,
    image_urls_json: str | None = None,
):
    """Update entry fields; never modifies created_at. Sets updated_at to now."""
    probs = all_probs_json if all_probs_json is not None else "{}"
    title_clean = str(title or "").strip()[:180] or None
    conn = get_conn()
    cur = conn.cursor()
    try:
        images_sql = image_urls_json
        if images_sql is None:
            if USE_POSTGRES:
                cur.execute(
                    "SELECT image_urls_json FROM journal_entries WHERE id = %s AND user_id = %s",
                    (entry_id, user_id),
                )
                r = cur.fetchone()
                images_sql = (r.get("image_urls_json") if r else None) or "[]"
            else:
                cur.execute(
                    "SELECT image_urls_json FROM journal_entries WHERE id = ? AND user_id = ?",
                    (entry_id, user_id),
                )
                r = cur.fetchone()
                images_sql = (r["image_urls_json"] if r else None) or "[]"
        if images_sql is None:
            images_sql = "[]"

        if USE_POSTGRES:
            cur.execute(
                """
                UPDATE journal_entries
                SET title = %s,
                    text_content = %s,
                    tags_json = %s,
                    sentiment_label = %s,
                    sentiment_score = %s,
                    emotion_label = %s,
                    emotion_score = %s,
                    all_probs_json = %s,
                    image_urls_json = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s AND user_id = %s
                RETURNING id, user_id, title, entry_datetime_utc, text_content, tags_json, sentiment_label, sentiment_score, emotion_label, emotion_score, all_probs_json, image_urls_json, created_at, updated_at
                """,
                (
                    title_clean,
                    text_content,
                    tags_json,
                    sentiment_label,
                    sentiment_score,
                    emotion_label,
                    emotion_score,
                    probs,
                    images_sql,
                    entry_id,
                    user_id,
                ),
            )
            row = cur.fetchone()
            conn.commit()
            return row_to_dict(row) if row else None

        cur.execute(
            """
            UPDATE journal_entries
            SET title = ?,
                text_content = ?,
                tags_json = ?,
                sentiment_label = ?,
                sentiment_score = ?,
                emotion_label = ?,
                emotion_score = ?,
                all_probs_json = ?,
                image_urls_json = ?,
                updated_at = datetime('now')
            WHERE id = ? AND user_id = ?
            """,
            (
                title_clean,
                text_content,
                tags_json,
                sentiment_label,
                sentiment_score,
                emotion_label,
                emotion_score,
                probs,
                images_sql,
                entry_id,
                user_id,
            ),
        )
        if cur.rowcount <= 0:
            conn.rollback()
            return None
        conn.commit()
        cur.execute(
            """
            SELECT id, user_id, title, entry_datetime_utc, text_content, tags_json, sentiment_label, sentiment_score, emotion_label, emotion_score, all_probs_json, image_urls_json, created_at, updated_at
            FROM journal_entries
            WHERE id = ? AND user_id = ?
            """,
            (entry_id, user_id),
        )
        return row_to_dict(cur.fetchone())
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def delete_journal_entry(entry_id: int, user_id: int) -> bool:
    """Delete a journal row if it belongs to the user. Returns True if a row was removed."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        if USE_POSTGRES:
            cur.execute(
                "DELETE FROM journal_entries WHERE id = %s AND user_id = %s RETURNING id",
                (entry_id, user_id),
            )
            deleted = cur.fetchone() is not None
        else:
            cur.execute("DELETE FROM journal_entries WHERE id = ? AND user_id = ?", (entry_id, user_id))
            deleted = cur.rowcount > 0
        conn.commit()
        return bool(deleted)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_tag_trigger_summary(user_id: int, min_entries_per_bucket: int = 3):
    """
    Build top tag triggers from saved entry tags (not NLP keywords).

    Buckets:
      - stress: anxious + sad + angry
      - happiness: happy
    """
    rows = get_journal_entries_by_user(user_id)
    min_entries = max(1, int(min_entries_per_bucket or 1))

    def _norm_tags(tags_raw):
        try:
            parsed = json.loads(tags_raw or "[]")
        except Exception:
            parsed = []
        if not isinstance(parsed, list):
            return []
        out = []
        seen = set()
        for t in parsed:
            s = str(t or "").strip().lower()
            if not s:
                continue
            if s in seen:
                continue
            seen.add(s)
            out.append(s)
        return out

    stress_emotions = {"anxious", "sad", "angry"}
    happy_emotions = {"happy"}
    stress_counts = {}
    happy_counts = {}
    stress_entries_with_tags = 0
    happy_entries_with_tags = 0

    for r in rows:
        emo = str(r.get("emotion_label") or "").strip().lower()
        tags = _norm_tags(r.get("tags_json"))
        if not tags:
            continue
        if emo in stress_emotions:
            stress_entries_with_tags += 1
            for tag in tags:
                stress_counts[tag] = stress_counts.get(tag, 0) + 1
        if emo in happy_emotions:
            happy_entries_with_tags += 1
            for tag in tags:
                happy_counts[tag] = happy_counts.get(tag, 0) + 1

    def _pick_top_with_ties(counter, max_items: int = 2):
        if not counter:
            return []
        ordered = sorted(counter.items(), key=lambda x: (-x[1], x[0]))
        top_count = ordered[0][1]
        ties = [tag for tag, cnt in ordered if cnt == top_count]
        return ties[: max(1, int(max_items or 1))]

    def _rank_all(counter):
        if not counter:
            return []
        return [tag for tag, _cnt in sorted(counter.items(), key=lambda x: (-x[1], x[0]))]

    top_stress = _pick_top_with_ties(stress_counts, 2) if stress_entries_with_tags >= min_entries else []
    top_happy = _pick_top_with_ties(happy_counts, 2) if happy_entries_with_tags >= min_entries else []
    return {
        "topStressTriggers": top_stress,
        "topHappinessTriggers": top_happy,
        "stressRanking": _rank_all(stress_counts) if stress_entries_with_tags >= min_entries else [],
        "happinessRanking": _rank_all(happy_counts) if happy_entries_with_tags >= min_entries else [],
        "stressCounts": stress_counts if stress_entries_with_tags >= min_entries else {},
        "happinessCounts": happy_counts if happy_entries_with_tags >= min_entries else {},
        "stressTaggedEntries": stress_entries_with_tags,
        "happinessTaggedEntries": happy_entries_with_tags,
        "minRequiredEntries": min_entries,
    }


# ============================================================================
# Admin Suite Database Helpers
# ============================================================================

def record_user_login(user_id: int):
    """Update last_login timestamp for user."""
    if not user_id or int(user_id) <= 0:
        return
    conn = get_conn()
    cur = conn.cursor()
    try:
        if USE_POSTGRES:
            cur.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = %s", (int(user_id),))
        else:
            cur.execute("UPDATE users SET last_login = datetime('now') WHERE id = ?", (int(user_id),))
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


def set_user_disabled_status(user_id: int, is_disabled: bool) -> bool:
    """Enable or disable user account from admin panel."""
    if not user_id or int(user_id) <= 0:
        return False
    conn = get_conn()
    cur = conn.cursor()
    try:
        val = bool(is_disabled)
        if USE_POSTGRES:
            cur.execute("UPDATE users SET is_disabled = %s WHERE id = %s", (val, int(user_id)))
        else:
            cur.execute("UPDATE users SET is_disabled = ? WHERE id = ?", (1 if val else 0, int(user_id)))
        conn.commit()
        return True
    finally:
        conn.close()


def delete_user_account_admin(user_id: int) -> bool:
    """Permanently delete user account and associated journal records."""
    if not user_id or int(user_id) <= 0:
        return False
    conn = get_conn()
    cur = conn.cursor()
    try:
        uid = int(user_id)
        if USE_POSTGRES:
            cur.execute("DELETE FROM journal_entries WHERE user_id = %s", (uid,))
            cur.execute("DELETE FROM user_tags WHERE user_id = %s", (uid,))
            cur.execute("DELETE FROM push_subscriptions WHERE user_id = %s", (uid,))
            cur.execute("DELETE FROM users WHERE id = %s", (uid,))
        else:
            cur.execute("DELETE FROM journal_entries WHERE user_id = ?", (uid,))
            cur.execute("DELETE FROM user_tags WHERE user_id = ?", (uid,))
            cur.execute("DELETE FROM push_subscriptions WHERE user_id = ?", (uid,))
            cur.execute("DELETE FROM users WHERE id = ?", (uid,))
        conn.commit()
        return True
    finally:
        conn.close()


def log_admin_action(admin_email: str, action: str, details: dict = None, ip_address: str = None):
    """Record administrative audit log."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        d_json = json.dumps(details or {})
        email_clean = str(admin_email or "admin")[:255]
        action_clean = str(action or "ACTION")[:64]
        ip_clean = str(ip_address or "")[:64]
        if USE_POSTGRES:
            cur.execute(
                """
                INSERT INTO admin_audit_logs (admin_email, action, details_json, ip_address, created_at)
                VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                """,
                (email_clean, action_clean, d_json, ip_clean),
            )
        else:
            cur.execute(
                """
                INSERT INTO admin_audit_logs (admin_email, action, details_json, ip_address, created_at)
                VALUES (?, ?, ?, ?, datetime('now'))
                """,
                (email_clean, action_clean, d_json, ip_clean),
            )
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


def get_admin_audit_logs(page: int = 1, per_page: int = 12, limit: int = None):
    """Retrieve paginated administrative audit logs."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM admin_audit_logs")
        total = _fetchcount(cur)

        if limit is not None:
            lim = max(1, min(int(limit), 200))
            offset = 0
            cur_page = 1
            total_pages = 1
        else:
            per_page = max(1, min(int(per_page or 12), 100))
            total_pages = max(1, (total + per_page - 1) // per_page) if total > 0 else 1
            cur_page = max(1, min(int(page or 1), total_pages))
            offset = (cur_page - 1) * per_page
            lim = per_page

        if USE_POSTGRES:
            cur.execute(
                """
                SELECT id, admin_email, action, details_json, ip_address, created_at
                FROM admin_audit_logs
                ORDER BY created_at DESC, id DESC
                LIMIT %s OFFSET %s
                """,
                (lim, offset),
            )
        else:
            cur.execute(
                """
                SELECT id, admin_email, action, details_json, ip_address, created_at
                FROM admin_audit_logs
                ORDER BY datetime(created_at) DESC, id DESC
                LIMIT ? OFFSET ?
                """,
                (lim, offset),
            )
        rows = [row_to_dict(r) for r in cur.fetchall()]
        out = []
        for r in rows:
            details = {}
            if r.get("details_json"):
                try:
                    details = json.loads(r["details_json"])
                except Exception:
                    details = {}
            out.append({
                "id": r["id"],
                "adminEmail": r["admin_email"],
                "action": r["action"],
                "details": details,
                "ipAddress": r.get("ip_address") or "—",
                "createdAt": str(r["created_at"] or ""),
            })
        return {
            "records": out,
            "total": total,
            "page": cur_page,
            "perPage": lim,
            "totalPages": total_pages,
        }
    finally:
        conn.close()


def get_admin_dashboard_stats():
    """Retrieve key metrics, 30-day timeline, and emotion breakdown for admin dashboard."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        # Total users
        cur.execute("SELECT COUNT(*) FROM users")
        total_users = _fetchcount(cur)

        # Active users in last 30 days - handle NULL last_login gracefully
        try:
            if USE_POSTGRES:
                cur.execute(
                    """
                    SELECT COUNT(DISTINCT id) FROM users
                    WHERE (last_login IS NOT NULL AND last_login >= NOW() - INTERVAL '30 days')
                       OR id IN (SELECT DISTINCT user_id FROM journal_entries WHERE created_at >= NOW() - INTERVAL '30 days')
                    """
                )
            else:
                cur.execute(
                    """
                    SELECT COUNT(DISTINCT id) FROM users
                    WHERE (last_login IS NOT NULL AND last_login >= datetime('now', '-30 days'))
                       OR id IN (SELECT DISTINCT user_id FROM journal_entries WHERE created_at >= datetime('now', '-30 days'))
                    """
                )
            active_users = _fetchcount(cur)
        except Exception:
            active_users = total_users

        # Total entries
        cur.execute("SELECT COUNT(*) FROM journal_entries")
        total_entries = _fetchcount(cur)

        # Total AI analyses
        cur.execute("SELECT COUNT(*) FROM journal_entries WHERE emotion_label IS NOT NULL AND emotion_label != ''")
        total_ai_analyses = _fetchcount(cur)

        # Emotion distribution
        cur.execute(
            """
            SELECT LOWER(TRIM(emotion_label)) as emo, COUNT(*) as cnt
            FROM journal_entries
            WHERE emotion_label IS NOT NULL AND emotion_label != ''
            GROUP BY LOWER(TRIM(emotion_label))
            """
        )
        emo_rows = cur.fetchall()
        emo_counts = {"happy": 0, "sad": 0, "anxious": 0, "angry": 0, "neutral": 0}
        for r in emo_rows:
            r = row_to_dict(r)
            k = str(r.get("emo") or "").lower()
            cnt = int(r.get("cnt") or 0)
            if k in emo_counts:
                emo_counts[k] += cnt
            elif "anx" in k or "fear" in k:
                emo_counts["anxious"] += cnt
            elif "joy" in k or "hap" in k or "love" in k:
                emo_counts["happy"] += cnt
            elif "sad" in k:
                emo_counts["sad"] += cnt
            elif "ang" in k:
                emo_counts["angry"] += cnt
            else:
                emo_counts["neutral"] += cnt

        # 30-day activity timeline
        timeline = []
        today = datetime.now(timezone.utc).date()
        for i in range(29, -1, -1):
            d = today - timedelta(days=i)
            d_str = d.strftime("%Y-%m-%d")
            timeline.append({"date": d_str, "entries": 0, "signups": 0})
        date_map = {item["date"]: item for item in timeline}

        if USE_POSTGRES:
            cur.execute(
                """
                SELECT TO_CHAR(created_at, 'YYYY-MM-DD') as day, COUNT(*)
                FROM journal_entries
                WHERE created_at >= NOW() - INTERVAL '30 days'
                GROUP BY day
                """
            )
        else:
            cur.execute(
                """
                SELECT SUBSTR(created_at, 1, 10) as day, COUNT(*)
                FROM journal_entries
                WHERE created_at >= datetime('now', '-30 days')
                GROUP BY day
                """
            )
        for r in cur.fetchall():
            rd = row_to_dict(r)
            day_key = str(rd.get("day") or "")
            if day_key in date_map:
                date_map[day_key]["entries"] = int(rd.get("count") or list(rd.values())[-1] or 0)

        if USE_POSTGRES:
            cur.execute(
                """
                SELECT TO_CHAR(created_at, 'YYYY-MM-DD') as day, COUNT(*)
                FROM users
                WHERE created_at >= NOW() - INTERVAL '30 days'
                GROUP BY day
                """
            )
        else:
            cur.execute(
                """
                SELECT SUBSTR(created_at, 1, 10) as day, COUNT(*)
                FROM users
                WHERE created_at >= datetime('now', '-30 days')
                GROUP BY day
                """
            )
        for r in cur.fetchall():
            rd = row_to_dict(r)
            day_key = str(rd.get("day") or "")
            if day_key in date_map:
                date_map[day_key]["signups"] = int(rd.get("count") or list(rd.values())[-1] or 0)

        # Recent activities (privacy-safe: user nickname, emotion, sentiment, date, words)
        if USE_POSTGRES:
            cur.execute(
                """
                SELECT j.id, j.user_id, u.nickname, u.email, j.emotion_label, j.sentiment_label,
                       j.created_at, LENGTH(j.text_content) - LENGTH(REPLACE(j.text_content, ' ', '')) + 1 as word_est
                FROM journal_entries j
                JOIN users u ON u.id = j.user_id
                ORDER BY j.created_at DESC
                LIMIT 6
                """
            )
        else:
            cur.execute(
                """
                SELECT j.id, j.user_id, u.nickname, u.email, j.emotion_label, j.sentiment_label,
                       j.created_at, LENGTH(j.text_content) - LENGTH(REPLACE(j.text_content, ' ', '')) + 1 as word_est
                FROM journal_entries j
                JOIN users u ON u.id = j.user_id
                ORDER BY datetime(j.created_at) DESC
                LIMIT 6
                """
            )
        recent = []
        for r in cur.fetchall():
            rd = row_to_dict(r)
            email = str(rd.get("email") or "")
            recent.append({
                "entryId": rd.get("id"),
                "userId": rd.get("user_id"),
                "nickname": rd.get("nickname"),
                "maskedEmail": f"{email[:2]}***@{email.split('@')[-1]}" if "@" in email else "***",
                "emotion": str(rd.get("emotion_label") or "neutral").lower(),
                "sentiment": str(rd.get("sentiment_label") or "neutral").lower(),
                "createdAt": str(rd.get("created_at") or ""),
                "words": max(1, int(rd.get("word_est") or 1)),
            })

        return {
            "totalUsers": total_users,
            "activeUsers": active_users,
            "totalEntries": total_entries,
            "totalAiAnalyses": total_ai_analyses,
            "emotionDistribution": emo_counts,
            "activityTimeline": timeline,
            "recentActivity": recent,
        }
    finally:
        conn.close()


def list_admin_users(search: str = "", status_filter: str = "", page: int = 1, per_page: int = 20):
    """Retrieve paginated user list with entry counts, 2FA, and disabled status for admin management."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        search_clean = (search or "").strip().lower()
        search_term = f"%{search_clean}%"
        status_filter = (status_filter or "").strip().lower()
        page = max(1, int(page or 1))
        per_page = max(5, min(int(per_page or 20), 100))
        offset = (page - 1) * per_page

        where_clauses = []
        params = []
        if search_clean:
            if USE_POSTGRES:
                where_clauses.append("(LOWER(u.nickname) LIKE %s OR LOWER(u.email) LIKE %s OR LOWER(COALESCE(u.first_name,'')) LIKE %s OR LOWER(COALESCE(u.last_name,'')) LIKE %s)")
                params.extend([search_term, search_term, search_term, search_term])
            else:
                where_clauses.append("(LOWER(u.nickname) LIKE ? OR LOWER(u.email) LIKE ? OR LOWER(COALESCE(u.first_name,'')) LIKE ? OR LOWER(COALESCE(u.last_name,'')) LIKE ?)")
                params.extend([search_term, search_term, search_term, search_term])

        if status_filter == "active":
            if USE_POSTGRES:
                where_clauses.append("(u.is_disabled IS NULL OR u.is_disabled = FALSE)")
            else:
                where_clauses.append("(u.is_disabled IS NULL OR u.is_disabled = 0)")
        elif status_filter == "disabled":
            if USE_POSTGRES:
                where_clauses.append("u.is_disabled = TRUE")
            else:
                where_clauses.append("u.is_disabled = 1")
        elif status_filter == "2fa":
            if USE_POSTGRES:
                where_clauses.append("u.totp_enabled = TRUE")
            else:
                where_clauses.append("u.totp_enabled = 1")

        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        # Total counts
        cur.execute(f"SELECT COUNT(*) FROM users u {where_sql}", tuple(params))
        total_filtered = _fetchcount(cur)

        # Summary counts
        cur.execute("SELECT COUNT(*) FROM users")
        total_all = _fetchcount(cur)
        if USE_POSTGRES:
            cur.execute("SELECT COUNT(*) FROM users WHERE is_disabled = TRUE")
        else:
            cur.execute("SELECT COUNT(*) FROM users WHERE is_disabled = 1")
        total_disabled = _fetchcount(cur)
        if USE_POSTGRES:
            cur.execute("SELECT COUNT(*) FROM users WHERE totp_enabled = TRUE")
        else:
            cur.execute("SELECT COUNT(*) FROM users WHERE totp_enabled = 1")
        total_2fa = _fetchcount(cur)
        total_active = max(0, total_all - total_disabled)

        # Query page records
        query_sql = f"""
            SELECT u.id, u.nickname, u.email, u.first_name, u.last_name, u.gender, u.birthday,
                   u.created_at, u.last_login, u.is_disabled, u.totp_enabled, u.avatar_data_url,
                   (SELECT COUNT(*) FROM journal_entries j WHERE j.user_id = u.id) as entry_count
            FROM users u
            {where_sql}
            ORDER BY u.created_at DESC, u.id DESC
            LIMIT {'%s' if USE_POSTGRES else '?'} OFFSET {'%s' if USE_POSTGRES else '?'}
        """
        page_params = list(params) + [per_page, offset]
        cur.execute(query_sql, tuple(page_params))

        users = []
        for r in cur.fetchall():
            row_dict = row_to_dict(r)
            full_name = f"{row_dict.get('first_name') or ''} {row_dict.get('last_name') or ''}".strip()
            users.append({
                "id": row_dict["id"],
                "nickname": row_dict["nickname"],
                "email": row_dict["email"],
                "fullName": full_name or row_dict["nickname"],
                "gender": row_dict.get("gender") or "Not specified",
                "birthday": str(row_dict.get("birthday") or "—"),
                "createdAt": str(row_dict.get("created_at") or ""),
                "lastLogin": str(row_dict.get("last_login") or "Never"),
                "isDisabled": bool(row_dict.get("is_disabled") in (True, 1, "true", "1")),
                "totpEnabled": bool(row_dict.get("totp_enabled") in (True, 1, "true", "1")),
                "entryCount": int(row_dict.get("entry_count") or 0),
                "avatarDataUrl": row_dict.get("avatar_data_url") or None,
            })

        return {
            "records": users,
            "total": total_filtered,
            "page": page,
            "perPage": per_page,
            "totalPages": max(1, (total_filtered + per_page - 1) // per_page),
            "counts": {
                "total": total_all,
                "active": total_active,
                "disabled": total_disabled,
                "twoFactor": total_2fa,
            }
        }
    finally:
        conn.close()


def get_admin_user_details(user_id: int):
    """Retrieve privacy-safe user metadata and aggregated emotion statistics."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        user = get_user_by_id(user_id)
        if not user:
            return None

        uid = int(user_id)
        if USE_POSTGRES:
            cur.execute(
                """
                SELECT COUNT(*) as count,
                       MIN(created_at) as first_entry,
                       MAX(created_at) as last_entry,
                       COUNT(CASE WHEN LOWER(emotion_label) = 'happy' THEN 1 END) as happy_cnt,
                       COUNT(CASE WHEN LOWER(emotion_label) = 'sad' THEN 1 END) as sad_cnt,
                       COUNT(CASE WHEN LOWER(emotion_label) = 'anxious' THEN 1 END) as anxious_cnt,
                       COUNT(CASE WHEN LOWER(emotion_label) = 'angry' THEN 1 END) as angry_cnt,
                       COUNT(CASE WHEN LOWER(emotion_label) = 'neutral' THEN 1 END) as neutral_cnt
                FROM journal_entries
                WHERE user_id = %s
                """,
                (uid,),
            )
        else:
            cur.execute(
                """
                SELECT COUNT(*) as count,
                       MIN(created_at) as first_entry,
                       MAX(created_at) as last_entry,
                       COUNT(CASE WHEN LOWER(emotion_label) = 'happy' THEN 1 END) as happy_cnt,
                       COUNT(CASE WHEN LOWER(emotion_label) = 'sad' THEN 1 END) as sad_cnt,
                       COUNT(CASE WHEN LOWER(emotion_label) = 'anxious' THEN 1 END) as anxious_cnt,
                       COUNT(CASE WHEN LOWER(emotion_label) = 'angry' THEN 1 END) as angry_cnt,
                       COUNT(CASE WHEN LOWER(emotion_label) = 'neutral' THEN 1 END) as neutral_cnt
                FROM journal_entries
                WHERE user_id = ?
                """,
                (uid,),
            )
        st = cur.fetchone()
        rd = row_to_dict(st) or {}
        stats = {
            "totalEntries": int(rd.get("count") or 0),
            "firstEntryDate": str(rd.get("first_entry") or "—"),
            "lastEntryDate": str(rd.get("last_entry") or "—"),
            "emotions": {
                "happy": int(rd.get("happy_cnt") or 0),
                "sad": int(rd.get("sad_cnt") or 0),
                "anxious": int(rd.get("anxious_cnt") or 0),
                "angry": int(rd.get("angry_cnt") or 0),
                "neutral": int(rd.get("neutral_cnt") or 0),
            }
        }

        full_name = f"{user.get('first_name') or ''} {user.get('last_name') or ''}".strip()
        return {
            "id": user["id"],
            "nickname": user["nickname"],
            "email": user["email"],
            "fullName": full_name or user["nickname"],
            "firstName": user.get("first_name") or "",
            "lastName": user.get("last_name") or "",
            "gender": user.get("gender") or "Not specified",
            "birthday": str(user.get("birthday") or "—"),
            "createdAt": str(user.get("created_at") or ""),
            "lastLogin": str(user.get("last_login") or "Never"),
            "privacyAgreedAt": str(user.get("privacy_agreed_at") or user.get("created_at") or "—"),
            "isDisabled": bool(user.get("is_disabled") in (True, 1, "true", "1")),
            "totpEnabled": bool(user.get("totp_enabled") in (True, 1, "true", "1")),
            "avatarDataUrl": user.get("avatar_data_url") or None,
            "journalStats": stats,
        }
    finally:
        conn.close()


def get_admin_analytics_data(days: int = 30):
    """Retrieve detailed analytics timelines, emotion trends, and sentiment distribution."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        days = max(7, min(int(days or 30), 365)) if days != 0 else 365

        today = datetime.now(timezone.utc).date()
        buckets = []
        for i in range(days - 1, -1, -1):
            d = today - timedelta(days=i)
            d_str = d.strftime("%Y-%m-%d")
            buckets.append({
                "date": d_str,
                "total": 0,
                "happy": 0,
                "sad": 0,
                "anxious": 0,
                "angry": 0,
                "neutral": 0,
            })
        bucket_map = {b["date"]: b for b in buckets}

        if USE_POSTGRES:
            cur.execute(
                """
                SELECT TO_CHAR(created_at, 'YYYY-MM-DD') as day,
                       LOWER(TRIM(COALESCE(emotion_label, 'neutral'))) as emo,
                       COUNT(*) as cnt
                FROM journal_entries
                WHERE created_at >= NOW() - (%s || ' days')::INTERVAL
                GROUP BY day, emo
                """,
                (str(days),),
            )
        else:
            cur.execute(
                """
                SELECT SUBSTR(created_at, 1, 10) as day,
                       LOWER(TRIM(COALESCE(emotion_label, 'neutral'))) as emo,
                       COUNT(*) as cnt
                FROM journal_entries
                WHERE created_at >= datetime('now', '-' || ? || ' days')
                GROUP BY day, emo
                """,
                (str(days),),
            )

        for r in cur.fetchall():
            rd = row_to_dict(r)
            day_str = str(rd.get("day") or "")
            emo = str(rd.get("emo") or "neutral").lower()
            cnt = int(rd.get("cnt") or 0)
            if day_str in bucket_map:
                bucket_map[day_str]["total"] += cnt
                if emo in bucket_map[day_str]:
                    bucket_map[day_str][emo] += cnt
                elif "anx" in emo:
                    bucket_map[day_str]["anxious"] += cnt
                elif "hap" in emo or "joy" in emo:
                    bucket_map[day_str]["happy"] += cnt
                elif "sad" in emo:
                    bucket_map[day_str]["sad"] += cnt
                elif "ang" in emo:
                    bucket_map[day_str]["angry"] += cnt
                else:
                    bucket_map[day_str]["neutral"] += cnt

        # Sentiment labels - add aliases for consistent dict key access
        if USE_POSTGRES:
            cur.execute(
                """
                SELECT LOWER(TRIM(COALESCE(sentiment_label, 'neutral'))) as s, COUNT(*) as cnt
                FROM journal_entries
                WHERE created_at >= NOW() - (%s || ' days')::INTERVAL
                GROUP BY s
                """,
                (str(days),),
            )
        else:
            cur.execute(
                """
                SELECT LOWER(TRIM(COALESCE(sentiment_label, 'neutral'))) as s, COUNT(*) as cnt
                FROM journal_entries
                WHERE created_at >= datetime('now', '-' || ? || ' days')
                GROUP BY s
                """,
                (str(days),),
            )
        sentiments = {"positive": 0, "neutral": 0, "negative": 0}
        for r in cur.fetchall():
            rd = row_to_dict(r)
            s = str(rd.get("s") or "neutral").lower()
            cnt = int(rd.get("cnt") or 0)
            if s in sentiments:
                sentiments[s] += cnt
            elif "pos" in s:
                sentiments["positive"] += cnt
            elif "neg" in s:
                sentiments["negative"] += cnt
            else:
                sentiments["neutral"] += cnt

        # Day of week distribution (0=Sun, 1=Mon, ..., 6=Sat)
        if USE_POSTGRES:
            cur.execute(
                """
                SELECT EXTRACT(DOW FROM created_at)::INTEGER as dow, COUNT(*) as cnt
                FROM journal_entries
                WHERE created_at >= NOW() - (%s || ' days')::INTERVAL
                GROUP BY dow
                ORDER BY dow
                """,
                (str(days),),
            )
        else:
            cur.execute(
                """
                SELECT CAST(STRFTIME('%%w', created_at) AS INTEGER) as dow, COUNT(*) as cnt
                FROM journal_entries
                WHERE created_at >= datetime('now', '-' || ? || ' days')
                GROUP BY dow
                ORDER BY dow
                """,
                (str(days),),
            )
        dow_counts = [0] * 7
        for r in cur.fetchall():
            rd = row_to_dict(r)
            idx = int(rd.get("dow") or 0)
            if 0 <= idx <= 6:
                dow_counts[idx] = int(rd.get("cnt") or 0)

        return {
            "timeline": buckets,
            "sentiments": sentiments,
            "dayOfWeek": dow_counts,
            "totalEntriesInRange": sum(b["total"] for b in buckets),
            "rangeDays": days,
        }
    finally:
        conn.close()


def get_database_health_info():
    """Retrieve database engine health, latency, and row counts."""
    import time
    t0 = time.perf_counter()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT 1")
        cur.fetchone()
        latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        cur.execute("SELECT COUNT(*) FROM users")
        u_cnt = _fetchcount(cur)
        cur.execute("SELECT COUNT(*) FROM journal_entries")
        j_cnt = _fetchcount(cur)
        return {
            "engine": "PostgreSQL" if USE_POSTGRES else "SQLite",
            "connected": True,
            "latencyMs": latency_ms,
            "totalUsers": u_cnt,
            "totalEntries": j_cnt,
        }
    except Exception as e:
        return {
            "engine": "PostgreSQL" if USE_POSTGRES else "SQLite",
            "connected": False,
            "error": str(e),
        }
    finally:
        conn.close()
