import html
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
    return """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Twitter Crawl Reader</title>
  <style>
    :root {
      --bg: #f4f0e6;
      --panel: #fffdf8;
      --line: #ddd4c1;
      --ink: #1f2937;
      --muted: #6b7280;
      --accent: #0b5cab;
      --chip: #f3f4f6;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at 10% 0%, #fff6df 0, transparent 35%),
        radial-gradient(circle at 90% 10%, #e8f3ff 0, transparent 30%),
        var(--bg);
    }
    .wrap { max-width: 1120px; margin: 0 auto; padding: 16px 14px 38px; }
    .card {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 14px;
      margin-bottom: 10px;
      box-shadow: 0 6px 20px rgba(20, 27, 45, .06);
    }
    h1 {
      margin: 0 0 6px;
      font-size: 30px;
      line-height: 1.1;
      font-family: Georgia, "Times New Roman", serif;
    }
    .muted { color: var(--muted); }
    .toolbar {
      display: grid;
      grid-template-columns: 1.6fr 1fr 1fr 1fr auto;
      gap: 8px;
    }
    .toolbar input, .toolbar select, .toolbar button {
      border: 1px solid var(--line);
      background: #fff;
      border-radius: 10px;
      padding: 10px 12px;
      font-size: 14px;
    }
    .toolbar button {
      cursor: pointer;
      background: #0f172a;
      color: #fff;
      border-color: #0f172a;
    }
    .kpis {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin-top: 8px;
    }
    .kpi {
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 4px 10px;
      font-size: 12px;
      background: #fff;
    }
    .list {
      display: grid;
      grid-template-columns: 1fr;
      gap: 10px;
    }
    .item {
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 12px;
      background: #fff;
    }
    .meta {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      align-items: center;
      margin-bottom: 6px;
      font-size: 13px;
      color: var(--muted);
    }
    .author { font-weight: 700; color: var(--ink); }
    .chips { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 8px; }
    .chip {
      background: var(--chip);
      border: 1px solid #e5e7eb;
      border-radius: 999px;
      padding: 2px 8px;
      font-size: 12px;
    }
    .content {
      white-space: pre-wrap;
      line-height: 1.55;
      margin-bottom: 8px;
    }
    .links a {
      color: var(--accent);
      text-decoration: none;
      margin-right: 12px;
      font-size: 13px;
    }
    .links a:hover { text-decoration: underline; }
    .gallery {
      margin-top: 8px;
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 8px;
    }
    .gallery img {
      width: 100%;
      height: 180px;
      object-fit: cover;
      border-radius: 10px;
      border: 1px solid var(--line);
      background: #f3f4f6;
    }
    .load-more {
      margin-top: 8px;
      text-align: center;
    }
    .load-more button {
      border: 1px solid var(--line);
      background: #fff;
      border-radius: 999px;
      padding: 8px 16px;
      cursor: pointer;
    }
    @media (max-width: 900px) {
      .toolbar { grid-template-columns: 1fr; }
      h1 { font-size: 26px; }
    }
  </style>
</head>
<body>
  <main class="wrap">
    <section class="card">
      <h1>Twitter Crawl Reader</h1>
      <div class="muted">查看最新抓取的推文文本、原帖链接和配图。支持搜索、按作者筛选、仅看带图内容。</div>
      <div class="kpis">
        <span class="kpi" id="kpi-updated">更新时间: -</span>
        <span class="kpi" id="kpi-total">抓取总条数: -</span>
        <span class="kpi" id="kpi-show">本页载入: -</span>
        <span class="kpi" id="kpi-authors">作者数: -</span>
        <span class="kpi" id="kpi-img">带图条数: -</span>
      </div>
    </section>

    <section class="card">
      <div class="toolbar">
        <input id="q" placeholder="搜索作者 / 内容 / 外链" />
        <select id="author">
          <option value="">全部作者</option>
        </select>
        <select id="has-image">
          <option value="">全部内容</option>
          <option value="1">仅看带图</option>
        </select>
        <select id="sort">
          <option value="image_time_desc">图文优先</option>
          <option value="time_desc">按时间(新->旧)</option>
          <option value="likes_desc">按点赞(高->低)</option>
        </select>
        <button id="reset">重置</button>
      </div>
    </section>

    <section class="list" id="list"></section>
    <div class="load-more"><button id="more">加载更多</button></div>
  </main>

  <script>
    const state = {
      all: [],
      filtered: [],
      pageSize: 30,
      page: 1,
    };

    const esc = (s) =>
      String(s ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;");

    const getImages = (row) => {
      const hosted = Array.isArray(row.hosted_images) ? row.hosted_images.filter(Boolean) : [];
      const remote = Array.isArray(row.remote_images) ? row.remote_images.filter(Boolean) : [];
      const local = Array.isArray(row.local_images) ? row.local_images.filter(Boolean) : [];
      const uniq = [];
      // On GitHub Pages, local crawl images are usually not published.
      // Prefer remote URLs to avoid broken-image noise.
      const source = hosted.length ? hosted : (remote.length ? remote : local);
      for (const u of source) {
        if (u && !uniq.includes(u)) uniq.push(u);
      }
      return uniq;
    };

    function sortRows(rows, sortType) {
      const copy = [...rows];
      if (sortType === "image_time_desc") {
        copy.sort((a, b) => {
          const ai = getImages(a).length;
          const bi = getImages(b).length;
          if (bi !== ai) return bi - ai;
          return String(b.time || "").localeCompare(String(a.time || ""));
        });
        return copy;
      }
      if (sortType === "likes_desc") {
        copy.sort((a, b) => (b.likes || 0) - (a.likes || 0));
        return copy;
      }
      copy.sort((a, b) => String(b.time || "").localeCompare(String(a.time || "")));
      return copy;
    }

    function applyFilter() {
      const q = document.getElementById("q").value.trim().toLowerCase();
      const author = document.getElementById("author").value;
      const hasImage = document.getElementById("has-image").value === "1";
      const sortType = document.getElementById("sort").value;

      let rows = state.all.filter((r) => {
        if (author && r.author !== author) return false;
        if (hasImage && getImages(r).length === 0) return false;
        if (!q) return true;
        const blob = [
          r.author,
          r.content,
          r.external_link,
          r.tweet_url,
        ]
          .join(" ")
          .toLowerCase();
        return blob.includes(q);
      });

      rows = sortRows(rows, sortType);
      state.filtered = rows;
      state.page = 1;
      render();
    }

    function render() {
      const list = document.getElementById("list");
      const showRows = state.filtered.slice(0, state.page * state.pageSize);
      list.innerHTML = showRows
        .map((r) => {
          const images = getImages(r);
          const gallery = images.length
            ? `<div class="gallery">${images
                .map((u) => `<a href="${esc(u)}" target="_blank" rel="noopener noreferrer"><img loading="lazy" src="${esc(u)}" alt="tweet image" onerror="if(!this.dataset.retry){this.dataset.retry='1';if(this.src.indexOf('name=orig')>-1){this.src=this.src.replace('name=orig','name=large');return;}}this.parentElement.style.display='none';" /></a>`)
                .join("")}</div>`
            : "";
          const links = `
            <div class="links">
              ${r.tweet_url ? `<a href="${esc(r.tweet_url)}" target="_blank" rel="noopener noreferrer">原推文</a>` : ""}
              ${r.external_link ? `<a href="${esc(r.external_link)}" target="_blank" rel="noopener noreferrer">外部链接</a>` : ""}
            </div>
          `;
          return `
            <article class="item">
              <div class="meta">
                <span class="author">@${esc(r.author)}</span>
                <span>${esc(r.time || "-")}</span>
                <span>粉丝 ${esc(r.followers || 0)}</span>
              </div>
              <div class="chips">
                <span class="chip">赞 ${esc(r.likes || 0)}</span>
                <span class="chip">评 ${esc(r.replies || 0)}</span>
                <span class="chip">转 ${esc(r.reposts || 0)}</span>
                <span class="chip">图片 ${images.length}</span>
              </div>
              <div class="content">${esc(r.content || "")}</div>
              ${links}
              ${gallery}
            </article>
          `;
        })
        .join("");

      const moreBtn = document.getElementById("more");
      if (showRows.length >= state.filtered.length) {
        moreBtn.style.display = "none";
      } else {
        moreBtn.style.display = "inline-block";
      }
    }

    function fillAuthors(rows) {
      const set = new Set(rows.map((r) => r.author).filter(Boolean));
      const authors = [...set].sort((a, b) => a.localeCompare(b));
      const sel = document.getElementById("author");
      sel.innerHTML =
        `<option value="">全部作者</option>` +
        authors.map((a) => `<option value="${esc(a)}">${esc(a)}</option>`).join("");
    }

    function setMeta(meta) {
      document.getElementById("kpi-updated").textContent = `更新时间: ${meta.generated_at_utc || "-"}`;
      const removed = Number(meta.duplicates_removed || 0);
      const before = Number(meta.total_rows_before_dedup || meta.total_rows || 0);
      const after = Number(meta.total_rows || 0);
      document.getElementById("kpi-total").textContent = `抓取总条数: ${after} (原始 ${before}, 去重 ${removed})`;
      document.getElementById("kpi-show").textContent = `本页载入: ${meta.rows_in_page || 0}`;
      document.getElementById("kpi-authors").textContent = `作者数: ${meta.authors_in_page || 0}`;
      const hostedPosts = Number(meta.hosted_image_posts || 0);
      const hostedMB = (Number(meta.hosted_image_bytes || 0) / (1024 * 1024)).toFixed(1);
      document.getElementById("kpi-img").textContent = `带图条数: ${meta.with_images_in_page || 0} (本地托管 ${hostedPosts} 条, ${hostedMB}MB)`;
    }

    async function bootstrap() {
      const res = await fetch("./twitter_reader_data.json", { cache: "no-cache" });
      const payload = await res.json();
      const rows = Array.isArray(payload.rows) ? payload.rows : [];
      state.all = rows;
      state.filtered = [...rows];
      fillAuthors(rows);
      setMeta(payload.meta || {});
      applyFilter();
    }

    document.getElementById("q").addEventListener("input", applyFilter);
    document.getElementById("author").addEventListener("change", applyFilter);
    document.getElementById("has-image").addEventListener("change", applyFilter);
    document.getElementById("sort").addEventListener("change", applyFilter);
    document.getElementById("more").addEventListener("click", () => {
      state.page += 1;
      render();
    });
    document.getElementById("reset").addEventListener("click", () => {
      document.getElementById("q").value = "";
      document.getElementById("author").value = "";
      document.getElementById("has-image").value = "";
      document.getElementById("sort").value = "image_time_desc";
      applyFilter();
    });

    bootstrap().catch((err) => {
      const list = document.getElementById("list");
      list.innerHTML = `<section class="card">加载失败: ${esc(err.message || err)}</section>`;
    });
  </script>
</body>
</html>
"""


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
