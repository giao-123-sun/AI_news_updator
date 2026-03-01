import re
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DAILY_DIR = ROOT / "reports" / "daily"
OUT_HTML = DAILY_DIR / "index.html"


def pick_latest_dashboard(daily_dir: Path) -> str:
    files = sorted(daily_dir.glob("subagent_dashboard_????-??-??.html"))
    if not files:
        return ""
    return files[-1].name


def pick_latest_digest_page(daily_dir: Path) -> str:
    digest_dir = daily_dir / "replica_digest" / "digest"
    files = sorted(digest_dir.glob("*.html"))
    if not files:
        return ""
    source_pages = [f for f in files if f.name.endswith("-sources.html")]
    normal_pages = [f for f in files if not f.name.endswith("-sources.html")]
    if normal_pages:
        return f"replica_digest/digest/{normal_pages[-1].name}"
    if source_pages:
        return f"replica_digest/digest/{source_pages[-1].name}"
    return ""


def file_status(path: Path) -> str:
    return "available" if path.exists() else "missing"


def make_link(label: str, href: str, exists: bool) -> str:
    cls = "ok" if exists else "bad"
    if exists:
        return f'<li><a href="{href}" target="_blank">{label}</a> <span class="{cls}">available</span></li>'
    return f'<li>{label} <span class="{cls}">missing</span></li>'


def build_html() -> str:
    latest_dashboard = pick_latest_dashboard(DAILY_DIR)
    latest_dashboard_rel = latest_dashboard
    replica_home = "replica_digest/index.html"
    latest_digest = pick_latest_digest_page(DAILY_DIR)

    links = [
        ("Daily Dashboard (latest date file)", latest_dashboard_rel),
        ("Replica Digest Home", replica_home),
        ("Replica Latest Digest Page", latest_digest),
        ("Latest Report JSON", "latest_report.json"),
        ("Latest Report JS", "latest_report.js"),
        ("Source Map JSON", "source_map.json"),
    ]

    items = []
    for label, href in links:
        if not href:
            items.append(make_link(label, "", False))
            continue
        exists = (DAILY_DIR / href).exists()
        items.append(make_link(label, href, exists))

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>AI Insight Pipeline - Daily Site Index</title>
  <style>
    :root {{
      --bg:#f5f3ee;
      --card:#ffffff;
      --line:#dfe3ea;
      --text:#0f172a;
      --muted:#64748b;
      --ok:#0f766e;
      --bad:#b91c1c;
      --accent:#0b3b66;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: linear-gradient(180deg, #f8f6f2 0%, #edf1f6 100%);
      color: var(--text);
      font: 16px/1.65 "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
    }}
    .wrap {{ max-width: 900px; margin: 0 auto; padding: 24px 16px 48px; }}
    .card {{
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 14px;
      box-shadow: 0 3px 12px rgba(2, 8, 20, .06);
      padding: 16px 18px;
      margin-bottom: 12px;
    }}
    h1 {{
      margin: 0 0 8px;
      font-family: Georgia, "Times New Roman", serif;
      font-size: 34px;
      line-height: 1.1;
    }}
    h2 {{ margin: 0 0 8px; font-size: 20px; }}
    p {{ margin: 0 0 8px; }}
    ul {{ margin: 8px 0 0 18px; padding: 0; }}
    li {{ margin: 6px 0; }}
    a {{ color: var(--accent); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .ok, .bad {{
      font-size: 12px;
      border: 1px solid;
      border-radius: 999px;
      padding: 1px 8px;
      margin-left: 6px;
    }}
    .ok {{ color: var(--ok); border-color: #99f6e4; background: #ecfeff; }}
    .bad {{ color: var(--bad); border-color: #fecaca; background: #fff1f2; }}
    .muted {{ color: var(--muted); }}
    code {{ background: #f1f5f9; border: 1px solid #e2e8f0; border-radius: 6px; padding: 1px 6px; }}
  </style>
</head>
<body>
  <div class="wrap">
    <section class="card">
      <h1>Daily Site Index</h1>
      <p class="muted">Stable web entry for this repository's generated daily artifacts.</p>
      <p class="muted">Generated at: {generated}</p>
    </section>

    <section class="card">
      <h2>Live Pages</h2>
      <ul>
        {''.join(items)}
      </ul>
    </section>

    <section class="card">
      <h2>Repository Mapping</h2>
      <p><code>reports/daily/index.html</code> is the stable entry point.</p>
      <p><code>reports/daily/subagent_dashboard_YYYY-MM-DD.html</code> is the per-day dashboard.</p>
      <p><code>reports/daily/replica_digest/index.html</code> is the digest-style reading site.</p>
    </section>
  </div>
</body>
</html>
"""
    return html


def main() -> int:
    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(build_html(), encoding="utf-8")
    print(f"[ok] wrote: {OUT_HTML}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

