# Progress

## 2026-02-27

### Completed
- Refactored crawler to read:
  - users from `data/X.txt`
  - cookie from `human_comment/cookies.txt`
- Added:
  - proxy support
  - page/user sleeps
  - per-user exception skip
  - output mode switch (single/per-user)
  - image download for tweets
  - analysis CSV + HTML report

### Capability test (reply/comment)
- Added reusable probe script: `capability_probe.py`.
- Ran probe (`python capability_probe.py --users-limit 10 --no-proxy`) and saved result to `data/capability_test_results.json`.
- Probe summary:
  - Users tested target: 10 (success 9, 1 transient network failure)
  - Reply samples detected: 85
  - Comment samples (direct replies) from `conversation_id` query: 4
  - Parent post inclusion is not guaranteed in first-page conversation query.

### Current status
- Original posts: can crawl.
- Reply posts: can crawl.
- Replied-to parent post: partial (not guaranteed by current query strategy).
- Comments under a post: can crawl partially via `conversation_id:<tweet_id>`.

### Next
- Add dedicated parent-post fetch endpoint (TweetDetail) for deterministic parent retrieval.
- Add multi-page conversation crawl for deeper comment coverage.

## 2026-02-27 (V1 Hub Iteration)

### Completed
- Added V1 strategy and prompt assets:
  - `docs/v1_first_design.md`
  - `docs/prompt_studio_v1.md`
  - `docs/raci_v1.md`
  - `config/prompts_v1.json`
  - `config/idea_baseline_v1.json`
- Implemented deliverable builder:
  - `build_insight_hub_v1.py`
  - outputs: `daily_brief_v1.md`, `post_feed_v1.csv`, `idea_compare_v1.csv`, `hub_v1.html`
- Added QA screenshot runner:
  - `qa_capture_hub_v1.py`

### Fixes after visual QA
- Fixed markdown rendering in Daily + Compare sections.
- Fixed broken image links caused by `nan` values and relative path mismatch.
- Added post pagination (`20 per page + load more`) for mobile stability and browsing performance.

### Docs
- Added execution report: `docs/execution_v1.md`.

## 2026-02-27 (V1 Hub Hotfix)

### Completed
- Compare section switched to table renderer with expandable evidence rows.
- Daily brief added quality filter:
  - `quality_score` / `quality_level` / `quality_reasons`
  - threshold-based filtering for daily and compare
  - evidence gate for key daily items

### Validation
- Rebuilt outputs:
  - `report/daily_brief_v1.md`
  - `report/idea_compare_v1.csv`
  - `report/hub_v1.html`
- Re-ran screenshot QA:
  - `report/qa/hub_v1_compare_desktop.png`
  - `report/qa/hub_v1_compare_mobile.png`

## 2026-02-27 (Dedup + 3 Longreads)

### Completed
- Added dedup concept into feed pipeline (before scoring/export).
- Daily brief now includes:
  - dedup removal count
  - low-signal filtering stats
  - evidence-gated key items
- Added longread pipeline:
  - `build_longreads_v1.py`
  - outputs in `human_comment/3ofthem/`
    - `facts_YYYY-MM-DD.md`
    - `brief_history.md`
    - `YYYY-MM-DD_karpathy_longread.md`
    - `YYYY-MM-DD_amjad_longread.md`
    - `YYYY-MM-DD_elad_longread.md`
    - `reading_room.html`
- Added one-command daily runner:
  - `run_daily_pipeline_v1.py`

### QA
- Reading page screenshots:
  - `human_comment/3ofthem/qa/reading_room_desktop.png`
  - `human_comment/3ofthem/qa/reading_room_mobile.png`

## 2026-02-28 (Integrated Longreads UX + Facts/History Refinement)

### Completed
- Clarified output location:
  - Longreads now stay under `report/longreads/` (not `human_comment`).
