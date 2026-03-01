import html
import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path(".")
FEED_CSV = ROOT / "report" / "post_feed_v1.csv"
OUT_DIR = ROOT / "report" / "ai_digest_clone"
DIGEST_DIR = OUT_DIR / "digest"
SOURCES_DIR = OUT_DIR / "sources"


def safe(v):
    if v is None:
        return ""
    t = str(v).strip()
    if t.lower() == "nan":
        return ""
    return t


def split_multi(v):
    t = safe(v)
    if not t:
        return []
    return [x.strip() for x in t.split("|") if x.strip()]


def parse_date(s):
    t = safe(s)
    if not t:
        return ""
    try:
        return pd.to_datetime(t).strftime("%Y-%m-%d")
    except Exception:
        return t[:10]


def fmt_date_zh(date_str):
    try:
        dt = pd.to_datetime(date_str)
        return f"{dt.year}年{dt.month}月{dt.day}日"
    except Exception:
        return date_str


def one_line(text, n=88):
    t = " ".join(safe(text).split())
    t = re.sub(r"https?://\S+", "", t).strip()
    if len(t) <= n:
        return t
    return t[: n - 1].rstrip() + "…"


def slugify(date_str, idx=0):
    return f"{date_str}-digest-{idx:02d}"


def esc(s):
    return html.escape(str(s), quote=True)


def linkify(text):
    return re.sub(
        r"(https?://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+)",
        r'<a href="\1" target="_blank">\1</a>',
        esc(text),
    )


def card_headline(row):
    t = one_line(row.get("text", ""), n=56)
    if not t:
        t = "今日重点更新"
    return t


def dedup(df):
    def k(row):
        link = safe(row.get("tweet_link", ""))
        if link:
            return "link::" + link
        txt = " ".join(safe(row.get("text", "")).lower().split())
        return f"txt::{safe(row.get('author',''))}::{parse_date(row.get('time',''))}::{txt[:280]}"

    out = df.copy()
    out["_k"] = out.apply(k, axis=1)
    out = out.drop_duplicates(subset=["_k"], keep="first").drop(columns=["_k"])
    return out


def load_feed():
    if not FEED_CSV.exists():
        raise FileNotFoundError(f"missing feed: {FEED_CSV}")
    df = pd.read_csv(FEED_CSV, encoding="utf-8-sig")
    if len(df) == 0:
        raise ValueError("empty feed")
    df = dedup(df)
    df["date"] = df["time"].apply(parse_date)
    df["quality_score"] = pd.to_numeric(df.get("quality_score", 0), errors="coerce").fillna(0).astype(int)
    df = df[df["date"].astype(str).str.len() > 0].copy()
    df = df.sort_values(["date", "quality_score", "time"], ascending=[False, False, False])
    return df


