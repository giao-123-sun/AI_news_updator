# Architecture

## Current pipeline
1. Input users: `data/X.txt` (URL / @username / username).
   - learning-mode profile can expand watchlist (current snapshot: 35 users).
2. Query build: convert to `from:<username>`.
3. Fetch: X GraphQL `SearchTimeline` (POST), auto-discover query hash from web bundle.
4. Parse: tweet text, engagement, links, image URLs, reply metadata.
5. Save:
- CSV output (`single` or `per_user` mode).
- Download tweet images to `tweet_images/<username>/`.
6. Analyze:
- classify into tools / experience / news-paper.
- export CSVs + HTML dashboard.
- analysis input resolution:
  - prefer aggregate crawl files (`twitter_all_users_merged.csv`, `twitter_all_users*.csv`)
  - fallback to per-user files only when aggregate files are missing
7. Hub build (`build_insight_hub_v1.py`):
- merge 3 category CSVs into `report/post_feed_v1.csv`.
- evidence enrichment:
  - backfill links from post text URL patterns when source link fields are empty
  - keep `tweet_link` as primary evidence and `external_links` as fallback evidence
- precision layer:
  - drop short reply-style noise without links/images
  - score AI relevance (keywords/domains/trusted authors)
  - keep only relevance-qualified rows before dedup/scoring
- dedup before scoring and output.
- quality scoring + daily filtering.
- render `report/hub_v1.html` (daily / posts / compare / longreads entry).
8. Longreads build (`build_longreads_v1.py`):
- read `report/post_feed_v1.csv` and dedup again for safety.
- generate full-event fact page:
  - `report/longreads/facts_all_events.html`
- generate concise history store (structured, non-markdown for users):
  - `report/longreads/brief_history.json`
  - `report/longreads/brief_history.html`
- generate 3 full-page articles (Medium-like reading):
  - `report/longreads/articles/<date>_karpathy.html`
  - `report/longreads/articles/<date>_amjad.html`
  - `report/longreads/articles/<date>_elad.html`
- generate integrated reading entry:
  - `report/longreads/index.html`
  - `report/longreads/manifest.json`
9. Digest clone build (`build_ai_digest_clone.py`):
- read `report/post_feed_v1.csv`
- group by day and rank top items by quality
- generate replica pages:
  - `report/ai_digest_clone/index.html`
  - `report/ai_digest_clone/archive.html`
  - `report/ai_digest_clone/digest/*.html`
  - `report/ai_digest_clone/sources/*-sources.html`
  - `report/ai_digest_clone/style.css`
  - `report/ai_digest_clone/manifest.json`

## Capability probe flow
`capability_probe.py` runs three probes:
1. Original-vs-reply detection on first page of `from:<user>`.
2. Parent retrieval test using `conversation_id:<parent_id>`.
3. Comment retrieval test using `conversation_id:<post_id>`.

Outputs to `data/capability_test_results.json`.

## Known boundaries
- Parent post is not guaranteed in `conversation_id` first page.
- Comment retrieval is partial (search-index based), not a full thread crawler.
- If proxy is down, requests fail; run with `--no-proxy` for direct network test.
- If local clock crosses day boundary, longread article date suffix changes (e.g. `2026-02-27` -> `2026-02-28`).
- If upstream crawl output misses structured link fields, current pipeline can recover URL evidence from post text, but cannot reconstruct missing image metadata.

## Crawl runtime config
- `x_user_crawler.py` supports env overrides:
  - `X_PROXY`
  - `X_MAX_PAGES`
  - `X_PAGE_SLEEP_MIN`, `X_PAGE_SLEEP_MAX`
  - `X_USER_SLEEP_MIN`, `X_USER_SLEEP_MAX`
