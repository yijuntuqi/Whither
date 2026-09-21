"""③ 验收（离线）：PDF 乱码修复前后统计。不调用 embedding。
用法: E:\\conda_envs\\langchain\\python.exe scripts/verify_cid_fix.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import fitz
from vectorize import SimpleTextSplitter, count_suspect, CID_FIX

splitter = SimpleTextSplitter()
total_before = total_after = 0
affected_files = 0
chunks_with_bad = 0
total_chunks = 0

for pdf_file in Path("data/pdfs").rglob("*.pdf"):
    doc = fitz.open(pdf_file)
    text = "\n".join(page.get_text() for page in doc)
    doc.close()
    if not text.strip():
        continue
    before = count_suspect(text)
    # 在修复前文本上切分，统计含乱码的 chunk（对照基线 2582/4289）
    raw_chunks = splitter.split_text(text)
    total_chunks += len(raw_chunks)
    chunks_with_bad += sum(1 for c in raw_chunks if count_suspect(c))
    fixed = text.translate(CID_FIX)
    after = count_suspect(fixed)
    total_before += before
    total_after += after
    if before:
        affected_files += 1

print(f"PDF 文件总数: {len(list(Path('data/pdfs').rglob('*.pdf')))}")
print(f"受影响文件: {affected_files}")
print(f"含乱码 chunk: {chunks_with_bad}/{total_chunks}")
print(f"可疑字符: 修复前 {total_before} → 修复后 {total_after}")
if total_after == 0:
    print("✅ ③ 验收通过：乱码 100% 修复")
else:
    print("❌ 仍有残留")
