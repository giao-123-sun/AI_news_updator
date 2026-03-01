import html
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DAILY_DIR = ROOT / "reports" / "daily"
OUT_HTML = DAILY_DIR / "index.html"
OUT_LATEST_ALIAS = DAILY_DIR / "latest_dashboard.html"
OUT_SOURCE_MAP_HTML = DAILY_DIR / "source_map.html"


def pick_latest_dashboard(daily_dir: Path) -> str:
    files = sorted(daily_dir.glob("subagent_dashboard_????-??-??.html"))
    if not files:
        return ""
    return files[-1].name


def available_dashboard_dates(daily_dir: Path) -> list[str]:
    files = sorted(daily_dir.glob("subagent_dashboard_????-??-??.html"))
    dates = []
    for f in files:
        m = re.match(r"subagent_dashboard_(\d{4}-\d{2}-\d{2})\.html$", f.name)
        if m:
            dates.append(m.group(1))
    return dates


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


def restore_daily_main_from_runs(daily_dir: Path) -> dict[str, int]:
    runs = daily_dir / "runs"
    if not runs.exists():
        return {"days": 0, "files_restored": 0}

    patterns = {
        "subagent_report_json": re.compile(r"^subagent_report_(\d{4}-\d{2}-\d{2})_\d{2}-\d{2}-\d{2}\.json$"),
        "subagent_report_md": re.compile(r"^subagent_report_(\d{4}-\d{2}-\d{2})_\d{2}-\d{2}-\d{2}\.md$"),
        "subagent_dashboard_html": re.compile(
            r"^subagent_dashboard_(\d{4}-\d{2}-\d{2})_\d{2}-\d{2}-\d{2}\.html$"
        ),
        "daily_brief_json": re.compile(r"^daily_brief_(\d{4}-\d{2}-\d{2})_\d{2}-\d{2}-\d{2}\.json$"),
        "daily_brief_md": re.compile(r"^daily_brief_(\d{4}-\d{2}-\d{2})_\d{2}-\d{2}-\d{2}\.md$"),
    }

    picks: dict[tuple[str, str], Path] = {}
    for p in runs.iterdir():
        if not p.is_file():
            continue
        for kind, pat in patterns.items():
            m = pat.match(p.name)
            if not m:
                continue
            day = m.group(1)
            key = (kind, day)
            prev = picks.get(key)
            if prev is None or p.name > prev.name:
                picks[key] = p
            break

    restored = 0
    days = sorted({day for (_, day) in picks.keys()})
    for day in days:
        mapping = [
            ("subagent_report_json", daily_dir / f"subagent_report_{day}.json"),
            ("subagent_report_md", daily_dir / f"subagent_report_{day}.md"),
            ("subagent_dashboard_html", daily_dir / f"subagent_dashboard_{day}.html"),
            ("daily_brief_json", daily_dir / f"daily_brief_{day}.json"),
            ("daily_brief_md", daily_dir / f"daily_brief_{day}.md"),
        ]
        for kind, dst in mapping:
            src = picks.get((kind, day))
            if src is None:
                continue
            if not dst.exists():
                shutil.copy2(src, dst)
                restored += 1
    return {"days": len(days), "files_restored": restored}