- Integrated deep-reading entry into main hub page:
  - `report/hub_v1.html` adds in-site "深度阅读" section with direct links.
  - Removed iframe-based reading dependency for article consumption.
- Rebuilt longread generator (`build_longreads_v1.py`):
  - Three full-page article HTML outputs (Medium-like reading layout).
  - Full-event fact page includes complete event list + search/filter + evidence links.
  - Added event image gallery rendering in fact page.
  - History is now structured and user-facing in HTML:
    - `report/longreads/brief_history.html`
    - `report/longreads/brief_history.json`
  - User-facing pages no longer expose markdown source.
- Updated QA script coverage:
  - `qa_capture_hub_v1.py` now captures longreads tab on desktop/mobile.
  - `qa_capture_longreads_v1.py` now captures index/facts/history/article.

### Output snapshot
- Hub:
  - `report/hub_v1.html`
- Longreads:
  - `report/longreads/index.html`
  - `report/longreads/facts_all_events.html`
  - `report/longreads/brief_history.html`
  - `report/longreads/brief_history.json`
  - `report/longreads/articles/2026-02-28_karpathy.html`
  - `report/longreads/articles/2026-02-28_amjad.html`
  - `report/longreads/articles/2026-02-28_elad.html`
  - `report/longreads/manifest.json`

### QA screenshots
- Hub:
  - `report/qa/hub_v1_longreads_desktop.png`
  - `report/qa/hub_v1_longreads_mobile.png`
- Longreads:
  - `report/qa_longreads/longreads_index_desktop.png`
  - `report/qa_longreads/facts_events_desktop.png`
  - `report/qa_longreads/history_desktop.png`
  - `report/qa_longreads/article_desktop.png`
  - `report/qa_longreads/article_mobile.png`

## 2026-02-28 (Writing Style Prompt Upgrade)

### Completed
- Added writing-style constraints into prompt config:
  - one paragraph = one idea
  - first-person dominant voice
  - explicit transition between paragraphs
  - reduce parallel rhetoric
- Added reusable writing pack:
  - `config/writing_style_pack_v1.json`
  - includes openers / transitions / endings / checklist
- Rebuilt prompt studio docs:
  - `docs/prompt_studio_v1.md`
- Replaced longread generator text logic to align with style:
  - first-person interpretation and action statements
  - transition-led paragraph starts

### Validation
- Re-ran pipeline:
  - `python run_daily_pipeline_v1.py`
- Re-ran longreads QA capture:
  - `python qa_capture_longreads_v1.py`

## 2026-02-28 (Deep Writing Model + Ad Gate)

### Completed
- Deep-writing model switched to:
  - `google/gemini-3.1-pro-preview`
  - config file: `config/deep_writing_model_v1.json`
- Added runtime override support:
  - env `DEEP_WRITING_MODEL`
- Added ad-content gate in longread pipeline:
  - ad-like events are flagged by keyword rules
  - ad events are excluded from deep articles/facts/history
- Manifest now includes deep-writing filtering metrics:
  - `deep_writing_model`
  - `event_count_raw`
  - `event_count_deep`
  - `ad_blocked_count`

### Validation
- Rebuilt pipeline:
  - `python run_daily_pipeline_v1.py`
- Checked manifest:
  - `report/longreads/manifest.json`

## 2026-02-28 (AI Digest Clone Kickoff)

### Completed
- Studied `ai-digest.liziran.com` structure and visual pattern:
  - nav + slogan + daily numbered cards + source count + archive
- Implemented replica generator:
  - `build_ai_digest_clone.py`
  - outputs under `report/ai_digest_clone/`
- Added screenshot QA:
  - `qa_capture_ai_digest_clone.py`
- Integrated build into daily pipeline:
  - `run_daily_pipeline_v1.py` now runs `build_ai_digest_clone.py`
- Added entry link inside hub longreads tab:
  - `report/hub_v1.html` (generated from `build_insight_hub_v1.py`)

