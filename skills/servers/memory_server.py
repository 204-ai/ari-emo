#!/usr/bin/env python3
"""
SQLite Memory Server for Ari.

Wraps the Hermes SessionDB pattern (SQLite + FTS5) as a lightweight HTTP API.
Provides persistent session storage with full-text search for chat history.

Usage:
    python memory_server.py [--port 8192] [--db ./data/ari_memory.db]
"""

import json
import os
import sqlite3
import time
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL DEFAULT 'chat',
    started_at REAL NOT NULL,
    ended_at REAL,
    message_count INTEGER DEFAULT 0,
    summary TEXT
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    role TEXT NOT NULL,
    content TEXT,
    timestamp REAL NOT NULL,
    token_estimate INTEGER
);

CREATE INDEX IF NOT EXISTS idx_sessions_started ON sessions(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, timestamp);
"""

FTS_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
    content,
    content=messages,
    content_rowid=id
);

CREATE TRIGGER IF NOT EXISTS messages_fts_insert AFTER INSERT ON messages BEGIN
    INSERT INTO messages_fts(rowid, content) VALUES (new.id, new.content);
END;

CREATE TRIGGER IF NOT EXISTS messages_fts_delete AFTER DELETE ON messages BEGIN
    INSERT INTO messages_fts(messages_fts, rowid, content) VALUES('delete', old.id, old.content);
END;

CREATE TRIGGER IF NOT EXISTS messages_fts_update AFTER UPDATE ON messages BEGIN
    INSERT INTO messages_fts(messages_fts, rowid, content) VALUES('delete', old.id, old.content);
    INSERT INTO messages_fts(rowid, content) VALUES (new.id, new.content);
END;
"""

SCHEMA_VERSION = 1


