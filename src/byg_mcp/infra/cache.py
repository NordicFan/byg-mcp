"""Persistent cache i SQLite. Én fil, ingen server. Overlever genstart af MCP-serveren."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any


class SQLiteCache:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("CREATE TABLE IF NOT EXISTS cache (k TEXT PRIMARY KEY, udloeber REAL NOT NULL, v TEXT NOT NULL)")
        self._db.commit()

    def get(self, key: str) -> Any | None:
        with self._lock:
            row = self._db.execute("SELECT udloeber, v FROM cache WHERE k = ?", (key,)).fetchone()
        if row is None:
            return None
        if time.time() > row[0]:
            with self._lock:
                self._db.execute("DELETE FROM cache WHERE k = ?", (key,))
                self._db.commit()
            return None
        return json.loads(row[1])

    def set(self, key: str, value: Any, ttl: float) -> None:
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO cache (k, udloeber, v) VALUES (?, ?, ?)",
                (key, time.time() + ttl, json.dumps(value, ensure_ascii=False)),
            )
            self._db.commit()

    def ryd_udloebne(self) -> int:
        with self._lock:
            n = self._db.execute("DELETE FROM cache WHERE udloeber < ?", (time.time(),)).rowcount
            self._db.commit()
        return n
