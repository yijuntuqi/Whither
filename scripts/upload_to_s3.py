"""
爬虫原始数据备份到 Neon S3
- data/crawled/free_travels/*.json → s3://whither/crawled/free_travels/
- data/crawled/city_index.json    → s3://whither/crawled/city_index.json
"""
import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from loguru import logger
import boto3

load_dotenv()

BUCKET = os.getenv("AWS_BUCKET_NAME")
s3 = boto3.client(
    "s3",
    endpoint_url=os.getenv("AWS_ENDPOINT_URL_S3"),
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_REGION"),
)

files = list(Path("data/crawled/free_travels").glob("*.json")) + [Path("data/crawled/city_index.json")]
logger.info(f"📤 上传 {len(files)} 个文件 → s3://{BUCKET}/crawled/")

ok, fail = 0, 0
for f in files:
    key = f"crawled/{f.parent.name}/{f.name}" if f.parent.name == "free_travels" else f"crawled/{f.name}"
    try:
        s3.upload_file(str(f), BUCKET, key)
        ok += 1
    except Exception as e:
        fail += 1
        logger.error(f"  ❌ {f.name}: {e}")

logger.info(f"✅ 上传完成: {ok} 成功 / {fail} 失败")

# 验证：列出部分对象
resp = s3.list_objects_v2(Bucket=BUCKET, Prefix="crawled/", MaxKeys=5)
objs = resp.get("Contents", [])
logger.info(f"📋 验证 s3://{BUCKET}/crawled/ 前5个对象:")
for o in objs:
    logger.info(f"   {o['Key']} ({o['Size']/1024:.1f} KB)")
