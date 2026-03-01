# AI Insight Pipeline

This repository contains a daily X (Twitter) learning pipeline:
- crawl from watched accounts
- classify and score posts
- generate hub pages, longreads, and digest clone pages
- capture visual QA screenshots

## Project Structure

- `x_user_crawler.py`: crawl + classify + base report generation
- `build_insight_hub_v1.py`: build unified feed + daily brief + compare + hub page
- `build_longreads_v1.py`: build longread center / facts / history / 3 perspective articles
- `build_ai_digest_clone.py`: build AI Digest style replica pages
- `run_daily_pipeline_v1.py`: one-command daily build runner
- `qa_capture_*.py`: screenshot-based visual QA scripts
- `data/`: source account watchlist and probe outputs
- `config/`: prompt/model/baseline configs (secret key file is ignored)
- `docs/`: architecture, design, functions, and progress records

## Quick Start

1. Prepare:
- `data/X.txt` with account list
- `human_comment/cookies.txt` with valid X cookie string

2. Crawl + classify:
```bash
python x_user_crawler.py
```

3. Build all pages:
```bash
python run_daily_pipeline_v1.py
```

4. Visual QA:
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

