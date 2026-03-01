# AI Insight Pipeline

Daily AI information pipeline for crawling, structuring, and publishing readable web pages.

## Live Website (GitHub Pages)

- Home: `https://giao-123-sun.github.io/AI_news_updator/`
- Stable daily entry: `https://giao-123-sun.github.io/AI_news_updator/reports/daily/index.html`
- Latest dashboard alias: `https://giao-123-sun.github.io/AI_news_updator/reports/daily/latest_dashboard.html`
- Source map page: `https://giao-123-sun.github.io/AI_news_updator/reports/daily/source_map.html`
- Replica digest home: `https://giao-123-sun.github.io/AI_news_updator/reports/daily/replica_digest/index.html`
- Latest dated dashboard (current snapshot):  
  `https://giao-123-sun.github.io/AI_news_updator/reports/daily/subagent_dashboard_2026-03-02.html`

## Repo -> Website Mapping

- `reports/daily/index.html`: stable website index page (always keep this link fixed).
- `reports/daily/subagent_dashboard_YYYY-MM-DD.html`: per-day dashboard.
- `reports/daily/replica_digest/index.html`: digest-style browse page.
- `reports/daily/latest_report.json`: latest aggregated machine-readable data.

## Project Structure

- `x_user_crawler.py`: crawl + classify + base report generation.
- `build_insight_hub_v1.py`: build unified feed + daily brief + compare + hub page.
- `build_longreads_v1.py`: build longread center / facts / history / 3 perspective articles.
- `build_ai_digest_clone.py`: build AI Digest style replica pages.
- `run_daily_pipeline_v1.py`: one-command daily build runner.
- `scripts/build_daily_site_index.py`: generate stable website index (`reports/daily/index.html`).
- `qa_capture_*.py`: screenshot-based visual QA scripts.
- `data/`: source account watchlist and probe outputs.
- `config/`: prompt/model/baseline configs (secret key files are ignored).
- `docs/`: architecture, design, functions, process, and progress records.

## Quick Start

1. Prepare:
- `data/X.txt` with account list.
- `human_comment/cookies.txt` with valid X cookie string.

2. Crawl + classify:
```bash
python x_user_crawler.py
```

3. Build all pages:
```bash
python run_daily_pipeline_v1.py
```
(`run_daily_pipeline_v1.py` now also regenerates `reports/daily/index.html` automatically.)

4. Build stable web entry page:
```bash
python scripts/build_daily_site_index.py
```

5. Visual QA:
```bash
python qa_capture_hub_v1.py
python qa_capture_longreads_v1.py
python qa_capture_ai_digest_clone.py
```

## Environment Overrides (Crawler)

- `X_SINGLE_OUTPUT_FILE`
- `X_PROXY`
- `X_MAX_PAGES`
- `X_PAGE_SLEEP_MIN`, `X_PAGE_SLEEP_MAX`
- `X_USER_SLEEP_MIN`, `X_USER_SLEEP_MAX`