### Validation
- Rebuilt pipeline:
  - `python run_daily_pipeline_v1.py`
- Captured clone screenshots:
  - `report/qa_ai_digest_clone/index_desktop.png`
  - `report/qa_ai_digest_clone/archive_desktop.png`
  - `report/qa_ai_digest_clone/index_mobile.png`
  - `report/qa_ai_digest_clone/digest_mobile.png`

## 2026-02-28 (AI Digest Clone V2 Typography Alignment)

### Completed
- Updated `build_ai_digest_clone.py` style profile to V2 while keeping clone IA unchanged.
- Reduced oversized typography on clone homepage:
  - slogan (`page-subtitle`)
  - card lead headline (`.card-numbered .lead`)
  - card index numerals (`.num`)
  - nav/card meta text
- Reworked mobile breakpoints to avoid font-size inflation and align with reference density.
- Added clone version marker:
  - footer: `AI Digest Clone V2`
  - manifest: `"version": "v2"`

### Validation
- Rebuilt clone:
  - `python build_ai_digest_clone.py`
- Re-ran clone QA screenshots:
  - `report/qa_ai_digest_clone/index_desktop.png`
  - `report/qa_ai_digest_clone/archive_desktop.png`
  - `report/qa_ai_digest_clone/index_mobile.png`
  - `report/qa_ai_digest_clone/digest_mobile.png`
- Re-ran full pipeline:
  - `python run_daily_pipeline_v1.py`

## 2026-03-01 (Evidence Chain Repair for Browsing UX)

### Objective
- Improve "information browsing convenience" by restoring clickable evidence links in hub/daily/compare flows.

### Completed
- Updated `build_insight_hub_v1.py`:
  - Added URL extraction from `text` and evidence backfill for:
    - `tweet_link`
    - `external_links`
  - Added fallback evidence rendering in daily brief:
    - use first external link if tweet link is missing.
  - Updated compare evidence payload:
    - include `external_links`.
  - Updated compare UI evidence link rendering:
    - tweet link first, external link fallback.
- Updated `x_user_crawler.py`:
  - analysis input selection now prioritizes aggregate CSVs over per-user CSVs.
  - added text-URL backfill in analysis stage for `推文链接` / `外部链接`.

### Validation
- Rebuilt full pipeline:
  - `python run_daily_pipeline_v1.py`
- Re-ran hub screenshots:
  - `python qa_capture_hub_v1.py`
- Post-feed evidence metrics after fix (`report/post_feed_v1.csv`):
  - `external_links` non-empty: `124` (was `0`)
  - `tweet_link` non-empty: `0` (still missing in source; recovered with external-link fallback)
  - evidence-any (`tweet_link OR external_links`): `124`

## 2026-03-01 (Full Recrawl + Evidence Field Recovery)

### Completed
- Ran full crawl for all users in `data/X.txt` with 5 pages/user:
  - command: `python x_user_crawler.py`
  - generated: `twitter_all_users_v2.csv`
- Updated crawler runtime config:
  - default proxy now env-driven (`X_PROXY`) and disabled by default.
  - page/user sleep and max-page now env-overridable.
- Rebuilt all downstream outputs:
  - `python run_daily_pipeline_v1.py`

### Data recovery results
- Raw crawl (`twitter_all_users_v2.csv`):
  - rows: `1667`
  - `推文链接` non-empty: `1667`
  - `外部链接` non-empty: `152`
  - `图片链接` non-empty: `219`
  - `本地图片` non-empty: `219`
- Hub feed (`report/post_feed_v1.csv`):
  - rows: `210` (after dedup + quality pipeline)
  - `tweet_link` non-empty: `210`
  - `external_links` non-empty: `90`
  - `images_local` non-empty: `45`
  - `images_remote` non-empty: `45`
- Local image asset store:
  - `tweet_images/` files: `186`

