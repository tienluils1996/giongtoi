"""Lưu trữ SQLite: hồ sơ giọng, mẫu tham chiếu, dự án đọc (chương/câu), từ điển, cài đặt."""

from __future__ import annotations

import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS voices (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS voice_refs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    voice_id TEXT NOT NULL REFERENCES voices(id) ON DELETE CASCADE,
    label TEXT NOT NULL DEFAULT 'bình thường',
    audio_path TEXT NOT NULL,
    raw_path TEXT,
    transcript TEXT NOT NULL DEFAULT '',
    duration REAL NOT NULL DEFAULT 0,
    is_default INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    voice_id TEXT,
    ref_id INTEGER,
    engine TEXT NOT NULL,
    speed REAL NOT NULL DEFAULT 1.0,
    pause_sentence_ms INTEGER NOT NULL DEFAULT 300,
    pause_paragraph_ms INTEGER NOT NULL DEFAULT 700,
    english_mode TEXT NOT NULL DEFAULT 'vietnamize',
    status TEXT NOT NULL DEFAULT 'draft',
    error TEXT,
    source_text TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS chapters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    idx INTEGER NOT NULL,
    title TEXT NOT NULL,
    wav_path TEXT,
    mp3_path TEXT,
    duration REAL
);
CREATE TABLE IF NOT EXISTS segments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    chapter_id INTEGER NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    idx INTEGER NOT NULL,
    text TEXT NOT NULL,
    paragraph_end INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',
    audio_path TEXT,
    duration REAL,
    error TEXT,
    seconds REAL
);
CREATE INDEX IF NOT EXISTS idx_segments_project ON segments(project_id, status);
CREATE TABLE IF NOT EXISTS lexicon (
    term TEXT PRIMARY KEY,
    reading TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


class Store:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        with self.conn() as c:
            c.executescript(SCHEMA)

    @contextmanager
    def conn(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            c = sqlite3.connect(self.path, timeout=30)
            c.row_factory = sqlite3.Row
            c.execute("PRAGMA foreign_keys = ON")
            c.execute("PRAGMA journal_mode = WAL")
            try:
                yield c
                c.commit()
            finally:
                c.close()

    # ------------------------------------------------------------ helpers
    def _all(self, sql: str, args: tuple = ()) -> list[dict[str, Any]]:
        with self.conn() as c:
            return [dict(r) for r in c.execute(sql, args).fetchall()]

    def _one(self, sql: str, args: tuple = ()) -> dict[str, Any] | None:
        rows = self._all(sql, args)
        return rows[0] if rows else None

    def _exec(self, sql: str, args: tuple = ()) -> int:
        with self.conn() as c:
            return c.execute(sql, args).lastrowid

    # ------------------------------------------------------------ voices
    def create_voice(self, voice_id: str, name: str) -> dict:
        self._exec("INSERT INTO voices(id, name, created_at) VALUES (?,?,?)", (voice_id, name, time.time()))
        return self.get_voice(voice_id)

    def get_voice(self, voice_id: str) -> dict | None:
        return self._one("SELECT * FROM voices WHERE id=?", (voice_id,))

    def list_voices(self) -> list[dict]:
        return self._all("SELECT * FROM voices ORDER BY created_at")

    def delete_voice(self, voice_id: str) -> None:
        self._exec("DELETE FROM voices WHERE id=?", (voice_id,))

    def add_ref(self, voice_id: str, audio_path: str, transcript: str, duration: float,
                label: str = "bình thường", raw_path: str | None = None) -> int:
        has_default = self._one("SELECT 1 FROM voice_refs WHERE voice_id=? AND is_default=1", (voice_id,))
        return self._exec(
            "INSERT INTO voice_refs(voice_id,label,audio_path,raw_path,transcript,duration,is_default,created_at)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (voice_id, label, audio_path, raw_path, transcript, duration, 0 if has_default else 1, time.time()),
        )

    def list_refs(self, voice_id: str) -> list[dict]:
        return self._all("SELECT * FROM voice_refs WHERE voice_id=? ORDER BY id", (voice_id,))

    def get_ref(self, ref_id: int) -> dict | None:
        return self._one("SELECT * FROM voice_refs WHERE id=?", (ref_id,))

    def default_ref(self, voice_id: str) -> dict | None:
        return self._one(
            "SELECT * FROM voice_refs WHERE voice_id=? ORDER BY is_default DESC, id LIMIT 1", (voice_id,)
        )

    def set_default_ref(self, ref_id: int) -> None:
        ref = self.get_ref(ref_id)
        if not ref:
            return
        with self.conn() as c:
            c.execute("UPDATE voice_refs SET is_default=0 WHERE voice_id=?", (ref["voice_id"],))
            c.execute("UPDATE voice_refs SET is_default=1 WHERE id=?", (ref_id,))

    def update_ref(self, ref_id: int, **fields) -> None:
        self._update("voice_refs", ref_id, fields)

    def delete_ref(self, ref_id: int) -> dict | None:
        ref = self.get_ref(ref_id)
        if ref:
            self._exec("DELETE FROM voice_refs WHERE id=?", (ref_id,))
            if ref["is_default"]:
                nxt = self.default_ref(ref["voice_id"])
                if nxt:
                    self.set_default_ref(nxt["id"])
        return ref

    # ------------------------------------------------------------ projects
    def create_project(self, title: str, source_text: str, engine: str, voice_id: str | None,
                       ref_id: int | None, speed: float = 1.0, pause_sentence_ms: int = 300,
                       pause_paragraph_ms: int = 700, english_mode: str = "vietnamize",
                       chapters: list[tuple[str, list[tuple[str, bool]]]] = ()) -> int:
        now = time.time()
        with self.conn() as c:
            pid = c.execute(
                "INSERT INTO projects(title,voice_id,ref_id,engine,speed,pause_sentence_ms,pause_paragraph_ms,"
                "english_mode,status,source_text,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (title, voice_id, ref_id, engine, speed, pause_sentence_ms, pause_paragraph_ms,
                 english_mode, "draft", source_text, now, now),
            ).lastrowid
            for ci, (ctitle, segs) in enumerate(chapters):
                cid = c.execute(
                    "INSERT INTO chapters(project_id, idx, title) VALUES (?,?,?)", (pid, ci, ctitle)
                ).lastrowid
                c.executemany(
                    "INSERT INTO segments(project_id, chapter_id, idx, text, paragraph_end) VALUES (?,?,?,?,?)",
                    [(pid, cid, si, t, int(pe)) for si, (t, pe) in enumerate(segs)],
                )
        return pid

    def get_project(self, pid: int) -> dict | None:
        return self._one("SELECT * FROM projects WHERE id=?", (pid,))

    def list_projects(self) -> list[dict]:
        return self._all(
            "SELECT p.*, "
            " (SELECT COUNT(*) FROM segments s WHERE s.project_id=p.id) AS n_total,"
            " (SELECT COUNT(*) FROM segments s WHERE s.project_id=p.id AND s.status='done') AS n_done,"
            " (SELECT COUNT(*) FROM segments s WHERE s.project_id=p.id AND s.status='error') AS n_error"
            " FROM projects p ORDER BY p.updated_at DESC"
        )

    def update_project(self, pid: int, **fields) -> None:
        fields["updated_at"] = time.time()
        self._update("projects", pid, fields)

    def delete_project(self, pid: int) -> None:
        self._exec("DELETE FROM projects WHERE id=?", (pid,))

    def next_queued_project(self) -> dict | None:
        return self._one(
            "SELECT * FROM projects WHERE status IN ('queued','running') ORDER BY updated_at LIMIT 1"
        )

    def reset_running(self) -> None:
        """Khi khởi động lại: việc đang chạy dở → xếp hàng lại để chạy tiếp."""
        self._exec("UPDATE projects SET status='queued' WHERE status='running'")

    # ------------------------------------------------------------ chapters & segments
    def list_chapters(self, pid: int) -> list[dict]:
        return self._all("SELECT * FROM chapters WHERE project_id=? ORDER BY idx", (pid,))

    def get_chapter(self, cid: int) -> dict | None:
        return self._one("SELECT * FROM chapters WHERE id=?", (cid,))

    def update_chapter(self, cid: int, **fields) -> None:
        self._update("chapters", cid, fields)

    def list_segments(self, pid: int, chapter_id: int | None = None) -> list[dict]:
        if chapter_id is None:
            return self._all(
                "SELECT s.* FROM segments s JOIN chapters c ON c.id=s.chapter_id"
                " WHERE s.project_id=? ORDER BY c.idx, s.idx", (pid,))
        return self._all("SELECT * FROM segments WHERE chapter_id=? ORDER BY idx", (chapter_id,))

    def next_pending_segment(self, pid: int) -> dict | None:
        return self._one(
            "SELECT s.* FROM segments s JOIN chapters c ON c.id=s.chapter_id"
            " WHERE s.project_id=? AND s.status='pending' ORDER BY c.idx, s.idx LIMIT 1", (pid,))

    def get_segment(self, sid: int) -> dict | None:
        return self._one("SELECT * FROM segments WHERE id=?", (sid,))

    def update_segment(self, sid: int, **fields) -> None:
        self._update("segments", sid, fields)

    # ------------------------------------------------------------ lexicon
    def lexicon(self) -> dict[str, str]:
        return {r["term"]: r["reading"] for r in self._all("SELECT term, reading FROM lexicon ORDER BY term")}

    def set_lexicon(self, term: str, reading: str) -> None:
        self._exec(
            "INSERT INTO lexicon(term, reading, created_at) VALUES (?,?,?)"
            " ON CONFLICT(term) DO UPDATE SET reading=excluded.reading",
            (term.strip(), reading.strip(), time.time()),
        )

    def delete_lexicon(self, term: str) -> None:
        self._exec("DELETE FROM lexicon WHERE term=?", (term,))

    # ------------------------------------------------------------ settings
    def get_setting(self, key: str, default: str | None = None) -> str | None:
        row = self._one("SELECT value FROM settings WHERE key=?", (key,))
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        self._exec(
            "INSERT INTO settings(key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )

    # ------------------------------------------------------------
    _ALLOWED = {
        "projects": {"title", "status", "error", "speed", "pause_sentence_ms", "pause_paragraph_ms",
                     "english_mode", "engine", "voice_id", "ref_id", "updated_at"},
        "chapters": {"wav_path", "mp3_path", "duration", "title"},
        "segments": {"text", "status", "audio_path", "duration", "error", "seconds"},
        "voice_refs": {"label", "transcript"},
    }

    def _update(self, table: str, row_id: int, fields: dict) -> None:
        bad = set(fields) - self._ALLOWED[table]
        if bad:
            raise ValueError(f"Trường không hợp lệ cho {table}: {bad}")
        if not fields:
            return
        cols = ", ".join(f"{k}=?" for k in fields)
        self._exec(f"UPDATE {table} SET {cols} WHERE id=?", (*fields.values(), row_id))
