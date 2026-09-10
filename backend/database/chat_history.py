import os
import psycopg2
from psycopg2 import pool
from datetime import datetime
import threading

_pool = None
_pool_lock = threading.Lock()


def _get_pool():
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _pool = pool.ThreadedConnectionPool(
                    minconn=2,
                    maxconn=10,
                    host=os.environ.get("POSTGRES_HOST", "localhost"),
                    database=os.environ.get("POSTGRES_DB", "rag_db"),
                    user=os.environ.get("POSTGRES_USER", "admin"),
                    password=os.environ.get("POSTGRES_PASSWORD", "password"),
                    port=int(os.environ.get("POSTGRES_PORT", 5432))
                )
    return _pool


def get_connection():
    return _get_pool().getconn()


def put_connection(conn):
    _get_pool().putconn(conn)


def init_chat_table():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                id SERIAL PRIMARY KEY,
                session_id VARCHAR(64) NOT NULL,
                role VARCHAR(16) NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_session ON chat_history(session_id);
        """)
        conn.commit()
        cur.close()
    finally:
        put_connection(conn)


def save_message(session_id: str, role: str, content: str):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO chat_history (session_id, role, content) VALUES (%s, %s, %s)",
            (session_id, role, content)
        )
        conn.commit()
        cur.close()
    finally:
        put_connection(conn)


def get_history(session_id: str, limit: int = 20):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT role, content, created_at FROM chat_history WHERE session_id = %s ORDER BY created_at DESC LIMIT %s",
            (session_id, limit)
        )
        rows = cur.fetchall()
        cur.close()
        return [{"role": r, "content": c, "created_at": t.isoformat()} for r, c, t in reversed(rows)]
    finally:
        put_connection(conn)


def list_sessions():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT session_id, MIN(created_at) as started, MAX(created_at) as last_message,
                   COUNT(*) as message_count
            FROM chat_history GROUP BY session_id ORDER BY last_message DESC
        """)
        rows = cur.fetchall()
        cur.close()
        return [
            {"session_id": s, "started": st.isoformat(), "last_message": lm.isoformat(), "message_count": mc}
            for s, st, lm, mc in rows
        ]
    finally:
        put_connection(conn)


def list_sessions_with_titles():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT s.session_id, s.started, s.last_message, s.message_count, first.title
            FROM (
                SELECT session_id, MIN(created_at) AS started, MAX(created_at) AS last_message,
                       COUNT(*) AS message_count
                FROM chat_history
                GROUP BY session_id
            ) s
            LEFT JOIN LATERAL (
                SELECT content AS title
                FROM chat_history
                WHERE session_id = s.session_id
                ORDER BY created_at ASC
                LIMIT 1
            ) first ON true
            ORDER BY s.last_message DESC
        """)
        rows = cur.fetchall()
        cur.close()
        return [
            {
                "session_id": sids,
                "started": st.isoformat(),
                "last_message": lm.isoformat(),
                "message_count": mc,
                "title": (title or "").strip()[:80],
            }
            for sids, st, lm, mc, title in rows
        ]
    finally:
        put_connection(conn)


def delete_chat_session(session_id: str):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM chat_history WHERE session_id = %s",
            (session_id,)
        )
        conn.commit()
        deleted = cur.rowcount
        cur.close()
        return {"deleted": session_id, "messages_removed": deleted}
    finally:
        put_connection(conn)


init_chat_table()