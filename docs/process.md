# Process (Always-on)

## Standard cycle for each new request
1. Run a capability test first (small sample).
2. Record objective outputs (counts, failures, boundaries).
3. Update docs in the same turn:
   - `docs/architecture.md`
   - `docs/functions.md`
   - `docs/design.md`
   - `docs/progress.md`
4. Then implement or adjust features.
5. Re-run tests and append progress.
6. Keep repository and website synchronized:
   - regenerate stable site entry `reports/daily/index.html`
   - verify GitHub Pages URLs return `200`
   - push code + generated pages in the same commit

## Probe command
```bash
python capability_probe.py --users-limit 10 --no-proxy --output data/capability_test_results.json
```

## Reporting rule
- Always distinguish:
  - validated capabilities
  - partial capabilities
  - unsupported capabilities
- Always include result file paths in the update note.

## Website Sync Checklist
1. Generate pages (`run_daily_pipeline_v1.py` or daily scripts in `scripts/`).
2. Generate stable site index:
```bash
python scripts/build_daily_site_index.py
```
3. Verify local outputs exist:
   - `reports/daily/index.html`
   - `reports/daily/replica_digest/index.html`
   - latest dated dashboard under `reports/daily/subagent_dashboard_YYYY-MM-DD.html`
4. Verify online URLs after push:
   - `https://giao-123-sun.github.io/AI_news_updator/`
   - `https://giao-123-sun.github.io/AI_news_updator/reports/daily/index.html`