def write_style():
    css = """/* AI Digest Replica V2 */
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: system-ui, -apple-system, "PingFang SC", "Noto Sans SC", "Source Han Sans SC", sans-serif;
  font-size: 1.05rem;
  line-height: 1.8;
  color: #374151;
  background: #fafafa;
  letter-spacing: 0.04em;
}
.container { max-width: 750px; margin: 0 auto; padding: 2rem 1.35rem 2.5rem; }
.site-nav {
  display: flex; align-items: center; justify-content: space-between;
  padding: 1rem 0; margin-bottom: 1rem; border-bottom: 2px solid #1a6b3c;
  font-size: 0.95rem;
}
.nav-title { color: #1a6b3c; font-weight: 700; text-decoration: none; }
.nav-links { list-style: none; display: flex; gap: 1.15rem; align-items: center; }
.nav-links a, .nav-links button {
  color: #6b7280; text-decoration: none; border: 0; background: transparent; cursor: pointer; font-size: 0.95rem;
}
.nav-links a:hover, .nav-links a.active, .nav-links button:hover { color: #111827; }
.page-header { text-align: center; padding: 2.25rem 0 1.4rem; }
.page-subtitle {
  font-family: "Songti SC", "Noto Serif SC", "Source Han Serif SC", Georgia, serif;
  font-size: 1.92rem; font-weight: 800; color: #1a1a1a; margin-bottom: 0.4rem; line-height: 1.45;
}
.page-tagline { font-size: 0.88rem; color: #888; letter-spacing: 0.03em; }
.article-list { list-style: none; display: grid; gap: 12px; }
.article-card {
  background: #fff; border: 1px solid #f0f2f4; border-radius: 6px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.05); overflow: hidden;
}
.card-link { display: block; text-decoration: none; color: inherit; padding: 1.1rem 1.2rem 0.8rem; }
.card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.55rem; }
.card-date { font-size: 0.86rem; color: #9ca3af; font-weight: 600; }
.card-numbered { list-style: none; display: grid; gap: 0.42rem; }
.card-numbered li { display: grid; grid-template-columns: 30px 1fr; gap: 0.5rem; color: #6b7280; line-height: 1.58; font-size: 0.92rem; }
.card-numbered .lead { color: #1f2937; font-weight: 700; font-size: 1.13rem; line-height: 1.62; }
.num {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  color: #c1814f; font-size: 1.08rem; font-weight: 700; letter-spacing: 0;
}
.card-numbered li:not(.lead) .num { color: #d1d5db; font-size: 0.95rem; }
.card-stat {
  display: block; text-align: right; text-decoration: none; padding: 0 1.2rem 0.9rem;
  font-size: 0.75rem; color: #a3a3a3;
}
.card-stat:hover { color: #6b7280; }
.view-all { text-align: center; margin: 1.2rem 0 0.6rem; font-size: 0.88rem; }
.view-all a { color: #9ca3af; text-decoration: none; }
.view-all a:hover { color: #6b7280; }
.article-wrap {
  background: #fff; border: 1px solid #f0f2f4; border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,.05);
  padding: 1.3rem 1.15rem;
}
.article-wrap h1 {
  font-family: "Songti SC", "Noto Serif SC", "Source Han Serif SC", Georgia, serif;
  font-size: 1.55rem; color: #111827; line-height: 1.45; margin-bottom: 0.45rem;
}
.meta { color: #9ca3af; font-size: 0.82rem; margin-bottom: 0.9rem; }
.section { border-top: 1px solid #f0f2f4; padding-top: 0.9rem; margin-top: 0.9rem; }
.section h2 { font-size: 1.22rem; line-height: 1.58; margin-bottom: 0.45rem; color: #1f2937; }
.section p { font-size: 1.05rem; color: #4b5563; line-height: 1.85; margin-bottom: 0.45rem; white-space: pre-wrap; }
.links a { margin-right: 10px; font-size: 0.85rem; color: #2563eb; text-decoration: none; }
.list-plain { list-style: none; display: grid; gap: 10px; }
.list-plain li { background: #fff; border: 1px solid #f0f2f4; border-radius: 6px; padding: 0.75rem; font-size: 0.9rem; line-height: 1.65; }
.footer { margin-top: 1.5rem; text-align: center; color: #b8b8b8; font-size: 0.72rem; }
@media (max-width: 740px) {
  body { font-size: 1rem; }
  .container { padding: 1rem 0.65rem 1.5rem; }
  .site-nav { flex-direction: column; align-items: flex-start; gap: 0.45rem; margin-bottom: 0.8rem; }
  .nav-links { gap: 0.9rem; flex-wrap: wrap; }
  .page-header { padding: 1.3rem 0 0.9rem; }
  .page-subtitle { font-size: 1.42rem; line-height: 1.4; }
  .page-tagline { font-size: 0.82rem; }
  .card-link { padding: 1rem 0.9rem 0.7rem; }
  .card-numbered li { grid-template-columns: 28px 1fr; font-size: 0.9rem; }
  .card-numbered .lead { font-size: 1rem; }
  .num { font-size: 0.95rem; }
  .card-numbered li:not(.lead) .num { font-size: 0.88rem; }
  .card-stat { padding: 0 0.9rem 0.8rem; font-size: 0.72rem; }
  .article-wrap { padding: 1rem 0.9rem; }
  .article-wrap h1 { font-size: 1.2rem; }
  .section h2 { font-size: 1.06rem; }
  .section p { font-size: 0.98rem; }
}
"""
    (OUT_DIR / "style.css").write_text(css, encoding="utf-8")


