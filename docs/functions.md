# Functions

## Crawl
- Read user list from `data/X.txt`.
- Learning mode supports expanded watchlist (core + exploration accounts).
- Build search query as `from:<username>`.
- Crawl with cursor pagination and per-page/per-user sleep.
- Continue-on-error per user.
- Save merged and per-user CSV outputs.
- Runtime env overrides:
  - `X_SINGLE_OUTPUT_FILE`
  - `X_PROXY`
  - `X_MAX_PAGES`
  - `X_PAGE_SLEEP_MIN`, `X_PAGE_SLEEP_MAX`
  - `X_USER_SLEEP_MIN`, `X_USER_SLEEP_MAX`

## Media
- Extract tweet image URLs from timeline entities.
- Download local copies to `tweet_images/<username>/`.
- Save image fields into analysis outputs:
  - remote image links
  - local image paths

## Categorization outputs
- `report/tools_share.csv`
- `report/experience_share.csv`
- `report/news_papers.csv`
- `report/insights_report.html`

## Hub V1
`build_insight_hub_v1.py`:
- Build unified feed `report/post_feed_v1.csv`.
- Backfill evidence links from post text when source links are empty.
- Apply precision filters before final scoring:
  - hard-drop low-value reply posts (short reply + no links/images)
  - AI relevance scoring by keywords/domains/trusted authors
- Apply dedup before scoring/export.
- Compute `quality_score` / `quality_level`.
- Filter low-signal content for daily and compare.
- Daily/compare quality thresholds are now stricter (`>= 3`).
- Build:
  - `report/daily_brief_v1.md`
  - `report/idea_compare_v1.csv`
  - `report/hub_v1.html`
- Hub views:
  - 日报
  - 帖子浏览（含图片）
  - 方案对比（表格证据展开）
  - 深度阅读入口（同站集成，不用 iframe 阅读正文）
  - 证据链接展示策略：推文链接优先，外链兜底

## Longreads V1
`build_longreads_v1.py`:
- Input: `report/post_feed_v1.csv`.
- Generate full-event fact page (not summary):
  - `report/longreads/facts_all_events.html`
- Persist concise daily facts for later reading:
  - `report/longreads/brief_history.json`
  - `report/longreads/brief_history.md` (internal fallback)
  - `report/longreads/brief_history.html` (user-facing)
- Generate three full-page articles:
  - `report/longreads/articles/<date>_karpathy.html`
  - `report/longreads/articles/<date>_amjad.html`
  - `report/longreads/articles/<date>_elad.html`
- Generate reading hub:
  - `report/longreads/index.html`
  - `report/longreads/manifest.json`
- Facts/History/Article pages render rich HTML, not markdown source.
- Runtime model selector:
  - `config/deep_writing_model_v1.json`
  - default model: `google/gemini-3.1-pro-preview`
  - can override via env `DEEP_WRITING_MODEL`
- Ad filtering before deep writing:
  - ad-like posts are flagged by keyword rules
  - flagged items are excluded from:
    - longread articles
    - longread facts/history datasets
  - summary is written to `report/longreads/manifest.json`:
    - `event_count_raw`
    - `event_count_deep`
    - `ad_blocked_count`

## Prompt assets (writing style)
- `config/prompts_v1.json`
  - global writing constraints and role prompts
- `config/writing_style_pack_v1.json`
  - first-person openers / transitions / endings / paragraph checklist

## Pipeline
- One-command daily runner:
```bash
python run_daily_pipeline_v1.py
```

## Crawl analysis input selection
`x_user_crawler.py`:
- analysis input now prefers aggregate CSVs (`twitter_all_users*`, merged) over per-user files.
- among candidates, selects the file with richer evidence fields first.
- analysis stage backfills `tweet_link` / `external_links` from text URLs when raw fields are empty.

## Full recrawl baseline (2026-03-01)
- Raw crawl file:
  - `twitter_all_users_v2.csv`
- Recovered structured evidence fields:
  - `tweet_link`
  - `external_links`
  - `images_remote`
  - `images_local`

## QA capture
- Hub screenshots:
```bash
python qa_capture_hub_v1.py
```
- Longreads screenshots:
```bash
python qa_capture_longreads_v1.py
```

## AI Digest Clone
- Build script:
```bash
python build_ai_digest_clone.py
```
- Outputs:
  - `report/ai_digest_clone/index.html`
  - `report/ai_digest_clone/archive.html`
  - `report/ai_digest_clone/digest/*.html`
  - `report/ai_digest_clone/sources/*-sources.html`
  - `report/ai_digest_clone/style.css`
  - `report/ai_digest_clone/manifest.json`
- Clone style/version notes:
  - current clone version: `v2`
  - reduced homepage/card typography scale to align with target site
  - mobile typography no longer uses oversized responsive amplification
- QA screenshots:
```bash
python qa_capture_ai_digest_clone.py
```

