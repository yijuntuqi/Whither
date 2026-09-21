"""
旅行知识库检索器
- SQLite 向量检索（bge-m3 1024 维，cosine 相似度）
- 城市自动识别 + 城市过滤（避免跨城市语义干扰）
"""
import os
import json
import sqlite3
from pathlib import Path

import httpx
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DB_PATH = PROJECT_ROOT / "data" / "rag.sqlite"


class TravelRetriever:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = str(db_path)
        self.ollama_base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.embed_model = os.getenv("EMBED_MODEL", "bge-m3")  # 须与 vectorize.py 一致
        self._cities_cache = None
        # 嵌入矩阵缓存：进程内只从 SQLite 全量加载一次，查询零表扫描
        self._matrix = None          # np.ndarray (n, dim) 已归一化
        self._rows_meta = None       # [(city, chunk_text, metadata_json), ...]

    def _ensure_matrix(self):
        if self._matrix is not None:
            return
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT city, chunk_text, metadata, embedding_json FROM whither_rag_embeddings"
            ).fetchall()
        import json as _json
        import numpy as _np

        def _to_vec(v):  # 兼容 BLOB(float32) 与旧 JSON 文本（迁移期共存）
            if isinstance(v, (bytes, memoryview, bytearray)):
                return _np.frombuffer(v, dtype=_np.float32)
            return _np.array(_json.loads(v), dtype=_np.float32)

        mat = _np.vstack([_to_vec(r["embedding_json"]) for r in rows])
        norms = _np.linalg.norm(mat, axis=1, keepdims=True)
        self._matrix = mat / (norms + 1e-8)
        self._rows_meta = [(r["city"], r["chunk_text"], r["metadata"]) for r in rows]

    def reload(self):
        """知识库更新后调用，强制重建矩阵缓存"""
        self._matrix = None
        self._rows_meta = None
        self._cities_cache = None

    # ---------- 基础 ----------
    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def embed_query(self, text: str) -> list[float]:
        provider = os.getenv("EMBEDDING_PROVIDER", "ollama").lower()
        if provider == "dashscope":
            return self._embed_dashscope(text)
        return self._embed_ollama(text)

    def _embed_ollama(self, text: str) -> list[float]:
        resp = httpx.post(
            f"{self.ollama_base}/api/embed",
            json={"model": self.embed_model, "input": [text[:6000]]},
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()["embeddings"][0]

    def _embed_dashscope(self, text: str) -> list[float]:
        """DashScope embedding（默认 qwen3.7-text-embedding，1024维，与 bge-m3 兼容）"""
        import dashscope
        dashscope.api_key = os.getenv("DASHSCOPE_API_KEY", "")
        resp = dashscope.TextEmbedding.call(
            model=os.getenv("DASHSCOPE_EMBED_MODEL", "qwen3.7-text-embedding"),
            input=text[:6000],
        )
        if resp.status_code != 200:
            raise RuntimeError(f"DashScope embed error: {resp.message}")
        return resp.output["embeddings"][0]["embedding"]

    def supported_cities(self) -> list[str]:
        """知识库覆盖的城市（按字数降序，便于子串匹配优先命中长地名）"""
        if self._cities_cache is None:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT DISTINCT city FROM whither_rag_embeddings "
                    "WHERE city != ''"
                ).fetchall()
            self._cities_cache = sorted((r["city"] for r in rows), key=len, reverse=True)
        return self._cities_cache

    def detect_city(self, query: str) -> str | None:
        """从用户问题里识别城市名（子串匹配）"""
        for city in self.supported_cities():
            if city in query:
                return city
        return None

    # ---------- 检索 ----------
    def search(self, query: str, city: str | None = None, top_k: int = 5) -> list[dict]:
        """
        向量检索（基于内存矩阵缓存，查询时零 SQL）。
        city 为空时全库检索；指定时只在该城市攻略内检索。
        返回 [{city, title, url, views, snippet, score}, ...]
        """
        # 未显式给城市时尝试自动识别
        if not city:
            city = self.detect_city(query)

        self._ensure_matrix()
        qv = np.array(self.embed_query(query), dtype=np.float32)
        qv = qv / (np.linalg.norm(qv) + 1e-8)

        if city:
            mask = np.array([c == city for c, _, _ in self._rows_meta], dtype=bool)
            if not mask.any():
                return []
            scores = self._matrix[mask] @ qv
            idx = np.argsort(-scores)[:top_k]
            local_rows = [r for r, m in zip(self._rows_meta, mask) if m]
        else:
            scores = self._matrix @ qv
            idx = np.argsort(-scores)[:top_k]
            local_rows = self._rows_meta

        results = []
        for i in idx:
            r_city, r_chunk, r_meta_raw = local_rows[i]
            meta = json.loads(r_meta_raw)
            results.append({
                "city": r_city,
                "title": meta.get("title", ""),
                "url": meta.get("url", ""),
                "views": meta.get("views", ""),
                "snippet": r_chunk[:200].replace("\n", " "),
                "score": round(float(scores[i]), 4),
            })
        return results

    def format_results(self, results: list[dict]) -> str:
        """把检索结果格式化为给 LLM 的上下文文本"""
        if not results:
            return "知识库中没有找到相关攻略。"
        lines = []
        for i, r in enumerate(results, 1):
            loc = f" | {r['city']}" if r["city"] else ""
            hot = f" | 热度{r['views']}" if r["views"] else ""
            lines.append(
                f"[{i}] {r['title']}{loc}{hot}\n"
                f"    链接: {r['url']}\n"
                f"    内容: {r['snippet']}..."
            )
        return "\n".join(lines)


# 模块级单例（tool 复用）
_retriever = None


def get_retriever() -> TravelRetriever:
    global _retriever
    if _retriever is None:
        _retriever = TravelRetriever()
    return _retriever
