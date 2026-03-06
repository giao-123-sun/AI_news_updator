import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
RAW_CSV = ROOT / "twitter_all_users.csv"
OUT_DIR = ROOT / "reports" / "daily"
OUT_JSON = OUT_DIR / "twitter_reader_data.json"
OUT_HTML = OUT_DIR / "twitter_reader.html"
ASSET_DIR = OUT_DIR / "twitter_reader_assets"
TEMPLATE_HTML = ROOT / "templates" / "twitter_reader_template.html"


def parse_list_field(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, float) and pd.isna(value):
        return []
    s = str(value).strip()
    if not s:
        return []
    parts = [p.strip() for p in s.split("|")]
    return [p for p in parts if p]


def to_float(value: object) -> float:
    try:
        if value is None:
            return 0.0
        if isinstance(value, float) and pd.isna(value):
            return 0.0
        return float(value)
    except Exception:
        return 0.0


def to_int(value: object) -> int:
    return int(to_float(value))


def normalize_row(row: pd.Series) -> dict:
    local_images_raw = parse_list_field(row.get("本地图片"))
    remote_images = parse_list_field(row.get("图片链接"))
    local_images = []
    for p in local_images_raw:
        rel = p.replace("\\", "/").strip()
        abs_p = ROOT / rel
        if abs_p.exists():
            local_images.append("../../" + rel)
    return {
        "author": str(row.get("发帖人", "") or "").strip(),
        "tweet_id": str(row.get("推文ID", "") or "").strip(),
        "tweet_url": str(row.get("推文链接", "") or "").strip(),
        "content": str(row.get("内容", "") or "").strip(),
        "time": str(row.get("时间", "") or "").strip(),
        "likes": to_int(row.get("点赞")),
        "replies": to_int(row.get("评论")),
        "reposts": to_int(row.get("转发")),
        "bio": str(row.get("简介", "") or "").strip(),
        "followers": to_int(row.get("粉丝量")),
        "following": to_int(row.get("关注量")),
        "external_link": str(row.get("外部链接", "") or "").strip(),
        "remote_images": remote_images,
        "local_images": local_images,
        "hosted_images": [],
    }

def choose_images(item: dict) -> list[str]:
    # Prefer remote image links for GitHub Pages compatibility.
    merged: list[str] = []
    for u in item.get("remote_images", []):
        if u and u not in merged:
            merged.append(u)
    for u in item.get("local_images", []):
        if u and u not in merged:
            merged.append(u)
    return merged


def stable_str(v: object) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and pd.isna(v):
        return ""
    s = str(v).strip()
    if s.lower() == "nan":
        return ""
    return s


def dedup_key(item: dict) -> str:
    tid = stable_str(item.get("tweet_id"))
    if tid:
        return f"id:{tid}"
    turl = stable_str(item.get("tweet_url"))
    if turl:
        return f"url:{turl}"
    author = stable_str(item.get("author"))
    t = stable_str(item.get("time"))
    content = stable_str(item.get("content"))[:200]
    return f"fallback:{author}|{t}|{content}"


def row_quality(item: dict) -> tuple:
    images = len(choose_images(item))
    engage = int(item.get("likes", 0)) + int(item.get("replies", 0)) + int(item.get("reposts", 0))
    content_len = len(stable_str(item.get("content")))
    has_link = 1 if stable_str(item.get("external_link")) else 0
    t = parse_time_for_sort(stable_str(item.get("time")))
    return (images, engage, has_link, content_len, t)


def deduplicate_rows(rows: list[dict]) -> tuple[list[dict], int]:
    best: dict[str, dict] = {}
    for item in rows:
        k = dedup_key(item)
        prev = best.get(k)
        if prev is None or row_quality(item) > row_quality(prev):
            best[k] = item
    deduped = list(best.values())
    return deduped, len(rows) - len(deduped)


def stage_hosted_images(rows: list[dict], hosted_posts: int) -> tuple[int, int]:
    if ASSET_DIR.exists():
        shutil.rmtree(ASSET_DIR)
    ASSET_DIR.mkdir(parents=True, exist_ok=True)

    posts_with_assets = 0
    bytes_total = 0
    for r in rows:
        if posts_with_assets >= hosted_posts:
            break
        locals_in_row = [u for u in (r.get("local_images") or []) if u]
        if not locals_in_row:
            continue
        tweet_id = stable_str(r.get("tweet_id")) or "noid"
        hosted = []
        copied_any = False
        for idx, rel in enumerate(locals_in_row, start=1):
            rel_clean = rel.replace("\\", "/").strip()
            if rel_clean.startswith("../../"):
                rel_clean = rel_clean[6:]
            src = ROOT / rel_clean
            if not src.exists():
                continue
            ext = src.suffix.lower() or ".jpg"
            dst_name = f"{tweet_id}_{idx}{ext}"
            dst = ASSET_DIR / dst_name
            shutil.copy2(src, dst)
            hosted.append(f"./twitter_reader_assets/{dst_name}")
            bytes_total += dst.stat().st_size
            copied_any = True
        if copied_any:
            r["hosted_images"] = hosted
            posts_with_assets += 1
    return posts_with_assets, bytes_total


def parse_time_for_sort(time_str: str) -> float:
    try:
        dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
        return dt.timestamp()
    except Exception:
        return 0.0


def build_payload(max_rows: int) -> dict:
    if not RAW_CSV.exists():
        return {
            "meta": {
                "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
                "source_csv": RAW_CSV.as_posix(),
                "exists": False,
                "total_rows": 0,
                "rows_in_page": 0,
            },
            "rows": [],
        }

    df = pd.read_csv(RAW_CSV, encoding="utf-8-sig")
    raw_rows = [normalize_row(r) for _, r in df.iterrows()]
    rows, removed = deduplicate_rows(raw_rows)
    rows.sort(
        key=lambda x: (
            len(choose_images(x)),
            parse_time_for_sort(x.get("time", "")),
            x.get("likes", 0),
            x.get("replies", 0),
            x.get("reposts", 0),
        ),
        reverse=True,
    )
    limited = rows[:max_rows]
    hosted_posts = int(os.environ.get("TW_READER_HOSTED_POSTS", str(max_rows)))
    hosted_count, hosted_bytes = stage_hosted_images(limited, hosted_posts=hosted_posts)

    latest_time = limited[0]["time"] if limited else ""
    with_images = sum(1 for r in limited if choose_images(r))
    authors = len({r.get("author", "") for r in limited if r.get("author", "")})
    return {
        "meta": {
            "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "source_csv": RAW_CSV.as_posix(),
            "exists": True,
            "latest_time": latest_time,
            "total_rows_before_dedup": len(raw_rows),
            "duplicates_removed": removed,
            "total_rows": len(rows),
            "rows_in_page": len(limited),
            "authors_in_page": authors,
            "with_images_in_page": with_images,
            "hosted_image_posts": hosted_count,
            "hosted_image_bytes": hosted_bytes,
        },
        "rows": limited,
    }


def build_html() -> str:
    if TEMPLATE_HTML.exists():
        return TEMPLATE_HTML.read_text(encoding="utf-8")
    return """<!doctype html><html><body><p>template missing: templates/twitter_reader_template.html</p></body></html>"""

def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    max_rows = int(os.environ.get("TW_READER_MAX_ROWS", "2000"))
    payload = build_payload(max_rows=max_rows)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_HTML.write_text(build_html(), encoding="utf-8")
    print(f"[ok] wrote {OUT_JSON.as_posix()} rows={len(payload.get('rows', []))}")
    print(f"[ok] wrote {OUT_HTML.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