class SessionDB:
    """SQLite-backed session storage with FTS5 search."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,
            timeout=10.0,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    def _init_schema(self):
        cursor = self._conn.cursor()
        cursor.executescript(SCHEMA_SQL)

        cursor.execute("SELECT version FROM schema_version LIMIT 1")
        row = cursor.fetchone()
        if row is None:
            cursor.execute(
                "INSERT INTO schema_version (version) VALUES (?)",
                (SCHEMA_VERSION,),
            )

        # FTS5 setup
        try:
            cursor.execute("SELECT * FROM messages_fts LIMIT 0")
        except sqlite3.OperationalError:
            cursor.executescript(FTS_SQL)

        self._conn.commit()

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    # -- Sessions ----------------------------------------------------------

    def create_session(self, session_id: str = None) -> str:
        sid = session_id or str(uuid.uuid4())
        self._conn.execute(
            "INSERT INTO sessions (id, source, started_at) VALUES (?, 'chat', ?)",
            (sid, time.time()),
        )
        self._conn.commit()
        return sid

    def end_session(self, session_id: str, summary: str = None) -> None:
        self._conn.execute(
            "UPDATE sessions SET ended_at = ?, summary = ? WHERE id = ?",
            (time.time(), summary, session_id),
        )
        self._conn.commit()

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        cursor = self._conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def list_sessions(self, limit: int = 20, offset: int = 0) -> List[Dict]:
        cursor = self._conn.execute(
            "SELECT * FROM sessions ORDER BY started_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        return [dict(row) for row in cursor.fetchall()]

    # -- Messages ----------------------------------------------------------

    def append_message(
        self,
        session_id: str,
        role: str,
        content: str,
        token_estimate: int = None,
    ) -> int:
        cursor = self._conn.execute(
            """INSERT INTO messages (session_id, role, content, timestamp, token_estimate)
               VALUES (?, ?, ?, ?, ?)""",
            (session_id, role, content, time.time(), token_estimate),
        )
        msg_id = cursor.lastrowid
        self._conn.execute(
            "UPDATE sessions SET message_count = message_count + 1 WHERE id = ?",
            (session_id,),
        )
        self._conn.commit()
        return msg_id

    def get_messages(
        self, session_id: str, limit: int = 200, offset: int = 0
    ) -> List[Dict]:
        cursor = self._conn.execute(
            """SELECT * FROM messages WHERE session_id = ?
               ORDER BY timestamp, id LIMIT ? OFFSET ?""",
            (session_id, limit, offset),
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_recent_messages(self, limit: int = 50) -> List[Dict]:
        """Get most recent messages across all sessions."""
        cursor = self._conn.execute(
            """SELECT m.*, s.started_at as session_started
               FROM messages m JOIN sessions s ON s.id = m.session_id
               ORDER BY m.timestamp DESC LIMIT ?""",
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]

    # -- Search ------------------------------------------------------------

    def search(
        self,
        query: str,
        role_filter: List[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Dict]:
        """Full-text search across all messages using FTS5."""
        if not query or not query.strip():
            return []

        where_clauses = ["messages_fts MATCH ?"]
        params: list = [query]

        if role_filter:
            placeholders = ",".join("?" for _ in role_filter)
            where_clauses.append(f"m.role IN ({placeholders})")
            params.extend(role_filter)

        where_sql = " AND ".join(where_clauses)
        params.extend([limit, offset])

        sql = f"""
            SELECT
                m.id,
                m.session_id,
                m.role,
                snippet(messages_fts, 0, '>>>', '<<<', '...', 40) AS snippet,
                m.timestamp,
                s.started_at AS session_started
            FROM messages_fts
            JOIN messages m ON m.id = messages_fts.rowid
            JOIN sessions s ON s.id = m.session_id
            WHERE {where_sql}
            ORDER BY rank
            LIMIT ? OFFSET ?
        """

        cursor = self._conn.execute(sql, params)
        matches = []
        for row in cursor.fetchall():
            match = dict(row)
            # Add surrounding context
            try:
                ctx = self._conn.execute(
                    """SELECT role, content FROM messages
                       WHERE session_id = ? AND id >= ? - 1 AND id <= ? + 1
                       ORDER BY id""",
                    (match["session_id"], match["id"], match["id"]),
                )
                match["context"] = [
                    {"role": r["role"], "content": (r["content"] or "")[:200]}
                    for r in ctx.fetchall()
                ]
            except Exception:
                match["context"] = []
            matches.append(match)
        return matches

    # -- Stats -------------------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        sessions = self._conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        messages = self._conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        return {"sessions": sessions, "messages": messages, "db_path": str(self.db_path)}


# ---------------------------------------------------------------------------
# HTTP Server
# ---------------------------------------------------------------------------


class MemoryHandler(BaseHTTPRequestHandler):
    db: SessionDB = None

    def _json_response(self, data: Any, status: int = 200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> Dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length))

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0]
        params = {}
        if "?" in self.path:
            from urllib.parse import parse_qs
            params = {k: v[0] for k, v in parse_qs(self.path.split("?")[1]).items()}

        if path == "/stats":
            self._json_response(self.db.stats())

        elif path == "/sessions":
            limit = int(params.get("limit", 20))
            offset = int(params.get("offset", 0))
            self._json_response(self.db.list_sessions(limit, offset))

        elif path.startswith("/sessions/") and "/messages" in path:
            session_id = path.split("/")[2]
            limit = int(params.get("limit", 200))
            self._json_response(self.db.get_messages(session_id, limit))

        elif path.startswith("/sessions/"):
            session_id = path.split("/")[2]
            session = self.db.get_session(session_id)
            if session:
                self._json_response(session)
            else:
                self._json_response({"error": "not found"}, 404)

        elif path == "/search":
            query = params.get("q", "")
            limit = int(params.get("limit", 20))
            self._json_response(self.db.search(query, limit=limit))

        elif path == "/recent":
            limit = int(params.get("limit", 50))
            self._json_response(self.db.get_recent_messages(limit))

        else:
            self._json_response({"error": "not found"}, 404)

    def do_POST(self):
        path = self.path.split("?")[0]
        body = self._read_body()

        if path == "/sessions":
            sid = self.db.create_session(body.get("session_id"))
            self._json_response({"session_id": sid}, 201)

        elif path.startswith("/sessions/") and path.endswith("/end"):
            session_id = path.split("/")[2]
            self.db.end_session(session_id, body.get("summary"))
            self._json_response({"ok": True})

        elif path == "/messages":
            session_id = body.get("session_id")
            if not session_id:
                self._json_response({"error": "session_id required"}, 400)
                return
            # Auto-create session if it doesn't exist
            if not self.db.get_session(session_id):
                self.db.create_session(session_id)
            msg_id = self.db.append_message(
                session_id=session_id,
                role=body.get("role", "user"),
                content=body.get("content", ""),
                token_estimate=body.get("token_estimate"),
            )
            self._json_response({"message_id": msg_id}, 201)

        elif path == "/search":
            results = self.db.search(
                query=body.get("query", ""),
                role_filter=body.get("role_filter"),
                limit=body.get("limit", 20),
            )
            self._json_response(results)

        else:
            self._json_response({"error": "not found"}, 404)

    def log_message(self, format, *args):
        # Quiet logging — only errors
        if args and "404" not in str(args[0]):
            return


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Ari Memory Server (SQLite + FTS5)")
    parser.add_argument("--port", type=int, default=8192)
    parser.add_argument("--db", default="./data/ari_memory.db")
    args = parser.parse_args()

    db_path = Path(args.db)
    db = SessionDB(db_path)

    MemoryHandler.db = db

    server = HTTPServer(("127.0.0.1", args.port), MemoryHandler)
    print(f"Memory server running on http://127.0.0.1:{args.port}")
    print(f"Database: {db_path.resolve()}")
    print(f"Stats: {db.stats()}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        db.close()


if __name__ == "__main__":
    main()
