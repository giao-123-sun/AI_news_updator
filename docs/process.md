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
