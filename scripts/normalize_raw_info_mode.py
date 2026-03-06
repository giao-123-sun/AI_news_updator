import json
import re
import html as html_lib
from pathlib import Path


DAILY_DIR = Path("reports/daily")
RUNS_DIR = DAILY_DIR / "runs"


def iter_rows(payload: dict) -> list[dict]:
    if isinstance(payload.get("rows"), list):
        return payload["rows"]
    if isinstance(payload.get("records"), list):
        return payload["records"]
    return []


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_json(path: Path, payload) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def collect_layman_mapping() -> dict[str, str]:
    mapping: dict[str, str] = {}
    files = sorted(DAILY_DIR.glob("subagent_report_*.json"))
    files += sorted(RUNS_DIR.glob("subagent_report_*.json")) if RUNS_DIR.exists() else []
    latest = DAILY_DIR / "latest_report.json"
    if latest.exists():
        files.append(latest)

    for path in files:
        payload = load_json(path)
        if not isinstance(payload, dict):
            continue
        for row in iter_rows(payload):
            if not isinstance(row, dict):
                continue
            event = row.get("event_zh")
            layman = row.get("layman_zh")
            if isinstance(event, str) and isinstance(layman, str) and event and layman and event != layman:
                mapping[layman] = event
    return mapping


def normalize_json_file(path: Path) -> int:
    payload = load_json(path)
    if not isinstance(payload, dict):
        return 0

    changed = 0
    for row in iter_rows(payload):
        if not isinstance(row, dict):
            continue
        event = row.get("event_zh")
        layman = row.get("layman_zh")
        if isinstance(event, str) and isinstance(layman, str) and event and layman != event:
            row["layman_zh"] = event
            changed += 1

    if changed:
        save_json(path, payload)
    return changed


def normalize_latest_js(path: Path) -> int:
    if not path.exists():
        return 0
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^(\s*window\.__LATEST_DB__\s*=\s*)(\{.*\})(\s*;\s*)$", text, re.S)
    if not m:
        return 0

    prefix, json_blob, suffix = m.groups()
    try:
        payload = json.loads(json_blob)
    except Exception:
        return 0

    changed = 0
    for row in iter_rows(payload):
        if not isinstance(row, dict):
            continue
        event = row.get("event_zh")
        layman = row.get("layman_zh")
        if isinstance(event, str) and isinstance(layman, str) and event and layman != event:
            row["layman_zh"] = event
            changed += 1

    if changed:
        new_blob = json.dumps(payload, ensure_ascii=False, indent=2)
        path.write_text(f"{prefix}{new_blob}{suffix}", encoding="utf-8")
    return changed


def normalize_markdown(path: Path) -> int:
    if not path.exists():
        return 0
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    changed = False
    current_event = None
    out: list[str] = []
    for line in lines:
        if line.startswith("- 事情:"):
            current_event = line[len("- 事情:") :].strip()
            out.append(line)
            continue
        if line.startswith("- 大白话:") or line.startswith("- 原始信息:"):
            if current_event:
                out.append(f"- 原始信息: {current_event}")
                changed = True
            else:
                out.append(line.replace("- 大白话:", "- 原始信息:"))
                if "- 大白话:" in line:
                    changed = True
            continue
        out.append(line)

    new_text = "\n".join(out)
    if text.endswith("\n"):
        new_text += "\n"

    if changed or new_text != text:
        path.write_text(new_text, encoding="utf-8")
        return 1
    return 0


def normalize_html(path: Path) -> int:
    if not path.exists():
        return 0
    text = path.read_text(encoding="utf-8")
    original = text

    def strip_analogy_in_data_search(block: str, event_text: str | None = None) -> str:
        m_attr = re.search(r'data-search="(.*?)"', block, re.S)
        if not m_attr:
            return block
        raw = m_attr.group(1)
        cleaned = raw

        # Deterministic rewrite for legacy templates:
        # keep source + event + [事件...] tail, dropping layman segment entirely.
        tag_idx = raw.find("[事件]")
        if tag_idx >= 0 and event_text:
            m_source = re.search(r'data-source="(.*?)"', block, re.S)
            source = m_source.group(1) if m_source else ""
            plain_event = html_lib.unescape(re.sub(r"<[^>]+>", "", event_text)).strip()
            tail = raw[tag_idx:]
            rebuilt = " ".join(part for part in [source.strip(), plain_event, tail.strip()] if part)
            cleaned = rebuilt

        patterns = [
            r"打个比方：.*?\[事件\]",
            r"这就像是：.*?\[事件\]",
            r"这就像是.*?\[事件\]",
            r"这就像.*?\[事件\]",
            r"就像是.*?\[事件\]",
            r"就像.*?\[事件\]",
        ]
        for pat in patterns:
            cleaned = re.sub(pat, "[事件]", cleaned, flags=re.S)
        if cleaned != raw:
            block = block[: m_attr.start(1)] + cleaned + block[m_attr.end(1) :]
        return block

    def replace_article(match: re.Match) -> str:
        block = match.group(0)
        m_event = re.search(r'<p class="event">(.*?)</p>', block, re.S)
        m_layman = re.search(r'<p class="layman">(.*?)</p>', block, re.S)
        event_text = m_event.group(1) if m_event else None
        block = strip_analogy_in_data_search(block, event_text=event_text)
        if not m_event or not m_layman:
            return block
        layman_text = m_layman.group(1)
        if layman_text != event_text:
            block = block.replace(layman_text, event_text)
        return block

    text = re.sub(r'<article class="card .*?</article>', replace_article, text, flags=re.S)
    text = text.replace("事情 + 大白话", "事情 + 原始信息")
    text = text.replace("直接看「事情 + 大白话」，让非技术读者快速理解。", "直接看「事情 + 原始信息」，保留原始新闻表达。")
    text = text.replace("大白话", "原始信息")

    if text != original:
        path.write_text(text, encoding="utf-8")
        return 1
    return 0


def main() -> None:
    mapping = collect_layman_mapping()

    json_targets = sorted(DAILY_DIR.glob("subagent_report_*.json"))
    if RUNS_DIR.exists():
        json_targets += sorted(RUNS_DIR.glob("subagent_report_*.json"))
    for extra in (DAILY_DIR / "latest_report.json",):
        if extra.exists():
            json_targets.append(extra)

    json_rows_updated = 0
    json_files_updated = 0
    for path in json_targets:
        changed = normalize_json_file(path)
        if changed:
            json_rows_updated += changed
            json_files_updated += 1

    js_rows_updated = normalize_latest_js(DAILY_DIR / "latest_report.js")

    md_targets = sorted(DAILY_DIR.glob("subagent_report_*.md"))
    html_targets = sorted(DAILY_DIR.glob("subagent_dashboard_*.html"))
    if RUNS_DIR.exists():
        md_targets += sorted(RUNS_DIR.glob("subagent_report_*.md"))
        html_targets += sorted(RUNS_DIR.glob("subagent_dashboard_*.html"))
    if (DAILY_DIR / "replica_digest").exists():
        html_targets += sorted((DAILY_DIR / "replica_digest").rglob("*.html"))

    text_files_updated = 0
    for path in md_targets:
        text_files_updated += normalize_markdown(path)
    for path in html_targets:
        text_files_updated += normalize_html(path)

    print(
        f"normalize_raw_info_mode: mapping={len(mapping)} "
        f"json_files_updated={json_files_updated} json_rows_updated={json_rows_updated} "
        f"latest_js_rows_updated={js_rows_updated} text_files_updated={text_files_updated}"
    )


if __name__ == "__main__":
    main()