def render_nav(active="home", prefix=""):
    return f"""
<nav class="site-nav">
  <div class="nav-brand"><a class="nav-title" href="{prefix}index.html">AI资讯速览</a></div>
  <ul class="nav-links">
    <li><a class="{ 'active' if active=='search' else ''}" href="{prefix}search.html">搜索</a></li>
    <li><a class="{ 'active' if active=='method' else ''}" href="{prefix}methodology.html">方法论</a></li>
    <li><a href="{prefix}wechat.html">公众号</a></li>
    <li><a href="{prefix}en/index.html">English</a></li>
  </ul>
</nav>
"""


def shell_page(title, body, active="home", prefix=""):
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>{esc(title)}</title>
  <link rel="stylesheet" href="{prefix}style.css"/>
</head>
<body>
  <div class="container">
    {render_nav(active=active, prefix=prefix)}
    {body}
    <footer class="footer">复刻草案 · AI Digest Clone V2</footer>
  </div>
</body>
</html>"""


def render_index(df, archive=False):
    groups = []
    for date, g in df.groupby("date", sort=False):
        good = g[g["quality_score"] >= 2]
        if len(good) == 0:
            good = g
        top = good.head(3)
        count = len(good)
        slug = slugify(date, 0)
        card = f"""
<li class="article-card">
  <a href="digest/{slug}.html" class="card-link">
    <div class="card-header">
      <span class="card-date">{esc(fmt_date_zh(date))}</span>
    </div>
    <ol class="card-numbered">
      {"".join([f'<li class="lead"><span class="num">01</span>{esc(card_headline(top.iloc[0]))}</li>' if i==0 else f'<li><span class="num">{i+1:02d}</span>{esc(card_headline(top.iloc[i]))}</li>' for i in range(len(top))])}
    </ol>
  </a>
  <a class="card-stat" href="sources/{slug}-sources.html">从 {count} 条资讯中筛选</a>
</li>"""
        groups.append(card)
        if not archive and len(groups) >= 10:
            break

    header = """
<div class="page-header">
  <h1 class="page-subtitle">英文一手信源，如实呈现</h1>
  <p class="page-tagline">不炸裂，不夸张，不接商单</p>
</div>"""
    view_all = (
        '<p class="view-all"><a href="archive.html">查看全部存档 →</a></p>'
        if not archive
        else ""
    )
    body = f"""{header}
<ul class="article-list">
{''.join(groups)}
</ul>
{view_all}"""
    return shell_page("AI资讯速览", body, active="home")


def row_links(row):
    links = []
    if safe(row.get("tweet_link", "")):
        links.append(("推文原文", safe(row.get("tweet_link", ""))))
    for i, u in enumerate(split_multi(row.get("external_links", "")), start=1):
        links.append((f"外部链接{i}", u))
    return links


def render_digest_page(date, day_df):
    good = day_df[day_df["quality_score"] >= 2]
    if len(good) == 0:
        good = day_df
    top = good.head(3)
    items = []
    for i, (_, row) in enumerate(top.iterrows(), start=1):
        links = row_links(row)
        links_html = "".join([f'<a href="{esc(u)}" target="_blank">{esc(n)}</a>' for n, u in links[:4]])
        items.append(
            f"""
<section class="section">
  <h2>{i:02d} {esc(card_headline(row))}</h2>
  <p>{linkify(safe(row.get("text", "")))}</p>
  <div class="links">{links_html}</div>
</section>"""
        )
    body = f"""
<article class="article-wrap">
  <h1>{esc(fmt_date_zh(date))} · AI资讯速览</h1>
  <div class="meta">从 {len(good)} 条资讯中筛选，保留最值得先读的 3 条。</div>
  {''.join(items)}
