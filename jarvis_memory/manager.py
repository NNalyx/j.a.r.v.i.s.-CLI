"""Local long-term memory backed by SQLite and vector retrieval."""

from __future__ import annotations

import array
import hashlib
import json
import math
import re
import sqlite3
import threading
from datetime import datetime
from typing import Any, Dict, Iterable, List, Tuple

from jarvis_core.constants import MEMORY_DB_FILE, MEMORY_FILE


class MemoryManager:
    """Manage durable memory records and retrieve the most relevant ones."""

    MAX_CHARS = 5000
    CHUNK_CHARS = 500
    VECTOR_DIMENSIONS = 384
    EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    _lock = threading.RLock()
    _embedder = None
    _embedder_failed = False

    @classmethod
    def _connect(cls) -> sqlite3.Connection:
        connection = sqlite3.connect(str(MEMORY_DB_FILE), timeout=15)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute(
            "CREATE TABLE IF NOT EXISTS memory_records ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, content TEXT NOT NULL, "
            "created_at TEXT NOT NULL, embedding BLOB, embedding_model TEXT)"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS memory_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        cls._migrate_legacy_json(connection)
        return connection

    @classmethod
    def _migrate_legacy_json(cls, connection: sqlite3.Connection) -> None:
        migrated = connection.execute(
            "SELECT value FROM memory_metadata WHERE key='legacy_json_migrated'"
        ).fetchone()
        if migrated:
            return

        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as legacy_file:
                data = json.load(legacy_file)
            content = str(data.get("content") or "").strip()
            if content and "память пуста" not in content.lower():
                created_at = str(data.get("last_updated") or cls._now())
                cls._insert_chunks(connection, content, created_at)
        except FileNotFoundError:
            pass
        except Exception:
            # Leave the legacy file untouched and let normal memory operations work.
            return

        connection.execute(
            "INSERT OR REPLACE INTO memory_metadata(key, value) VALUES('legacy_json_migrated', '1')"
        )
        connection.commit()

    @staticmethod
    def _now() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @classmethod
    def _chunks(cls, content: str) -> List[str]:
        text = str(content or "").strip()
        if not text:
            return []
        chunks: List[str] = []
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
        for paragraph in paragraphs or [text]:
            while len(paragraph) > cls.CHUNK_CHARS:
                cut = paragraph.rfind(" ", 0, cls.CHUNK_CHARS)
                if cut < cls.CHUNK_CHARS // 2:
                    cut = cls.CHUNK_CHARS
                chunks.append(paragraph[:cut].strip())
                paragraph = paragraph[cut:].strip()
            if paragraph:
                chunks.append(paragraph)
        return chunks

    @classmethod
    def _insert_chunks(cls, connection: sqlite3.Connection, content: str, created_at: str) -> int:
        chunks = cls._chunks(content)
        connection.executemany(
            "INSERT INTO memory_records(content, created_at) VALUES(?, ?)",
            [(chunk, created_at) for chunk in chunks],
        )
        return len(chunks)

    @classmethod
    def _load_embedder(cls):
        if cls._embedder is not None or cls._embedder_failed:
            return cls._embedder
        try:
            from fastembed import TextEmbedding

            cls._embedder = TextEmbedding(model_name=cls.EMBEDDING_MODEL)
        except Exception:
            # Hash embeddings below keep memory search available offline and on
            # installations where the optional semantic model is not installed.
            cls._embedder_failed = True
        return cls._embedder

    @classmethod
    def _hash_embedding(cls, text: str) -> List[float]:
        normalized = re.sub(r"\s+", " ", str(text or "").lower()).strip()
        words = re.findall(r"[\w-]+", normalized, flags=re.UNICODE)
        features = list(words)
        features.extend(f"{left} {right}" for left, right in zip(words, words[1:]))
        compact = re.sub(r"\s+", "", normalized)
        features.extend(compact[index:index + 3] for index in range(max(0, len(compact) - 2)))

        vector = [0.0] * cls.VECTOR_DIMENSIONS
        for feature in features:
            digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
            value = int.from_bytes(digest[:4], "little")
            index = value % cls.VECTOR_DIMENSIONS
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector))
        return [value / norm for value in vector] if norm else vector

    @classmethod
    def _embed(cls, text: str, query: bool = False) -> Tuple[List[float], str]:
        embedder = cls._load_embedder()
        if embedder is not None:
            try:
                method = embedder.query_embed if query else embedder.embed
                vector = next(iter(method([text])))
                return [float(value) for value in vector], cls.EMBEDDING_MODEL
            except Exception:
                cls._embedder = None
                cls._embedder_failed = True
        return cls._hash_embedding(text), "multilingual-hash-chargram-v1"

    @staticmethod
    def _vector_blob(vector: Iterable[float]) -> bytes:
        values = array.array("f", vector)
        return values.tobytes()

    @staticmethod
    def _blob_vector(blob: bytes) -> List[float]:
        values = array.array("f")
        values.frombytes(blob)
        return list(values)

    @staticmethod
    def _cosine(left: List[float], right: List[float]) -> float:
        if len(left) != len(right) or not left:
            return 0.0
        dot = sum(a * b for a, b in zip(left, right))
        left_norm = math.sqrt(sum(value * value for value in left))
        right_norm = math.sqrt(sum(value * value for value in right))
        return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0

    @classmethod
    def _ensure_vectors(cls, connection: sqlite3.Connection, model: str) -> None:
        rows = connection.execute(
            "SELECT id, content FROM memory_records WHERE embedding IS NULL OR embedding_model != ?",
            (model,),
        ).fetchall()
        if not rows:
            return
        updates = []
        for row in rows:
            vector, actual_model = cls._embed(row["content"], query=False)
            if actual_model != model:
                # Do not mix vectors from different embedding spaces.
                return
            updates.append((cls._vector_blob(vector), model, row["id"]))
        connection.executemany(
            "UPDATE memory_records SET embedding=?, embedding_model=? WHERE id=?", updates
        )
        connection.commit()

    @classmethod
    def read(cls) -> Dict[str, Any]:
        try:
            with cls._lock, cls._connect() as connection:
                rows = connection.execute(
                    "SELECT content, created_at FROM memory_records ORDER BY id"
                ).fetchall()
            content = "\n\n".join(row["content"] for row in rows)
            last_updated = rows[-1]["created_at"] if rows else cls._now()
            return {"success": True, "content": content or "Память пуста.", "last_updated": last_updated}
        except Exception as exc:
            return {"success": False, "error": str(exc), "content": ""}

    @classmethod
    def write(cls, content: str) -> Dict[str, Any]:
        try:
            text = str(content or "")[:cls.MAX_CHARS].strip()
            with cls._lock, cls._connect() as connection:
                connection.execute("DELETE FROM memory_records")
                cls._insert_chunks(connection, text, cls._now())
                connection.commit()
            return {"success": True, "message": "Память записана в локальную векторную базу"}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    @classmethod
    def append(cls, content: str) -> Dict[str, Any]:
        try:
            text = str(content or "").strip()
            if not text:
                return {"success": False, "error": "Нельзя добавить пустую запись"}
            with cls._lock, cls._connect() as connection:
                cls._insert_chunks(connection, f"[{cls._now()}] {text}", cls._now())
                connection.commit()
            return {"success": True, "message": "Запись добавлена в локальную векторную базу"}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    @classmethod
    def clear(cls) -> Dict[str, Any]:
        try:
            with cls._lock, cls._connect() as connection:
                connection.execute("DELETE FROM memory_records")
                connection.execute(
                    "INSERT OR REPLACE INTO memory_metadata(key, value) VALUES('legacy_json_migrated', '1')"
                )
                connection.commit()
            return {"success": True, "message": "Векторная память очищена"}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    @classmethod
    def search(cls, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        text = str(query or "").strip()
        if not text:
            return []
        try:
            with cls._lock, cls._connect() as connection:
                if not connection.execute("SELECT 1 FROM memory_records LIMIT 1").fetchone():
                    return []
                query_vector, model = cls._embed(text, query=True)
                cls._ensure_vectors(connection, model)
                rows = connection.execute(
                    "SELECT id, content, created_at, embedding FROM memory_records "
                    "WHERE embedding_model=? AND embedding IS NOT NULL",
                    (model,),
                ).fetchall()
                ranked = [
                    (cls._cosine(query_vector, cls._blob_vector(row["embedding"])), row)
                    for row in rows
                ]
                ranked.sort(key=lambda item: item[0], reverse=True)
                return [
                    {"content": row["content"], "created_at": row["created_at"], "score": score}
                    for score, row in ranked
                    if score >= 0.12
                ][:max(1, int(limit))]
        except Exception:
            return []

    @classmethod
    def get_summary(cls) -> str:
        result = cls.read()
        if result["success"]:
            return str(result["content"])[-3000:]
        return "Не удалось загрузить память."

    @classmethod
    def get_context_for_prompt(cls, query: str = "", limit: int = 5) -> str:
        matches = cls.search(query, limit=limit) if query else []
        if not matches:
            return ""
        return "\n".join(f"- {item['content']}" for item in matches)
