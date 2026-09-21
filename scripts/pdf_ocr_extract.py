"""
PDF 乱码根治 · 方案D：RapidOCR 全量重提取
- fitz 渲染 200dpi → RapidOCR(onnxruntime, CPU) → 行文本拼接
- 输出 data/ocr_texts/{parent}__{stem}.txt（对应 vectorize 的 source_id = parent/stem）
- 断点续传：txt 已存在则跳过
- 分片：--shard i --shards N 处理第 i/N 片（可多进程并行）

用法:
  python scripts/pdf_ocr_extract.py --shard 0 --shards 3   # 后台并行 3 份
  python scripts/pdf_ocr_extract.py --status                # 查看进度
"""
import sys, time, json
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "scripts"))

from loguru import logger

PDF_DIR = PROJECT / "data" / "pdfs"
OUT_DIR = PROJECT / "data" / "ocr_texts"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def all_pdfs() -> list[Path]:
    return sorted(PDF_DIR.rglob("*.pdf"))


def out_name(pdf: Path) -> str:
    rel = pdf.relative_to(PDF_DIR)
    return "__".join(rel.parts[:-1] + (rel.stem,)) + ".txt"


def status():
    pdfs = all_pdfs()
    done = [p for p in pdfs if (OUT_DIR / out_name(p)).exists()]
    print(f"OCR 进度: {len(done)}/{len(pdfs)} 个文件完成")
    missing = [p.name for p in pdfs if not (OUT_DIR / out_name(p)).exists()]
    if missing:
        print("未完成:", "、".join(missing[:20]) + ("..." if len(missing) > 20 else ""))


def run(shard: int, shards: int):
    from rapidocr_onnxruntime import RapidOCR
    import fitz

    ocr = RapidOCR()
    pdfs = [p for i, p in enumerate(all_pdfs()) if i % shards == shard]
    logger.info(f"🚀 shard {shard}/{shards}: {len(pdfs)} 个 PDF")

    t_start = time.time()
    for k, pdf in enumerate(pdfs, 1):
        out = OUT_DIR / out_name(pdf)
        if out.exists():
            logger.info(f"[{k}/{len(pdfs)}] ⏭ {pdf.name} 已有，跳过")
            continue
        try:
            doc = fitz.open(pdf)
            parts = []
            for page in doc:
                pix = page.get_pixmap(dpi=200)
                result, _ = ocr(pix.tobytes("png"))
                if result:
                    parts.append("\n".join(r[1] for r in result))
            doc.close()
            text = "\n\n".join(parts)
            out.write_text(text, encoding="utf-8")
            logger.info(f"[{k}/{len(pdfs)}] 💾 {pdf.name}: {len(text):,} 字 "
                        f"(累计 {time.time()-t_start:.0f}s)")
        except Exception as e:
            logger.error(f"[{k}/{len(pdfs)}] ❌ {pdf.name}: {type(e).__name__}: {e}")
    logger.info(f"✅ shard {shard} 完成，耗时 {time.time()-t_start:.0f}s")


if __name__ == "__main__":
    if "--status" in sys.argv:
        status()
    else:
        shard = int(sys.argv[sys.argv.index("--shard") + 1]) if "--shard" in sys.argv else 0
        shards = int(sys.argv[sys.argv.index("--shards") + 1]) if "--shards" in sys.argv else 1
        run(shard, shards)