</article>"""
    return shell_page(f"{fmt_date_zh(date)} - AI资讯速览", body, active="home", prefix="../")


def render_sources_page(date, day_df):
    good = day_df[day_df["quality_score"] >= 2]
    if len(good) == 0:
        good = day_df
    lines = []
    idx = 1
    for _, row in good.iterrows():
        links = row_links(row)
        if not links:
            continue
        for n, u in links:
            lines.append(
                f"<li><strong>#{idx:03d}</strong> {esc(fmt_date_zh(date))} · {esc(safe(row.get('author','')))} · {esc(safe(row.get('category','')))} · {esc(n)}<br/><a href=\"{esc(u)}\" target=\"_blank\">{esc(u)}</a></li>"
            )
            idx += 1
    if not lines:
        lines = ["<li>暂无可追溯外链。</li>"]
    body = f"""
<article class="article-wrap">
  <h1>{esc(fmt_date_zh(date))} · 来源清单</h1>
  <div class="meta">按当日可追溯链接整理。</div>
  <ul class="list-plain">
    {''.join(lines)}
  </ul>
</article>"""
    return shell_page(f"{fmt_date_zh(date)} - 来源", body, active="search", prefix="../")


def render_static_page(title, text, active):
    body = f"""
<article class="article-wrap">
  <h1>{esc(title)}</h1>
  <p>{esc(text)}</p>
</article>"""
    return shell_page(title, body, active=active)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DIGEST_DIR.mkdir(parents=True, exist_ok=True)
    SOURCES_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "en").mkdir(parents=True, exist_ok=True)

    write_style()
    df = load_feed()
    dates = list(df["date"].dropna().drop_duplicates())

    (OUT_DIR / "index.html").write_text(render_index(df, archive=False), encoding="utf-8")
    (OUT_DIR / "archive.html").write_text(render_index(df, archive=True), encoding="utf-8")
    (OUT_DIR / "methodology.html").write_text(
        render_static_page(
            "方法论",
            "优先英文一手信息源；每日筛选高质量事件，按证据链复核后给出三条最值得先读的信号。",
            active="method",
        ),
        encoding="utf-8",
    )
    (OUT_DIR / "search.html").write_text(
        render_static_page(
            "搜索",
            "当前为复刻初版。下一步会加入全文检索和按作者/分类过滤。",
            active="search",
        ),
        encoding="utf-8",
    )
    (OUT_DIR / "wechat.html").write_text(
        render_static_page(
            "公众号",
            "复刻初版暂不接入二维码弹窗。下一步会加入扫码层与订阅入口。",
            active="home",
        ),
        encoding="utf-8",
    )
    (OUT_DIR / "en" / "index.html").write_text(
        shell_page(
            "AI Digest (EN)",
            """
<article class="article-wrap">
  <h1>AI Digest (EN)</h1>
  <p>English page is planned in next iteration.</p>
</article>""",
            active="home",
            prefix="../",
        ),
        encoding="utf-8",
    )

    summary = []
    for date in dates:
        day_df = df[df["date"] == date].copy()
        slug = slugify(date, 0)
        digest_path = DIGEST_DIR / f"{slug}.html"
        source_path = SOURCES_DIR / f"{slug}-sources.html"
        digest_path.write_text(render_digest_page(date, day_df), encoding="utf-8")
        source_path.write_text(render_sources_page(date, day_df), encoding="utf-8")
        summary.append(
            {
                "date": date,
                "digest": digest_path.relative_to(OUT_DIR).as_posix(),
                "sources": source_path.relative_to(OUT_DIR).as_posix(),
                "events": int(len(day_df)),
            }
        )

    (OUT_DIR / "manifest.json").write_text(
        json.dumps({"version": "v2", "days": summary, "count": len(summary)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print((OUT_DIR / "index.html").as_posix())
    print((OUT_DIR / "archive.html").as_posix())
    print((OUT_DIR / "manifest.json").as_posix())


if __name__ == "__main__":
    main()

