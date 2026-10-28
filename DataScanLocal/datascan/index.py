"""Bounded-memory local scratch index; stores fingerprints and coordinates, not values."""
from __future__ import annotations

import hashlib
import sqlite3
import struct
import tempfile
from contextlib import contextmanager
from pathlib import Path

KINDS = {"exact", "reordered", "decimal", "affine"}


def fingerprint(values) -> bytes:
    digest = hashlib.blake2b(digest_size=20)
    if values and isinstance(values[0], str):
        digest.update("\0".join(values).encode("ascii"))
    else:
        for value in values:
            # Python numeric equality considers -0.0 and +0.0 equal.
            digest.update(struct.pack("<d", value if value else 0.0))
    return digest.digest()


class CandidateIndex:
    def __init__(self, batch_size=10_000, cancelled=lambda: False):
        if not 1 <= batch_size <= 100_000:
            raise ValueError("索引批量大小必须在 1–100,000 之间。")
        self.batch_size = batch_size
        self.cancelled = cancelled
        self.count = 0
        self.pending = 0
        self.directory = None
        self.connection = None

    def check(self):
        if self.cancelled():
            raise InterruptedError("已取消核验；未生成部分结果。")

    def __enter__(self):
        self.check()
        self.directory = tempfile.TemporaryDirectory(prefix="datascan-index-")
        try:
            self.connection = sqlite3.connect(str(Path(self.directory.name) / "index.sqlite"))
            # This disposable database is regenerated on every scan; durability is unnecessary.
            self.connection.execute("PRAGMA journal_mode=OFF")
            self.connection.execute("PRAGMA synchronous=OFF")
            self.connection.execute("PRAGMA temp_store=FILE")
            self.connection.execute("PRAGMA cache_size=-8192")
            self.connection.execute("""CREATE TABLE candidates (
                id INTEGER PRIMARY KEY, source INTEGER, start INTEGER, stop INTEGER, step INTEGER,
                scope TEXT, n INTEGER, exact BLOB, reordered BLOB, decimal BLOB, affine BLOB
            )""")
            self.connection.set_progress_handler(lambda: int(self.cancelled()), 10_000)
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, *_):
        try:
            if self.connection is not None:
                self.connection.close()
                self.connection = None
        finally:
            if self.directory is not None:
                self.directory.cleanup()
                self.directory = None

    def add(self, reference, scope, size, signatures):
        if self.pending == 0:
            self.check()
        hashes = [fingerprint(signatures[k]) if signatures.get(k) is not None else None
                  for k in ("exact", "reordered", "decimal", "affine")]
        try:
            self.connection.execute("INSERT INTO candidates VALUES (NULL,?,?,?,?,?,?,?,?,?,?)",
                                    (*reference, scope, size, *hashes))
            self.count += 1
            self.pending += 1
            if self.pending >= self.batch_size:
                self.connection.commit()
                self.pending = 0
        except sqlite3.OperationalError as error:
            if self.cancelled():
                raise InterruptedError("已取消核验；未生成部分结果。") from error
            raise

    @contextmanager
    def groups(self, kind):
        """Yield streaming matching groups, ordered longest first, without fetchall()."""
        if kind not in KINDS:
            raise ValueError("Unknown index kind")
        self.check()
        self.connection.commit()
        self.pending = 0
        group_cursor = None
        current_cursor = None
        try:
            # kind is restricted above, never interpolated from a user value.
            self.connection.execute(f"CREATE INDEX match_{kind} ON candidates(scope,n,{kind})")
            group_cursor = self.connection.execute(f"""
                SELECT scope,n,{kind},MIN(id) FROM candidates WHERE {kind} IS NOT NULL
                GROUP BY scope,n,{kind} HAVING COUNT(*)>1 ORDER BY n DESC,MIN(id)
            """)

            def groups():
                nonlocal current_cursor
                for scope, size, key, _ in group_cursor:
                    self.check()
                    if current_cursor is not None:
                        current_cursor.close()
                    current_cursor = self.connection.execute(f"""
                        SELECT source,start,stop,step FROM candidates
                        WHERE scope=? AND n=? AND {kind}=? ORDER BY id
                    """, (scope, size, key))
                    yield current_cursor

            yield groups()
        except sqlite3.OperationalError as error:
            if self.cancelled():
                raise InterruptedError("已取消核验；未生成部分结果。") from error
            raise
        finally:
            if current_cursor is not None:
                current_cursor.close()
            if group_cursor is not None:
                group_cursor.close()
            # Reuse disk pages for the next rule rather than retaining four large indices.
            self.connection.set_progress_handler(None, 0)
            try:
                self.connection.execute(f"DROP INDEX IF EXISTS match_{kind}")
            finally:
                self.connection.set_progress_handler(lambda: int(self.cancelled()), 10_000)