### Visual validation
- Hub:
  - `report/qa/hub_v1_daily_desktop.png`
  - `report/qa/hub_v1_posts_desktop.png`
  - `report/qa/hub_v1_compare_desktop.png`
  - `report/qa/hub_v1_longreads_desktop.png`
- Longreads:
  - `report/qa_longreads/longreads_index_desktop.png`
  - `report/qa_longreads/facts_events_desktop.png`
  - `report/qa_longreads/history_desktop.png`
  - `report/qa_longreads/article_desktop.png`
- Digest clone:
  - `report/qa_ai_digest_clone/index_desktop.png`
  - `report/qa_ai_digest_clone/archive_desktop.png`
  - `report/qa_ai_digest_clone/index_mobile.png`
  - `report/qa_ai_digest_clone/digest_mobile.png`

## 2026-03-01 (Learning Mode: Expanded X Watchlist)

### Completed
- Expanded X watchlist in `data/X.txt` from 20 to 35 users.
- Added frontier and product accounts for broader learning coverage:
  - `sama`, `gdb`, `fchollet`, `ylecun`, `demishassabis`, `mustafasuleyman`
  - `emollick`, `ClementDelangue`, `jeremyphoward`, `natolambert`
  - `OpenAI`, `AnthropicAI`, `GoogleDeepMind`, `MistralAI`, `perplexity_ai`
- Ran crawl in learning-mode profile:
  - `X_MAX_PAGES=3`
  - reduced page/user sleep windows for faster collection.
- Rebuilt full outputs:
  - `python run_daily_pipeline_v1.py`

### Validation summary
- Raw incremental learning coverage:
  - new users in watchlist: `15`
  - raw posts from new users: `886` (in `twitter_all_users_v2.csv`)
  - hub-selected posts from new users: `175` (after classification + dedup + quality)
- Current hub feed snapshot (`report/post_feed_v1.csv`):
  - rows: `210`
  - authors: `17`
  - evidence-any (`tweet_link OR external_links`): `210`
- QA rerun:
  - `python qa_capture_hub_v1.py`
  - `report/qa/hub_v1_daily_desktop.png`
  - `report/qa/hub_v1_posts_desktop.png`
  - `report/qa/hub_v1_compare_desktop.png`

## 2026-03-02 (Broad + Precise Rollout)

### Completed
- Expanded watchlist to 55 users in `data/X.txt`.
- Added broad-source batch including:
  - major labs/orgs (`xai`, `Cohere`, `GroqInc`, `huggingface`, `NVIDIAAI`, `allen_ai`, `stanfordnlp`, `DeepLearningAI`)
  - practitioner accounts (`AndrewYNg`, `goodside`, `swyx`, `rasbt`, `hamelhusain`, `yoheinakajima`, `tomgoldsteincs`, `fei_fei_li`, etc.).
- Ran fresh learning crawl to dedicated output file:
  - env `X_SINGLE_OUTPUT_FILE=twitter_learning55`
  - env `X_MAX_PAGES=2`
  - command `python x_user_crawler.py`
- Upgraded precision in `build_insight_hub_v1.py`:
  - daily/compare threshold from `>=2` to `>=3`
  - AI relevance scoring (keywords + domains + trusted authors)
  - hard-drop short reply noise without links/images
  - retained evidence-first link strategy (tweet first, external fallback)

### Validation
- Rebuilt all outputs:
  - `python run_daily_pipeline_v1.py`
- Re-ran QA:
  - `python qa_capture_hub_v1.py`
  - `python qa_capture_longreads_v1.py`
  - `python qa_capture_ai_digest_clone.py`
- Current hub feed snapshot (`report/post_feed_v1.csv`):
  - rows: `363`
  - authors: `46`
  - categories:
    - 工具分享: `233`
    - 使用体验: `45`
    - 新闻/论文: `85`
  - quality `>=3`: `359`
  - evidence-any (`tweet_link OR external_links`): `363`
  - `precision_removed_total`: `72`
  - `dedup_removed_total`: `236`
