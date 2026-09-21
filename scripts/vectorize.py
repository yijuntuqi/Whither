"""
向量化脚本：爬虫 JSON → 文本切分 → Ollama Embedding → 向量库

双 backend：
  - sqlite (默认)：embedding 存 JSON，numpy 算 cosine 检索，零依赖
  - pgvector (待 Neon 通了用)：用 pgvector + lakebase_ann

流程：
  1. 读取 data/crawled/free_travels/*.json
  2. 把每个自由行方案组装成一段文本
  3. LangChain RecursiveCharacterTextSplitter 切分
  4. Ollama nomic-embed-text 生成向量（768 维）
  5. 批量写入 sqlite/pgvector

同时支持 PDF：data/pdfs/*.pdf → PyMuPDF 提取文本 → 同样切分 + 向量化
"""
import os, json, time, sqlite3, re
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Optional

import httpx
from dotenv import load_dotenv
from loguru import logger


# -----------------------------------------------------------
# 纯 Python 文本切分器（替代 langchain_text_splitters）
# -----------------------------------------------------------

class SimpleTextSplitter:
    """递归字符切分器，中文感知"""

    def __init__(self, chunk_size: int = 800, chunk_overlap: int = 100,
                 separators=None):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or ["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""]

    def split_text(self, text: str) -> list[str]:
        if len(text) <= self.chunk_size:
            return [text] if text.strip() else []

        # 递归切分
        chunks = self._recursive_split(text, self.separators)

        # 合并过短的块 + 加 overlap
        merged = self._merge_chunks(chunks)
        return merged

    def _recursive_split(self, text: str, separators: list[str]) -> list[str]:
        if len(text) <= self.chunk_size:
            return [text]

        if not separators:
            # 强制切分
            return [text[i:i + self.chunk_size] for i in range(0, len(text), self.chunk_size)]

        sep = separators[0]
        if sep == "":
            # 按字符切
            return [text[i:i + self.chunk_size] for i in range(0, len(text), self.chunk_size)]

        parts = text.split(sep)
        # 保留分隔符
        pieces = []
        for i, p in enumerate(parts):
            if i > 0:
                pieces.append(sep + p) if p else None
            if p:
                pieces.append(p) if i == 0 else None
        # 简化：直接用 split 结果
        pieces = []
        for i, p in enumerate(parts):
            if i == 0:
                pieces.append(p)
            else:
                pieces.append(sep + p)

        # 递归每个 piece
        result = []
        for piece in pieces:
            if len(piece) <= self.chunk_size:
                if piece.strip():
                    result.append(piece)
            else:
                result.extend(self._recursive_split(piece, separators[1:]))
        return result

    def _merge_chunks(self, chunks: list[str]) -> list[str]:
        merged = []
        current = ""
        for chunk in chunks:
            if len(current) + len(chunk) <= self.chunk_size:
                current += chunk
            else:
                if current.strip():
                    merged.append(current)
                # 加 overlap：保留当前块尾部
                overlap = current[-self.chunk_overlap:] if self.chunk_overlap > 0 else ""
                current = overlap + chunk
        if current.strip():
            merged.append(current)
        return merged


# -----------------------------------------------------------
# Ollama Embedding 客户端
# -----------------------------------------------------------

class OllamaEmbedder:
    """Ollama 嵌入客户端（默认 bge-m3，1024 维，中文优化）"""

    def __init__(self, model: str = None, base_url: str = "http://localhost:11434"):
        load_dotenv()
        self.model = model or os.getenv("EMBED_MODEL", "bge-m3")
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(timeout=120.0)
        self._dim = None
        # 超长文本保护：bge-m3 context 8192 tokens，中文按约 1.3 token/字估算留余量
        self._max_chars = 6000

    def _embed_request(self, inputs: list[str]) -> list[list[float]]:
        """POST /api/embed 批量接口；瞬时故障自动重试（4 次，指数退避 2/4/8s）"""
        payload = {"model": self.model, "input": inputs}
        last_err = None
        for attempt in range(4):
            if attempt:
                wait = 2 ** attempt
                logger.warning(f"  ⏳ Ollama 请求失败，{wait}s 后重试 (第 {attempt}/3 次): {last_err}")
                time.sleep(wait)
            try:
                resp = self.client.post(f"{self.base_url}/api/embed", json=payload)
                resp.raise_for_status()
                return resp.json()["embeddings"]
            except (httpx.HTTPStatusError, httpx.TransportError, KeyError) as e:
                last_err = e
        raise last_err

    def embed(self, text: str) -> list[float]:
        """生成单条文本的 embedding"""
        return self._embed_request([text[:self._max_chars]])[0]

    def embed_batch(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        """批量 embedding：/api/embed 一次请求 batch_size 条（真批量，非串行）"""
        results = []
        total = len(texts)
        for i in range(0, total, batch_size):
            batch = [t[:self._max_chars] for t in texts[i:i + batch_size]]
            results.extend(self._embed_request(batch))
            logger.info(f"  Embedding: {min(i + batch_size, total)}/{total}")
        return results

    @property
    def dim(self) -> int:
        if self._dim is None:
            vec = self.embed("test")
            self._dim = len(vec)
            logger.info(f"✅ Embedding 维度: {self._dim} (模型: {self.model})")
        return self._dim


# -----------------------------------------------------------
# 文本组装
# -----------------------------------------------------------

def assemble_plan_text(plan: dict, city: str) -> str:
    """自由行方案 → RAG 文本"""
    title = plan.get("title", "").strip()
    highlights = plan.get("highlights", [])
    views = plan.get("views", "")
    url = plan.get("url", "")

    parts = [f"【自由行方案】城市: {city}"]
    if title:
        parts.append(f"标题: {title}")
    if highlights:
        parts.append(f"亮点: {' | '.join(highlights[:5])}")
    if views:
        parts.append(f"浏览量: {views}")
    if url:
        parts.append(f"链接: {url}")
    return "\n".join(parts)


def assemble_pdf_text(text: str, filename: str) -> str:
    return f"【城市攻略 PDF】文件: {filename}\n\n{text}"


# PDF 文件名常见后缀（按长度优先匹配）
_PDF_NAME_SUFFIXES = [
    "自由行旅游攻略", "自由行攻略", "旅游攻略",
    "自由行", "攻略", "旅游指南", "指南",
]


# PDF 字体 ToUnicode CMap 缺失导致的系统性错字（129 份 PDF 中 85 份受影响）
# 仅由这 15 个错字产生；前 6 个覆盖 97.7%，全部覆盖 100%
CID_FIX = str.maketrans({
    "癿": "的", "丌": "不", "呾": "和", "斴": "旅", "艱": "色", "佖": "你",
    "乊": "之", "兲": "关", "杢": "来", "俱": "倒", "佒": "何", "乬": "云",
    "冎": "冒", "刋": "刊", "刉": "划",
})
# 可疑字符集（这些生僻字在正常现代旅游文本中不应出现），用于导入后检测闸门
CID_SUSPECT = set(CID_FIX._interpolation) if hasattr(CID_FIX, "_interpolation") \
    else set("癿丌呾斴艱佖乊兲杢俱佒乬冎刋刉")


def count_suspect(text: str) -> int:
    """统计文本中的 PDF 乱码可疑字符数"""
    return sum(text.count(c) for c in CID_SUSPECT)


# mafengwo 库未覆盖、但用于专题名前缀归并的常见城市/省会（直辖市、省会、港澳台）
_COMMON_CITIES = [
    "北京", "上海", "天津", "重庆", "香港", "澳门",
    "石家庄", "太原", "呼和浩特", "沈阳", "长春", "哈尔滨",
    "济南", "郑州", "合肥", "南京", "杭州", "福州", "台北", "高雄",
    "武汉", "长沙", "南昌", "广州", "南宁", "海口", "贵阳", "昆明",
    "成都", "贵阳", "拉萨", "西安", "兰州", "西宁", "银川",
    "乌鲁木齐", "乌鲁木齐",
]


def extract_city_from_pdf(stem: str, known_cities: list[str]) -> str:
    """从 PDF 文件名提取城市/目的地。
    1) 去掉 旅游攻略/攻略/自由行 等后缀
    2) 库内城市名出现在文件名中 → 归到该城市（香港购物旅游攻略→香港）
    3) 专题名以前缀命中常见城市 → 同样归并
    4) 去掉"X日/X天"行程尾缀（台湾12日→台湾），纯中文 1-6 字则信任为新目的地
       （retriever 城市清单动态读取，写入后该城市即可被检索命中）
    不可信（含杂符号等）返回空串。"""
    name = stem.strip()
    for suf in _PDF_NAME_SUFFIXES:
        if name.endswith(suf):
            name = name[: -len(suf)].strip()
            break
    # 1) 专题名前缀归并（只信任固定常识表，避免库内历史专题脏名自我命中）
    for city in sorted(_COMMON_CITIES, key=len, reverse=True):
        if name.startswith(city):
            return city
    # 2) 库内城市名出现在文件名中 → 归到该城市
    for city in sorted(known_cities, key=len, reverse=True):
        if city in name:
            return city
    # 3) 去掉"12日/8天"之类行程尾缀：台湾12日 → 台湾
    name2 = re.sub(r"\d+\s*[日天]$", "", name).strip()
    if name2 and re.fullmatch(r"[\u4e00-\u9fff]{1,6}", name2):
        return name2
    return ""


# -----------------------------------------------------------
# embedding 存储格式工具（P2-1：JSON 文本 → float32 BLOB）
# -----------------------------------------------------------

def emb_to_blob(vec) -> bytes:
    """向量 → float32 BLOB（1024 维 JSON 文本 ~20KB → BLOB 4KB，省 5 倍）"""
    return np.asarray(vec, dtype=np.float32).tobytes()


def blob_to_vec(val):
    """兼容读取：BLOB → float32 向量；旧 JSON 文本 → list（迁移期共存）"""
    if isinstance(val, (bytes, memoryview, bytearray)):
        return np.frombuffer(val, dtype=np.float32).tolist()
    return json.loads(val)


# -----------------------------------------------------------
# SQLite 向量库 backend
# -----------------------------------------------------------

class SQLiteBackend:
    """SQLite 向量库：embedding 存 JSON，检索用 numpy cosine"""

    def __init__(self, db_path: str = "data/rag.sqlite"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _init_schema(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS whither_rag_embeddings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_type TEXT,
                    source_id TEXT,
                    chunk_index INTEGER,
                    city TEXT,
                    chunk_text TEXT,
                    embedding_json TEXT,
                    metadata TEXT,
                    created_at TEXT,
                    UNIQUE(source_type, source_id, chunk_index)
                )
            """)
            self._migrate_schema(conn)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_rag_city ON whither_rag_embeddings(city)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_rag_source ON whither_rag_embeddings(source_type, source_id)")
            conn.commit()

    def _migrate_schema(self, conn):
        """旧库迁移：补 chunk_index（按来源内插入顺序）→ 去重 → 建 UNIQUE 索引"""
        cols = [r[1] for r in conn.execute("PRAGMA table_info(whither_rag_embeddings)").fetchall()]
        if "chunk_index" not in cols:
            logger.info("🔧 迁移旧库：添加 chunk_index 列")
            conn.execute("ALTER TABLE whither_rag_embeddings ADD COLUMN chunk_index INTEGER")
            conn.commit()
            groups = conn.execute(
                "SELECT DISTINCT source_type, source_id FROM whither_rag_embeddings"
            ).fetchall()
            for source_type, source_id in groups:
                ids = [r[0] for r in conn.execute(
                    "SELECT id FROM whither_rag_embeddings "
                    "WHERE source_type=? AND source_id=? ORDER BY id",
                    (source_type, source_id),
                )]
                conn.executemany(
                    "UPDATE whither_rag_embeddings SET chunk_index=? WHERE id=?",
                    list(enumerate(ids)),
                )
            conn.commit()
            before = conn.execute("SELECT COUNT(*) FROM whither_rag_embeddings").fetchone()[0]
            conn.execute(
                "DELETE FROM whither_rag_embeddings WHERE id NOT IN "
                "(SELECT MIN(id) FROM whither_rag_embeddings "
                " GROUP BY source_type, source_id, chunk_index)"
            )
            conn.commit()
            after = conn.execute("SELECT COUNT(*) FROM whither_rag_embeddings").fetchone()[0]
            logger.info(f"🔧 迁移去重: {before} → {after} 行（删除 {before-after} 条重复）")
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_rag_chunk "
            "ON whither_rag_embeddings(source_type, source_id, chunk_index)"
        )

    def insert_batch(self, chunks: list[dict], embeddings: list[list[float]]):
        now = datetime.now().isoformat()
        rows = [
            (
                c["source_type"],
                c["source_id"],
                c["chunk_index"],
                c["city"],
                c["chunk_text"],
                emb_to_blob(emb),
                c["metadata"],
                now,
            )
            for c, emb in zip(chunks, embeddings)
        ]
        with sqlite3.connect(self.db_path) as conn:
            conn.executemany(
                """INSERT OR REPLACE INTO whither_rag_embeddings
                   (source_type, source_id, chunk_index, city, chunk_text,
                    embedding_json, metadata, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                rows,
            )
            conn.commit()

    def delete_by_source_type(self, source_type: str) -> int:
        """按来源清空旧数据（根治孤儿行：chunk 切分变化时 INSERT OR REPLACE
        命不中旧键，残留旧维度向量会让检索矩阵构建直接崩溃）"""
        with sqlite3.connect(self.db_path) as conn:
            n = conn.execute(
                "DELETE FROM whither_rag_embeddings WHERE source_type = ?",
                (source_type,),
            ).rowcount
            conn.commit()
        if n:
            logger.info(f"  🗑 先删后插: 清除旧 {source_type} 数据 {n} 条")
        return n

    def count(self) -> int:
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute("SELECT COUNT(*) FROM whither_rag_embeddings").fetchone()[0]

    def count_cities(self) -> int:
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute(
                "SELECT COUNT(DISTINCT city) FROM whither_rag_embeddings WHERE city != ''"
            ).fetchone()[0]

    def distinct_cities(self) -> list[str]:
        """库内已有城市列表（用于 PDF 文件名的城市校验）"""
        with sqlite3.connect(self.db_path) as conn:
            return [r[0] for r in conn.execute(
                "SELECT DISTINCT city FROM whither_rag_embeddings WHERE city != ''"
            ).fetchall()]

    def search(self, query_vec: list[float], top_k: int = 5, city: str = None) -> list[dict]:
        """numpy cosine 检索；指定 city 时先过滤该城市再排序"""
        import numpy as np
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if city:
                rows = conn.execute(
                    "SELECT id, source_type, source_id, city, chunk_text, embedding_json, metadata "
                    "FROM whither_rag_embeddings WHERE city = ?",
                    (city,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, source_type, source_id, city, chunk_text, embedding_json, metadata FROM whither_rag_embeddings"
                ).fetchall()

        if not rows:
            return []

        matrix = np.array([blob_to_vec(r["embedding_json"]) for r in rows], dtype=np.float32)
        q = np.array(query_vec, dtype=np.float32)
        # cosine
        scores = matrix @ q / (np.linalg.norm(matrix, axis=1) * np.linalg.norm(q) + 1e-8)
        top_idx = np.argsort(-scores)[:top_k]

        return [
            {
                "id": rows[i]["id"],
                "source_type": rows[i]["source_type"],
                "source_id": rows[i]["source_id"],
                "city": rows[i]["city"],
                "chunk_text": rows[i]["chunk_text"],
                "metadata": rows[i]["metadata"],
                "score": float(scores[i]),
            }
            for i in top_idx
        ]


# -----------------------------------------------------------
# pgvector backend (Neon, 待用)
# -----------------------------------------------------------

class PgVectorBackend:
    def __init__(self, db_url: str):
        import psycopg
        self.db_url = db_url.replace("&channel_binding=require", "")
        self.psycopg = psycopg

    def connect(self):
        params = self.psycopg.conninfo.conninfo_to_dict(self.db_url)
        params["connect_timeout"] = "15"
        return self.psycopg.connect(**params)

    def insert_batch(self, chunks: list[dict], embeddings: list[list[float]]):
        with self.connect() as conn:
            with conn.cursor() as cur:
                for c, emb in zip(chunks, embeddings):
                    cur.execute(
                        """INSERT INTO whither_rag_embeddings
                           (source_type, source_id, city, chunk_text, embedding, metadata)
                           VALUES (%s, %s, %s, %s, %s::vector, %s::jsonb)""",
                        (c["source_type"], c["source_id"], c["city"],
                         c["chunk_text"], json.dumps(emb), c["metadata"]),
                    )
            conn.commit()

    def count(self) -> int:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM whither_rag_embeddings")
                return cur.fetchone()[0]

    def count_cities(self) -> int:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(DISTINCT city) FROM whither_rag_embeddings WHERE city != ''")
                return cur.fetchone()[0]

    def search(self, query_vec: list[float], top_k: int = 5) -> list[dict]:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT id, source_type, source_id, city, chunk_text, metadata,
                              embedding <=> %s::vector AS distance
                       FROM whither_rag_embeddings
                       ORDER BY distance ASC LIMIT %s""",
                    (json.dumps(query_vec), top_k),
                )
                rows = cur.fetchall()
        return [
            {
                "id": r[0], "source_type": r[1], "source_id": r[2],
                "city": r[3], "chunk_text": r[4], "metadata": r[5],
                "score": 1 - float(r[6]),
            }
            for r in rows
        ]


# -----------------------------------------------------------
# 主导入器
# -----------------------------------------------------------

class VectorImporter:
    def __init__(self, backend: str = "auto", db_url: Optional[str] = None):
        load_dotenv()
        self.embedder = OllamaEmbedder()
        self.splitter = SimpleTextSplitter(
            chunk_size=800,
            chunk_overlap=100,
        )
        self.stats = {"docs": 0, "chunks": 0, "embedded": 0}

        # 选择 backend
        if backend == "auto":
            # 优先 pgvector，连不上 fallback sqlite
            neon_url = db_url or os.getenv("NEON_DATABASE_URL") or os.getenv("NEON_DATABASE_URL_UNPOOLED")
            if neon_url:
                try:
                    self.backend = PgVectorBackend(neon_url)
                    self.backend.connect().close()
                    logger.info("✅ 使用 pgvector backend (Neon 连接成功)")
                except Exception as e:
                    logger.warning(f"⚠️  Neon 连接失败 ({type(e).__name__})，fallback 到 SQLite")
                    self.backend = SQLiteBackend()
            else:
                self.backend = SQLiteBackend()
        elif backend == "sqlite":
            self.backend = SQLiteBackend()
            logger.info("✅ 使用 SQLite backend")
        elif backend == "pgvector":
            neon_url = db_url or os.getenv("NEON_DATABASE_URL") or os.getenv("NEON_DATABASE_URL_UNPOOLED")
            self.backend = PgVectorBackend(neon_url)
            logger.info("✅ 使用 pgvector backend (强制)")
        else:
            raise ValueError(f"未知 backend: {backend}")

    def import_crawled_free_travels(self, glob_pattern: str = "data/crawled/free_travels/*.json"):
        logger.info("📥 导入自由行爬虫数据")

        # 用 glob.glob 而不是 Path.glob，避免 *.json 被当成路径
        import glob as _glob
        files = [Path(f) for f in _glob.glob(glob_pattern, recursive=False)]
        if not files:
            logger.warning(f"  没找到爬虫 JSON 文件: {glob_pattern}")
            return

        logger.info(f"  找到 {len(files)} 个城市文件")

        all_chunks = []
        for f in files:
            data = json.loads(f.read_text(encoding="utf-8"))
            city = data.get("city", "")
            plans = data.get("plans", [])

            for plan in plans:
                text = assemble_plan_text(plan, city)
                if not text or len(text) < 10:
                    continue

                if len(text) < self.splitter.chunk_size:
                    chunks = [text]
                else:
                    chunks = self.splitter.split_text(text)

                for chunk_index, chunk_text in enumerate(chunks):
                    all_chunks.append({
                        "chunk_text": chunk_text,
                        "source_type": "mafengwo_free",
                        "source_id": str(plan.get("plan_id", "")),
                        "chunk_index": chunk_index,
                        "city": city,
                        "metadata": json.dumps({
                            "title": plan.get("title", ""),
                            "url": plan.get("url", ""),
                            "views": plan.get("views", ""),
                        }, ensure_ascii=False),
                    })

                self.stats["docs"] += 1

        logger.info(f"  📋 共 {len(all_chunks)} 个文本块待向量化")
        self._embed_and_insert(all_chunks)

    def import_pdfs(self, pdf_dir: str = "data/pdfs"):
        pdf_path = Path(pdf_dir)
        if not pdf_path.exists():
            logger.info(f"📁 data/pdfs 目录不存在，跳过 PDF 导入")
            return

        pdfs = list(pdf_path.rglob("*.pdf"))
        if not pdfs:
            logger.info(f"  没有 PDF 文件")
            return

        logger.info(f"📥 导入 {len(pdfs)} 个 PDF")

        known_cities = self.backend.distinct_cities()
        logger.info(f"🗺️  库内已有 {len(known_cities)} 个城市，用于 PDF 城市校验")

        all_chunks = []
        unmatched = []
        total_bad_before = 0
        total_bad_after = 0
        try:
            import fitz  # PyMuPDF
        except ImportError:
            logger.error("  ❌ 需要安装 PyMuPDF: pip install pymupdf")
            return

        for pdf_file in pdfs:
            try:
                doc = fitz.open(pdf_file)
                text_parts = []
                for page in doc:
                    text_parts.append(page.get_text())
                doc.close()

                full_text = "\n".join(text_parts)
                if not full_text.strip():
                    continue

                # PDF 乱码修复（ToUnicode CMap 缺失的系统性错字）
                bad_before = count_suspect(full_text)
                full_text = full_text.translate(CID_FIX)
                bad_after = count_suspect(full_text)
                total_bad_before += bad_before
                total_bad_after += bad_after
                if bad_before:
                    logger.info(f"  🔤 {pdf_file.name}: 修复乱码 {bad_before} → 残留 {bad_after}")

                city = extract_city_from_pdf(pdf_file.stem, known_cities)
                if not city:
                    unmatched.append(pdf_file.name)

                # source_id 带上父分类目录，避免同名不同版本 PDF 互相覆盖
                source_id = f"{pdf_file.parent.name}/{pdf_file.stem}"
                chunks = self.splitter.split_text(full_text)
                for chunk_index, chunk_text in enumerate(chunks):
                    all_chunks.append({
                        "chunk_text": assemble_pdf_text(chunk_text, pdf_file.name),
                        "source_type": "pdf",
                        "source_id": source_id,
                        "chunk_index": chunk_index,
                        "city": city,
                        "metadata": json.dumps(
                            {"filename": pdf_file.name, "city": city},
                            ensure_ascii=False,
                        ),
                    })

                self.stats["docs"] += 1
                logger.info(f"  📄 {pdf_file.name}: {len(chunks)} chunks, city={city or '（未匹配）'}")
            except Exception as e:
                logger.error(f"  ❌ {pdf_file.name}: {e}")

        # 乱码检测闸门：修复后可疑字符必须清零
        logger.info(f"🔤 乱码检测闸门: 修复前 {total_bad_before} → 修复后 {total_bad_after}")
        if total_bad_after > 0:
            logger.error("❌ 仍有 PDF 乱码未修复，请补充 CID_FIX 映射！")
        else:
            logger.info("✅ PDF 乱码已全部修复（可疑字符 = 0）")

        if unmatched:
            logger.warning(
                f"⚠️ {len(unmatched)} 个 PDF 城市未匹配（city 留空，仅全库检索可达）: "
                f"{', '.join(unmatched)}"
            )

        if all_chunks:
            self._embed_and_insert(all_chunks)

    def import_ocr_texts(self, ocr_dir: str = "data/ocr_texts"):
        """从 OCR 文本导入 PDF 攻略（乱码根治：fitz 渲染 200dpi → RapidOCR 重提取）。

        文本文件名 {parent}__{stem}.txt ↔ source_id {parent}/{stem}，
        与 import_pdfs 的 source_id 规则对齐，可无缝替换旧 PDF 数据。
        OCR 文本天然无 ToUnicode CMap 乱码，无需 CID_FIX。"""
        ocr_path = Path(ocr_dir)
        files = sorted(ocr_path.glob("*.txt")) if ocr_path.exists() else []
        if not files:
            logger.warning(f"  没找到 OCR 文本文件: {ocr_dir}")
            return

        logger.info(f"📥 导入 {len(files)} 个 OCR 文本（PDF 乱码根治版）")
        known_cities = self.backend.distinct_cities()

        all_chunks = []
        for txt in files:
            text = txt.read_text(encoding="utf-8")
            if not text.strip():
                continue

            # OCR 文件名 = 相对 data/pdfs 的目录路径 + 文件名，全用 "__" 连接
            # 还原 import_pdfs 的 source_id 规则（只取直接父目录一层）: parent.name/stem
            parts = txt.stem.split("__")
            name = parts[-1]
            source_id = f"{parts[-2]}/{name}" if len(parts) >= 2 else f"pdfs/{name}"
            filename = f"{name}.pdf"

            city = extract_city_from_pdf(name, known_cities)

            chunks = self.splitter.split_text(text)
            for chunk_index, chunk_text in enumerate(chunks):
                all_chunks.append({
                    "chunk_text": assemble_pdf_text(chunk_text, filename),
                    "source_type": "pdf",
                    "source_id": source_id,
                    "chunk_index": chunk_index,
                    "city": city,
                    "metadata": json.dumps(
                        {"filename": filename, "city": city, "ocr": True},
                        ensure_ascii=False,
                    ),
                })

            self.stats["docs"] += 1

        logger.info(f"  📋 共 {len(all_chunks)} 个文本块待向量化")
        if all_chunks:
            self._embed_and_insert(all_chunks)

    def _embed_and_insert(self, chunks: list[dict], batch_size: int = 32):
        if not chunks:
            return

        logger.info(f"🧠 开始向量化 {len(chunks)} 个文本块...")
        logger.info(f"   Embedding: {self.embedder.model} ({self.embedder.dim} 维)")

        total = len(chunks)
        purged_types: set[str] = set()
        for i in range(0, total, batch_size):
            batch = chunks[i:i + batch_size]
            batch_texts = [c["chunk_text"] for c in batch]
            embeddings = self.embedder.embed_batch(batch_texts)  # 失败即抛出，旧数据不动

            # 首批 embedding 成功后按 source_type 先删旧数据再插入（防孤儿行）
            st = batch[0]["source_type"]
            if st not in purged_types:
                self.backend.delete_by_source_type(st)
                purged_types.add(st)

            self.backend.insert_batch(batch, embeddings)
            self.stats["embedded"] += len(batch)
            logger.info(f"  ✅ 已写入: {min(i + batch_size, total)}/{total}")

        total_rows = self.backend.count()
        cities = self.backend.count_cities()

        logger.info(f"\n🎉 向量化导入完成！")
        logger.info(f"   总行数: {total_rows}")
        logger.info(f"   覆盖城市: {cities}")


# -----------------------------------------------------------
# 测试检索
# -----------------------------------------------------------

def test_search(query: str = "北京有什么好玩的", top_k: int = 5):
    embedder = OllamaEmbedder()
    query_vec = embedder.embed(query)

    backend = SQLiteBackend()
    results = backend.search(query_vec, top_k=top_k)

    logger.info(f"\n🔍 检索: '{query}'  Top {top_k}:")
    for r in results:
        chunk = r["chunk_text"][:100].replace("\n", " ")
        meta = json.loads(r["metadata"]) if r["metadata"] else {}
        title = meta.get("title", "")
        logger.info(f"  [score={r['score']:.4f}] city={r['city']}")
        logger.info(f"    title: {title}")
        logger.info(f"    chunk: {chunk}...")


# -----------------------------------------------------------
# 入口
# -----------------------------------------------------------

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="向量化脚本：爬虫数据/PDF → Ollama → SQLite/pgvector")
    parser.add_argument("--backend", default="auto", choices=["auto", "sqlite", "pgvector"],
                        help="向量库 backend (auto: 先 pgvector 失败 fallback sqlite)")
    parser.add_argument("--skip-free", action="store_true", help="跳过自由行数据")
    parser.add_argument("--skip-pdf", action="store_true", help="跳过 PDF")
    parser.add_argument("--from-ocr", action="store_true",
                        help="PDF 数据改从 data/ocr_texts/ 导入（RapidOCR 乱码根治版）")
    parser.add_argument("--search", type=str, default=None, help="导入后测试检索")
    args = parser.parse_args()

    importer = VectorImporter(backend=args.backend)

    if not args.skip_free:
        importer.import_crawled_free_travels()

    if not args.skip_pdf:
        if args.from_ocr:
            importer.import_ocr_texts()
        else:
            importer.import_pdfs()

    if args.search:
        time.sleep(1)
        test_search(args.search)