def build_latest_dashboard_alias(latest_dashboard: str, dates: list[str]) -> str:
    target = latest_dashboard or ""
    links = "\n".join(
        f'<li><a href="subagent_dashboard_{d}.html" target="_blank">{d}</a></li>'
        for d in sorted(dates, reverse=True)
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Latest Dashboard Alias</title>
  <meta http-equiv="refresh" content="0; url={html.escape(target)}" />
  <style>
    body {{ font: 15px/1.6 "Segoe UI", sans-serif; max-width: 900px; margin: 24px auto; padding: 0 14px; }}
  </style>
</head>
<body>
  <h1>Latest Dashboard</h1>
  <p>Redirecting to: <a href="{html.escape(target)}">{html.escape(target)}</a></p>
  <h2>Archive Dashboards</h2>
  <ul>{links}</ul>
</body>
</html>
"""


def build_source_map_html(daily_dir: Path) -> str:
    map_json = daily_dir / "source_map.json"
    nodes = []
    edges_count = 0
    generated = ""
    if map_json.exists():
        try:
            obj = json.loads(map_json.read_text(encoding="utf-8"))
            nodes = list(obj.get("nodes", []))
            edges_count = len(obj.get("edges", []))
            generated = str((obj.get("meta") or {}).get("generated_at_utc", ""))
        except Exception:
            nodes = []
            edges_count = 0
            generated = ""

    # Sort by post_count desc then recency
    def sort_key(n: dict) -> tuple:
        return (int(n.get("post_count", 0)), -int(n.get("recency_days", 9999)))

    top = sorted(nodes, key=sort_key, reverse=True)[:120]
    rows = []
    for n in top:
        source = html.escape(str(n.get("source", n.get("id", ""))))
        post_count = int(n.get("post_count", 0))
        theme = html.escape(str(n.get("theme", "")))
        horizon = html.escape(str(n.get("horizon_label", n.get("horizon", ""))))
        recency = int(n.get("recency_days", 9999))
        last_date = html.escape(str(n.get("last_date", "")))
        rows.append(
            f"<tr><td>{source}</td><td>{post_count}</td><td>{theme}</td><td>{horizon}</td><td>{recency}</td><td>{last_date}</td></tr>"
        )
    table_rows = "\n".join(rows) or "<tr><td colspan='6'>No source map data</td></tr>"

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Source Map</title>
  <style>
    body {{ margin: 0; font: 15px/1.6 "Segoe UI", "PingFang SC", sans-serif; background: #f5f7fb; color: #0f172a; }}
    .wrap {{ max-width: 1200px; margin: 0 auto; padding: 20px 14px 40px; }}
    .card {{ background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 14px; margin-bottom: 12px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ border: 1px solid #e2e8f0; padding: 8px; text-align: left; vertical-align: top; }}
    th {{ background: #f8fafc; }}
    .muted {{ color: #64748b; }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <h1>Source Map</h1>
      <p class="muted">nodes={len(nodes)}, edges={edges_count}, generated_at={html.escape(generated or 'unknown')}</p>
      <p><a href="source_map.json" target="_blank">Open raw JSON</a></p>
    </div>
    <div class="card">
      <h2>Top Sources</h2>
      <table>
        <thead>
          <tr><th>Source</th><th>Post Count</th><th>Theme</th><th>Horizon</th><th>Recency Days</th><th>Last Date</th></tr>
        </thead>
        <tbody>
          {table_rows}
        </tbody>
      </table>
    </div>
  </div>
</body>
</html>
"""


def build_html() -> str:
    latest_dashboard = pick_latest_dashboard(DAILY_DIR)
    latest_dashboard_rel = latest_dashboard
    replica_home = "replica_digest/index.html"
    latest_digest = pick_latest_digest_page(DAILY_DIR)
    source_map_html = "source_map.html"
    latest_alias_html = "latest_dashboard.html"
    dates = available_dashboard_dates(DAILY_DIR)
    archive_links = "\n".join(
        f'<li><a href="subagent_dashboard_{d}.html" target="_blank">{d}</a></li>'
        for d in sorted(dates, reverse=True)
    ) or "<li>No dated dashboards found</li>"

    links = [
        ("Daily Dashboard Alias (legacy URL)", latest_alias_html),
        ("Daily Dashboard (latest date file)", latest_dashboard_rel),
        ("Replica Digest Home", replica_home),
        ("Replica Latest Digest Page", latest_digest),
        ("Source Map (legacy URL)", source_map_html),
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
      <p><code>reports/daily/latest_dashboard.html</code> is the legacy stable alias.</p>
      <p><code>reports/daily/subagent_dashboard_YYYY-MM-DD.html</code> is the per-day dashboard.</p>
      <p><code>reports/daily/source_map.html</code> is the source-map entry page.</p>
      <p><code>reports/daily/replica_digest/index.html</code> is the digest-style reading site.</p>
    </section>

    <section class="card">
      <h2>Dashboard Archive</h2>
      <ul>{archive_links}</ul>
    </section>
  </div>
</body>
</html>
"""
    return html


def main() -> int:
    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    restore = restore_daily_main_from_runs(DAILY_DIR)
    OUT_HTML.write_text(build_html(), encoding="utf-8")
    latest_dashboard = pick_latest_dashboard(DAILY_DIR)
    dates = available_dashboard_dates(DAILY_DIR)
    OUT_LATEST_ALIAS.write_text(
        build_latest_dashboard_alias(latest_dashboard=latest_dashboard, dates=dates),
        encoding="utf-8",
    )
    OUT_SOURCE_MAP_HTML.write_text(build_source_map_html(DAILY_DIR), encoding="utf-8")
    print(
        f"[ok] restored from runs: days={restore['days']}, files_restored={restore['files_restored']}"
    )
    print(f"[ok] wrote: {OUT_HTML}")
    print(f"[ok] wrote: {OUT_LATEST_ALIAS}")
    print(f"[ok] wrote: {OUT_SOURCE_MAP_HTML}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
