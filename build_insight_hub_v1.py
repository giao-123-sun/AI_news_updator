import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

ROOT = Path(".")
REPORT_DIR = ROOT / "report"
CONFIG_DIR = ROOT / "config"

TOOLS_CSV = REPORT_DIR / "tools_share.csv"
EXP_CSV = REPORT_DIR / "experience_share.csv"
NEWS_CSV = REPORT_DIR / "news_papers.csv"
IDEA_FILE = CONFIG_DIR / "idea_baseline_v1.json"

OUT_DAILY_MD = REPORT_DIR / "daily_brief_v1.md"
OUT_FEED_CSV = REPORT_DIR / "post_feed_v1.csv"
OUT_COMPARE_CSV = REPORT_DIR / "idea_compare_v1.csv"
OUT_HTML = REPORT_DIR / "hub_v1.html"

QUALITY_THRESHOLD_DAILY = 3
QUALITY_THRESHOLD_COMPARE = 3

URL_RE = re.compile(r"https?://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+")
X_STATUS_RE = re.compile(r"^https?://(?:www\.)?(?:x|twitter)\.com/[^/]+/status/\d+", re.IGNORECASE)

BAD_SIGNAL_KEYWORDS = [
    "抽奖",
    "互关",
    "关注我",
    "转发抽",
    "粉丝福利",
    "广告",
    "商务合作",
    "求扩散",
    "无脑吹",
    "nfa",
]
GOOD_SIGNAL_KEYWORDS = [
    "实测",
    "复现",
    "教程",
    "workflow",
    "benchmark",
    "对比",
    "开源",
    "github",
    "arxiv",
    "论文",
    "数据",
    "评估",
    "方案",
]

AI_RELEVANCE_KEYWORDS = [
    "ai",
    "llm",
    "model",
    "agent",
    "gpt",
    "claude",
    "gemini",
    "openai",
    "anthropic",
    "deepmind",
    "mistral",
    "perplexity",
    "prompt",
    "token",
    "inference",
    "benchmark",
    "arxiv",
    "paper",
    "fine-tune",
    "sft",
    "rlhf",
    "rag",
    "multi-agent",
    "tool use",
    "vibe coding",
    "mcp",
    "copilot",
    "diffusion",
    "transformer",
    "latency",
    "gpu",
]

AI_RELEVANCE_DOMAINS = {
    "x.com",
    "github.com",
    "huggingface.co",
    "openai.com",
    "anthropic.com",
    "deepmind.google",
    "ai.google",
    "blog.google",
    "mistral.ai",
    "perplexity.ai",
    "arxiv.org",
    "openreview.net",
    "paperswithcode.com",
    "langchain.com",
    "llamaindex.ai",
    "cohere.com",
    "groq.com",
    "nvidia.com",
}

TRUSTED_AI_AUTHORS = {
    "openai",
    "anthropicai",
    "googledeepmind",
    "mistralai",
    "perplexity_ai",
    "sama",
    "gdb",
    "fchollet",
    "ylecun",
    "demishassabis",
    "mustafasuleyman",
    "emollick",
    "clementdelangue",
    "jeremyphoward",
    "natolambert",
    "karpathy",
    "officiallogank",
    "op7418",
    "vista8",
    "dongxi_nlp",
}

HARD_DROP_REPLY_MAX_LEN = 120


def read_csv(path):
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig")


def split_values(value):
    if value is None:
        return []
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return []
    return [x.strip() for x in text.split("|") if x.strip()]


def safe_text(value):
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    text = str(value).strip()
    if text.lower() == "nan":
        return ""
    return text


def normalize_url(url):
    u = safe_text(url)
    if not u:
        return ""
    return u.rstrip(".,;:!?)\"]'")


def uniq_keep_order(items):
    out = []
    seen = set()
    for x in items:
        key = safe_text(x)
        if not key or key in seen:
            continue
        out.append(key)
        seen.add(key)
    return out


def extract_urls_from_text(text):
    if not text:
        return []
    urls = [normalize_url(x) for x in URL_RE.findall(str(text))]
    return uniq_keep_order(urls)


def pick_tweet_link(tweet_link, urls):
    current = normalize_url(tweet_link)
    if current:
        return current
    for u in urls:
        if X_STATUS_RE.match(u):
            return u
    return ""


def merge_external_links(external_links, text_urls, tweet_link):
    merged = []
    merged.extend(split_values(external_links))
    merged.extend(text_urls)
    tw = normalize_url(tweet_link)
    out = []
    for u in uniq_keep_order([normalize_url(x) for x in merged]):
        if tw and u == tw:
            continue
        out.append(u)
    return " | ".join(out)


def enrich_evidence_df(df):
    out = df.copy()
    new_tweet = []
    new_ext = []
    for _, row in out.iterrows():
        text_urls = extract_urls_from_text(row.get("text", ""))
        tw = pick_tweet_link(row.get("tweet_link", ""), text_urls)
        ex = merge_external_links(row.get("external_links", ""), text_urls, tw)
        new_tweet.append(tw)
        new_ext.append(ex)
    out["tweet_link"] = new_tweet
    out["external_links"] = new_ext
    return out


def to_report_relative(path_value):
    p = str(path_value or "").strip().replace("\\", "/")
    if not p:
        return ""
    if p.startswith("http://") or p.startswith("https://"):
        return p
    abs_path = (ROOT / p).resolve()
    if abs_path.exists():
        return os.path.relpath(abs_path, REPORT_DIR.resolve()).replace("\\", "/")
    if p.startswith("report/"):
        return p.replace("report/", "", 1)
    if not p.startswith("../"):
        return "../" + p
    return p


def normalize_time(value):
    if value is None:
        return ""
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return ""
    try:
        return pd.to_datetime(text).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return text


def contains_any_keyword(text, keywords):
    low = text.lower()
    return any(k.lower() in low for k in keywords)


def ai_keyword_hit(text):
    low = safe_text(text).lower()
    return any(k in low for k in AI_RELEVANCE_KEYWORDS)


def ai_domain_hit(links):
    for link in links:
        try:
            host = urlparse(link).netloc.lower().replace("www.", "")
        except Exception:
            host = ""
        if not host:
            continue
        for d in AI_RELEVANCE_DOMAINS:
            if host == d or host.endswith("." + d):
                return True
    return False


def is_low_signal_reply(text, links, images):
    t = safe_text(text)
    return t.startswith("@") and len(t) <= HARD_DROP_REPLY_MAX_LEN and not links and not images


def relevance_score(row):
    text = safe_text(row.get("text", ""))
    links = split_values(row.get("external_links", ""))
    images = split_values(row.get("images_local", "")) + split_values(row.get("images_remote", ""))
    author = safe_text(row.get("author", "")).lower()
    score = 0
    if ai_keyword_hit(text):
        score += 2
    if ai_domain_hit(links):
        score += 2
    if author in TRUSTED_AI_AUTHORS:
        score += 1
    if safe_text(row.get("tweet_link", "")):
        score += 1
    if images:
        score += 1
    return score


def apply_precision_filters(df):
    if len(df) == 0:
        return df, 0
    out = df.copy()
    rel_scores = []
    drop_mask = []
    for _, row in out.iterrows():
        text = safe_text(row.get("text", ""))
        links = split_values(row.get("external_links", ""))
        images = split_values(row.get("images_local", "")) + split_values(row.get("images_remote", ""))
        rel = relevance_score(row)
        rel_scores.append(rel)
        hard_drop = is_low_signal_reply(text, links, images)
        keep = (not hard_drop) and (rel >= 2 or ai_domain_hit(links))
        drop_mask.append(not keep)
    out["relevance_score"] = rel_scores
    before = len(out)
    out = out[[not x for x in drop_mask]].copy()
    removed = before - len(out)
    return out, removed


def dedup_text(text):
    base = safe_text(text).lower()
    base = " ".join(base.split())
    return base[:400]


def dedup_key(row):
    tlink = safe_text(row.get("tweet_link", ""))
    if tlink:
        return f"link::{tlink}"
    return "txt::{author}::{cat}::{time}::{text}".format(
        author=safe_text(row.get("author", "")),
        cat=safe_text(row.get("category", "")),
        time=safe_text(row.get("time", ""))[:10],
        text=dedup_text(row.get("text", "")),
    )


def apply_dedup(df):
    if len(df) == 0:
        return df, 0
    out = df.copy()
    out["dedup_key"] = out.apply(dedup_key, axis=1)
    before = len(out)
    out = out.drop_duplicates(subset=["dedup_key"], keep="first")
    removed = before - len(out)
    out = out.drop(columns=["dedup_key"])
    return out, removed


def signal_quality(row):
    text = safe_text(row.get("text", ""))
    links = split_values(row.get("external_links", ""))
    local_images = split_values(row.get("images_local", ""))
    remote_images = split_values(row.get("images_remote", ""))
    category = safe_text(row.get("category", ""))
    score = 0
    reasons = []

    if category == "工具分享":
        score += 2
        reasons.append("tool_category")
    elif category == "新闻/论文":
        score += 2
        reasons.append("news_paper_category")
    elif category == "使用体验":
        score += 1
        reasons.append("experience_category")

    if links:
        score += 2
        reasons.append("has_links")
    if local_images or remote_images:
        score += 1
        reasons.append("has_images")
    if safe_text(row.get("tweet_link", "")):
        score += 1
        reasons.append("has_tweet_link")
    else:
        score -= 1
        reasons.append("no_tweet_link")

    text_len = len(text)
    if text_len >= 80:
        score += 1
        reasons.append("long_text")
    if text_len >= 180:
        score += 1
        reasons.append("very_long_text")
    if text.startswith("@") and not links:
        score -= 2
        reasons.append("reply_style_no_link")
    if text.count("@") >= 3:
        score -= 1
        reasons.append("too_many_mentions")

    rel = int(row.get("relevance_score", 0) or 0)
    if rel >= 4:
        score += 2
        reasons.append("high_relevance")
    elif rel >= 2:
        score += 1
        reasons.append("relevant")
    else:
        score -= 2
        reasons.append("low_relevance")

    author = safe_text(row.get("author", "")).lower()
    if author in TRUSTED_AI_AUTHORS:
        score += 1
        reasons.append("trusted_source")

    if contains_any_keyword(text, GOOD_SIGNAL_KEYWORDS):
        score += 2
        reasons.append("good_keywords")
    if contains_any_keyword(text, BAD_SIGNAL_KEYWORDS):
        score -= 3
        reasons.append("bad_keywords")

    if score >= 4:
        level = "high"
    elif score >= 2:
        level = "medium"
    else:
        level = "low"

    return score, level, ",".join(reasons)


def build_feed():
    tools_df = read_csv(TOOLS_CSV)
    exp_df = read_csv(EXP_CSV)
    news_df = read_csv(NEWS_CSV)

    rows = []
    for _, r in tools_df.iterrows():
        local_images = [to_report_relative(x) for x in split_values(r.get("本地图片", ""))]
        remote_images = [x for x in split_values(r.get("图片链接", ""))]
        rows.append(
            {
                "category": "工具分享",
                "author": safe_text(r.get("发帖人", "")),
                "time": normalize_time(r.get("时间", "")),
                "text": safe_text(r.get("内容", "")),
                "tweet_link": safe_text(r.get("推文链接", "")),
                "external_links": safe_text(r.get("外部链接", "")),
                "images_local": " | ".join(local_images),
                "images_remote": " | ".join(remote_images),
            }
        )

    for _, r in exp_df.iterrows():
        local_images = [to_report_relative(x) for x in split_values(r.get("本地图片", ""))]
        remote_images = [x for x in split_values(r.get("图片链接", ""))]
        rows.append(
            {
                "category": "使用体验",
                "author": safe_text(r.get("发帖人", "")),
                "time": normalize_time(r.get("时间", "")),
                "text": safe_text(r.get("内容", "")),
                "tweet_link": safe_text(r.get("推文链接", "")),
                "external_links": "",
                "images_local": " | ".join(local_images),
                "images_remote": " | ".join(remote_images),
            }
        )

    for _, r in news_df.iterrows():
        local_images = [to_report_relative(x) for x in split_values(r.get("本地图片", ""))]
        remote_images = [x for x in split_values(r.get("图片链接", ""))]
        n_link = safe_text(r.get("论文/新闻链接", ""))
        ext = n_link if n_link else ""
        rows.append(
            {
                "category": "新闻/论文",
                "author": safe_text(r.get("发帖人", "")),
                "time": normalize_time(r.get("时间", "")),
                "text": safe_text(r.get("推文内容", "")),
                "tweet_link": safe_text(r.get("推文链接", "")),
                "external_links": ext,
                "images_local": " | ".join(local_images),
                "images_remote": " | ".join(remote_images),
            }
        )

    df = pd.DataFrame(rows)
    if len(df) == 0:
        return df

    # Backfill evidence links from text when upstream source omitted link fields.
    df = enrich_evidence_df(df)
    # Precision layer: keep AI-relevant signals and drop low-value reply noise.
    df, precision_removed = apply_precision_filters(df)
    if len(df) == 0:
        return df

    # Stable ordering for browsing
    try:
        df["_sort"] = pd.to_datetime(df["time"], errors="coerce")
        df = df.sort_values("_sort", ascending=False).drop(columns=["_sort"])
    except Exception:
        pass

    df, dedup_removed = apply_dedup(df)
    df["dedup_removed_total"] = dedup_removed
    df["precision_removed_total"] = precision_removed

    score_rows = []
    for _, row in df.iterrows():
        s, lv, rs = signal_quality(row)
        score_rows.append({"quality_score": s, "quality_level": lv, "quality_reasons": rs})
    score_df = pd.DataFrame(score_rows)
    df = pd.concat([df.reset_index(drop=True), score_df], axis=1)
    return df


def extract_domains(feed_df):
    counter = Counter()
    for _, r in feed_df.iterrows():
        links = split_values(r.get("external_links", ""))
        for link in links:
            try:
                host = urlparse(link).netloc.lower().replace("www.", "")
            except Exception:
                host = ""
            if host:
                counter[host] += 1
    return counter


def make_daily_brief(feed_df):
    total = len(feed_df)
    if total == 0:
        return "# 日报 V1\n\n- 无数据"

    good_df = feed_df[feed_df["quality_score"] >= QUALITY_THRESHOLD_DAILY].copy()
    if len(good_df) == 0:
        good_df = feed_df.copy()
    evidence_df = good_df[
        good_df["tweet_link"].astype(str).str.strip().ne("")
        | good_df["external_links"].astype(str).str.strip().ne("")
    ].copy()
    if len(evidence_df) == 0:
        evidence_df = good_df.copy()
    dropped = total - len(good_df)

    by_category = evidence_df["category"].value_counts().to_dict()
    by_author = evidence_df["author"].value_counts().head(8).to_dict()
    domain_counter = extract_domains(evidence_df)

    dedup_removed = int(feed_df["dedup_removed_total"].iloc[0]) if "dedup_removed_total" in feed_df.columns else 0
    precision_removed = int(feed_df["precision_removed_total"].iloc[0]) if "precision_removed_total" in feed_df.columns else 0
    today = datetime.now().strftime("%Y-%m-%d")
    lines = []
    lines.append(f"# 日报 V1 - {today}")
    lines.append("")
    lines.append("## 一览")
    lines.append(f"- 原始帖子数: {total}")
    lines.append(f"- 去重删除条数: {dedup_removed}")
    lines.append(f"- 精度过滤删除条数: {precision_removed}")
    lines.append(f"- 入选高质量帖子: {len(good_df)} (阈值 >= {QUALITY_THRESHOLD_DAILY})")
    lines.append(f"- 可追溯证据帖子: {len(evidence_df)}")
    lines.append(f"- 过滤低信号帖子: {dropped}")
    for k in ["工具分享", "使用体验", "新闻/论文"]:
        lines.append(f"- {k}: {by_category.get(k, 0)}")
    lines.append("")
    lines.append("## 质量分布")
    q_dist = feed_df["quality_level"].value_counts().to_dict()
    lines.append(f"- high: {q_dist.get('high', 0)}")
    lines.append(f"- medium: {q_dist.get('medium', 0)}")
    lines.append(f"- low: {q_dist.get('low', 0)}")
    lines.append("")
    lines.append("## 高频作者 Top")
    for a, c in by_author.items():
        lines.append(f"- {a}: {c}")
    lines.append("")
    lines.append("## 高频外链域名 Top")
    for d, c in domain_counter.most_common(12):
        lines.append(f"- {d}: {c}")
    lines.append("")
    lines.append("## 关键帖子（每类前3，高质量优先）")
    for cat in ["工具分享", "使用体验", "新闻/论文"]:
        lines.append(f"### {cat}")
        subset = evidence_df[evidence_df["category"] == cat].sort_values("quality_score", ascending=False).head(3)
        for _, r in subset.iterrows():
            short = str(r.get("text", "")).replace("\n", " ").strip()[:120]
            tlink = safe_text(r.get("tweet_link", ""))
            if not tlink:
                ext = split_values(r.get("external_links", ""))
                tlink = ext[0] if ext else ""
            lines.append(f"- [Q{r.get('quality_score',0)}] {r.get('author','')} | {short} | {tlink}")
        if len(subset) == 0:
            lines.append("- 无")
    lines.append("")
    return "\n".join(lines)


def load_ideas():
    if not IDEA_FILE.exists():
        return []
    with open(IDEA_FILE, "r", encoding="utf-8") as fp:
        return json.load(fp)


def contains_any(text, keywords):
    low = text.lower()
    return any(str(k).lower() in low for k in keywords)


def run_compare(feed_df, ideas):
    filtered_df = feed_df[feed_df["quality_score"] >= QUALITY_THRESHOLD_COMPARE].copy()
    if len(filtered_df) == 0:
        filtered_df = feed_df.copy()

    records = []
    for idea in ideas:
        name = idea.get("name", "")
        desc = idea.get("description", "")
        s_keys = idea.get("support_keywords", [])
        r_keys = idea.get("risk_keywords", [])

        support = []
        conflict = []
        for _, row in filtered_df.iterrows():
            blob = " ".join(
                [
                    str(row.get("category", "")),
                    str(row.get("text", "")),
                    str(row.get("external_links", "")),
                    str(row.get("author", "")),
                ]
            )
            if contains_any(blob, s_keys):
                support.append(row)
            if contains_any(blob, r_keys):
                conflict.append(row)

        def top_evidence(rows, limit=4):
            out = []
            for r in rows[:limit]:
                out.append(
                    {
                        "author": r.get("author", ""),
                        "category": r.get("category", ""),
                        "tweet_link": r.get("tweet_link", ""),
                        "external_links": r.get("external_links", ""),
                        "text": str(r.get("text", "")).replace("\n", " ")[:100],
                    }
                )
            return out

        score = len(support) - len(conflict)
        records.append(
            {
                "方案": name,
                "描述": desc,
                "参与对比帖子数": int(len(filtered_df)),
                "支持证据数": len(support),
                "冲突证据数": len(conflict),
                "净得分": score,
                "支持证据": json.dumps(top_evidence(support), ensure_ascii=False),
                "冲突证据": json.dumps(top_evidence(conflict), ensure_ascii=False),
            }
        )

    df = pd.DataFrame(records)
    if len(df):
        df = df.sort_values("净得分", ascending=False)
    return df


def render_html(feed_df, compare_df, daily_md):
    metrics = {
        "total": int(len(feed_df)),
        "tools": int((feed_df["category"] == "工具分享").sum()) if len(feed_df) else 0,
        "exp": int((feed_df["category"] == "使用体验").sum()) if len(feed_df) else 0,
        "news": int((feed_df["category"] == "新闻/论文").sum()) if len(feed_df) else 0,
    }

    feed_records = feed_df.head(1000).to_dict(orient="records")
    compare_records = compare_df.to_dict(orient="records")

    payload = {
        "metrics": metrics,
        "daily_md": daily_md,
        "feed": feed_records,
        "compare": compare_records,
    }

    data_json = json.dumps(payload, ensure_ascii=False)
    html_doc = f"""<!doctype html>
<html lang="zh">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>Insight Hub V1</title>
  <style>
    :root {{
      --bg: #f5f6f2;
      --ink: #111311;
      --muted: #4a5249;
      --card: #fffef8;
      --line: #d7dccf;
      --accent: #0c6d5d;
      --accent2: #ea5a3d;
      --accent3: #f1b72b;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      font-family: "Space Grotesk", "Noto Sans SC", "PingFang SC", sans-serif;
      background:
        radial-gradient(circle at 12% 10%, #d7f0eb 0%, transparent 32%),
        radial-gradient(circle at 90% 0%, #ffe0d2 0%, transparent 28%),
        var(--bg);
    }}
    .wrap {{ max-width: 1260px; margin: 0 auto; padding: 18px 14px 40px; }}
    .top {{
      display: grid;
      grid-template-columns: 1.5fr 1fr 1fr 1fr;
      gap: 10px;
      margin-bottom: 12px;
    }}
    .panel {{
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 14px;
      box-shadow: 0 6px 18px rgba(15, 30, 18, 0.08);
    }}
    .hero {{
      background: linear-gradient(140deg, #102a43, #0c6d5d);
      color: #ecfff8;
    }}
    .hero h1 {{ margin: 0 0 8px; font-size: 28px; letter-spacing: 0.3px; }}
    .hero p {{ margin: 0; font-size: 14px; opacity: 0.95; }}
    .kpi .n {{ font-size: 30px; font-weight: 800; line-height: 1; }}
    .kpi .t {{ color: var(--muted); margin-top: 6px; font-size: 13px; }}
    .tabs {{ display: flex; gap: 8px; margin: 12px 0; flex-wrap: wrap; }}
    .tab {{
      border: 1px solid var(--line);
      background: #fff;
      border-radius: 999px;
      padding: 7px 12px;
      font-weight: 700;
      cursor: pointer;
    }}
    .tab.active {{ background: var(--ink); color: white; border-color: var(--ink); }}
    .view {{ display: none; }}
    .view.active {{ display: block; }}
    .lr_shell {{
      background: #fff;
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 12px;
    }}
    .lr_head {{
      background: linear-gradient(140deg, #0f2b42, #0f5f5a);
      color: #ebfff8;
      border-radius: 12px;
      padding: 14px;
      margin-bottom: 10px;
    }}
    .lr_head h2 {{ margin: 0 0 6px; }}
    .lr_head p {{ margin: 0; opacity: 0.95; }}
    .lr_links {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 8px;
      margin-bottom: 10px;
    }}
    .lr_links a {{
      display: block;
      background: #fff;
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 10px;
      text-decoration: none;
      color: #0d56a0;
      font-weight: 700;
    }}
    .lr_grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
      gap: 8px;
    }}
    .lr_card {{
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 10px;
      background: #fcfdfb;
    }}
    .lr_card h3 {{ margin: 0 0 6px; font-size: 18px; }}
    .lr_card p {{ margin: 0 0 8px; color: var(--muted); font-size: 13px; }}
    .lr_card a {{ color: #0f593a; font-weight: 700; text-decoration: none; }}
    .daily {{
      line-height: 1.55;
      font-size: 14px;
      max-height: 70vh;
      overflow: auto;
    }}
    .daily h2, .daily h3, .daily h4 {{
      margin: 8px 0 6px;
      line-height: 1.3;
    }}
    .daily ul {{ margin: 4px 0 8px 20px; padding: 0; }}
    .daily p {{ margin: 4px 0; }}
    .toolbar {{
      display: grid;
      grid-template-columns: 1.2fr 0.7fr 0.7fr;
      gap: 8px;
      margin-bottom: 10px;
    }}
    .toolbar input, .toolbar select {{
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 10px;
      font-size: 14px;
      background: white;
    }}
    .feed_meta {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 10px;
      font-size: 13px;
      color: var(--muted);
    }}
    .feed_meta button {{
      border: 1px solid var(--line);
      background: #fff;
      border-radius: 10px;
      padding: 7px 10px;
      cursor: pointer;
      font-weight: 700;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(315px, 1fr));
      gap: 10px;
    }}
    .post {{
      border: 1px solid var(--line);
      border-radius: 14px;
      background: #fff;
      padding: 10px;
      display: flex;
      flex-direction: column;
      gap: 6px;
      min-height: 180px;
    }}
    .meta {{ color: var(--muted); font-size: 12px; }}
    .tag {{
      display: inline-block;
      border-radius: 6px;
      padding: 2px 6px;
      font-size: 12px;
      font-weight: 700;
      background: #e9f6f3;
      color: #0b5b4f;
      margin-right: 6px;
    }}
    .text {{
      white-space: pre-wrap;
      word-break: break-word;
      line-height: 1.4;
      max-height: 132px;
      overflow: auto;
      font-size: 14px;
    }}
    .links a {{
      margin-right: 8px;
      color: #125ea2;
      text-decoration: none;
      font-size: 13px;
    }}
    .images {{
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 6px;
    }}
    .images img {{
      width: 100%;
      border-radius: 8px;
      border: 1px solid var(--line);
      min-height: 75px;
      object-fit: cover;
      background: #f4f7f4;
    }}
    .cmp_wrap {{
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: 14px;
      background: #fff;
    }}
    table.cmp {{
      width: 100%;
      border-collapse: collapse;
      min-width: 960px;
      font-size: 13px;
    }}
    .cmp th, .cmp td {{
      border-bottom: 1px solid var(--line);
      padding: 10px;
      text-align: left;
      vertical-align: top;
    }}
    .cmp th {{
      position: sticky;
      top: 0;
      background: #eef3ee;
      z-index: 2;
    }}
    .cmp tr:hover td {{
      background: #f9fcf9;
    }}
    .cmp .name {{
      font-weight: 800;
      color: #0f2d48;
    }}
    .score {{
      font-weight: 800;
      font-size: 20px;
      color: #122f4e;
    }}
    .chip {{
      display: inline-block;
      padding: 3px 8px;
      border-radius: 8px;
      font-size: 12px;
      margin-right: 6px;
      font-weight: 700;
    }}
    .ok {{ background: #dff4df; color: #166016; }}
    .bad {{ background: #ffe1da; color: #8f2614; }}
    .evi {{
      font-size: 13px;
      color: var(--muted);
      line-height: 1.35;
      max-height: 220px;
      overflow: auto;
      max-width: 480px;
    }}
    details.ev_box {{
      border: 1px dashed var(--line);
      border-radius: 8px;
      padding: 6px 8px;
      background: #fcfdfb;
      margin-bottom: 8px;
    }}
    details.ev_box summary {{
      cursor: pointer;
      font-weight: 700;
      color: #1b4a3f;
      margin-bottom: 4px;
    }}
    .ev_item {{
      margin-bottom: 4px;
      border-bottom: 1px dotted #e2e8de;
      padding-bottom: 4px;
    }}
    @media (max-width: 900px) {{
      .top {{ grid-template-columns: 1fr; }}
      .toolbar {{ grid-template-columns: 1fr; }}
      .lr_links {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <section class="top">
      <div class="panel hero">
        <h1>Insight Hub V1</h1>
        <p>日报 + 帖子浏览 + 方案对比。目标是让团队在 5 分钟内掌握当天有效情报。</p>
      </div>
      <div class="panel kpi"><div class="n" id="k_total">0</div><div class="t">总帖子</div></div>
      <div class="panel kpi"><div class="n" id="k_tools">0</div><div class="t">工具分享</div></div>
      <div class="panel kpi"><div class="n" id="k_exp">0</div><div class="t">使用体验</div></div>
    </section>
    <section class="panel" style="margin-bottom:12px;">
      <div class="kpi"><div class="n" id="k_news">0</div><div class="t">新闻/论文</div></div>
      <div class="tabs">
        <button class="tab active" data-view="daily">日报</button>
        <button class="tab" data-view="posts">帖子浏览</button>
        <button class="tab" data-view="compare">方案对比</button>
        <button class="tab" data-view="longreads">深度阅读</button>
      </div>
    </section>

    <section id="view_daily" class="view active panel">
      <div class="daily" id="daily_text"></div>
    </section>

    <section id="view_posts" class="view panel">
      <div class="toolbar">
        <input id="search" placeholder="搜索内容/作者/链接关键词..." />
        <select id="cat">
          <option value="">全部分类</option>
          <option>工具分享</option>
          <option>使用体验</option>
          <option>新闻/论文</option>
        </select>
        <select id="author"><option value="">全部作者</option></select>
      </div>
      <div class="feed_meta"><span id="feed_count"></span><button id="more_btn">加载更多</button></div>
      <div id="feed" class="grid"></div>
    </section>

    <section id="view_compare" class="view panel">
      <div class="cmp_wrap"><div id="compare"></div></div>
    </section>

    <section id="view_longreads" class="view panel">
      <div class="lr_shell">
        <header class="lr_head">
          <h2>深度阅读中心</h2>
          <p>和主站在同一入口下展示。阅读文章时直接打开整页，不展示 Markdown 原文。</p>
        </header>
        <div class="lr_links">
          <a href="longreads/index.html" target="_blank">打开：深度阅读中心</a>
          <a href="longreads/facts_all_events.html" target="_blank">打开：全事件事实页</a>
          <a href="ai_digest_clone/index.html" target="_blank">打开：AI Digest 复刻页</a>
        </div>
        <div class="lr_grid">
          <article class="lr_card">
            <h3>Karpathy 视角</h3>
            <p>模型机制、工程可复现、系统边界。</p>
            <a href="longreads/index.html" target="_blank">进入整页阅读</a>
          </article>
          <article class="lr_card">
            <h3>Amjad 视角</h3>
            <p>开发者杠杆、任务闭环、交互成本。</p>
            <a href="longreads/index.html" target="_blank">进入整页阅读</a>
          </article>
          <article class="lr_card">
            <h3>Elad 视角</h3>
            <p>价值捕获、护城河、资本效率。</p>
            <a href="longreads/index.html" target="_blank">进入整页阅读</a>
          </article>
          <article class="lr_card">
            <h3>AI 今日精简历史</h3>
            <p>按日期保存“今天发生了什么”，供每次写长文前回看。</p>
            <a href="longreads/brief_history.html" target="_blank">打开历史页</a>
          </article>
          <article class="lr_card">
            <h3>AI Digest 复刻</h3>
            <p>对标 ai-digest.liziran.com 的首页阅读体验复刻。</p>
            <a href="ai_digest_clone/index.html" target="_blank">进入复刻页</a>
          </article>
        </div>
      </div>
    </section>
  </div>

  <script>
    const payload = {data_json};
    const feed = payload.feed || [];
    const compare = payload.compare || [];

    document.getElementById('k_total').textContent = payload.metrics.total;
    document.getElementById('k_tools').textContent = payload.metrics.tools;
    document.getElementById('k_exp').textContent = payload.metrics.exp;
    document.getElementById('k_news').textContent = payload.metrics.news;
    function esc(s) {{
      return String(s || '').replace(/[&<>"']/g, (m) => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[m]));
    }}
    function inlineMd(raw) {{
      let t = esc(raw);
      t = t.replace(/\\*\\*(.+?)\\*\\*/g, '<strong>$1</strong>');
      t = t.replace(/`([^`]+)`/g, '<code>$1</code>');
      t = t.replace(/\\[([^\\]]+)\\]\\((https?:\\/\\/[^\\s)]+)\\)/g, '<a href="$2" target="_blank">$1</a>');
      t = t.replace(/(^|\\s)(https?:\\/\\/[^\\s<]+)/g, '$1<a href="$2" target="_blank">$2</a>');
      return t;
    }}
    function mdBlock(text) {{
      const lines = String(text || '').split(/\\r?\\n/);
      let html = '';
      let inList = false;
      for (const line of lines) {{
        const s = line.trim();
        if (!s) {{
          if (inList) {{ html += '</ul>'; inList = false; }}
          continue;
        }}
        if (s.startsWith('### ')) {{
          if (inList) {{ html += '</ul>'; inList = false; }}
          html += `<h4>${{inlineMd(s.slice(4))}}</h4>`;
        }} else if (s.startsWith('## ')) {{
          if (inList) {{ html += '</ul>'; inList = false; }}
          html += `<h3>${{inlineMd(s.slice(3))}}</h3>`;
        }} else if (s.startsWith('# ')) {{
          if (inList) {{ html += '</ul>'; inList = false; }}
          html += `<h2>${{inlineMd(s.slice(2))}}</h2>`;
        }} else if (s.startsWith('- ')) {{
          if (!inList) {{ html += '<ul>'; inList = true; }}
          html += `<li>${{inlineMd(s.slice(2))}}</li>`;
        }} else {{
          if (inList) {{ html += '</ul>'; inList = false; }}
          html += `<p>${{inlineMd(s)}}</p>`;
        }}
      }}
      if (inList) html += '</ul>';
      return html;
    }}

    document.getElementById('daily_text').innerHTML = mdBlock(payload.daily_md);

    const tabs = document.querySelectorAll('.tab');
    tabs.forEach(btn => {{
      btn.addEventListener('click', () => {{
        tabs.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
        document.getElementById('view_' + btn.dataset.view).classList.add('active');
      }});
    }});

    const authorSel = document.getElementById('author');
    [...new Set(feed.map(x => x.author).filter(Boolean))].sort().forEach(a => {{
      const op = document.createElement('option');
      op.value = a; op.textContent = a;
      authorSel.appendChild(op);
    }});

    function parseMulti(v) {{
      if (!v) return [];
      return String(v).split('|').map(s => s.trim()).filter(Boolean);
    }}
    let feedLimit = 20;
    function renderFeed(resetLimit=false) {{
      if (resetLimit) feedLimit = 20;
      const q = (document.getElementById('search').value || '').toLowerCase();
      const cat = document.getElementById('cat').value;
      const author = document.getElementById('author').value;
      const root = document.getElementById('feed');
      const info = document.getElementById('feed_count');
      const moreBtn = document.getElementById('more_btn');
      root.innerHTML = '';
      const filtered = feed.filter(r => {{
        const blob = [r.author, r.text, r.external_links, r.tweet_link].join(' ').toLowerCase();
        if (q && !blob.includes(q)) return false;
        if (cat && r.category !== cat) return false;
        if (author && r.author !== author) return false;
        return true;
      }});
      const renderList = filtered.slice(0, feedLimit);
      info.textContent = `显示 ${{renderList.length}} / ${{filtered.length}}`;
      if (filtered.length > renderList.length) {{
        moreBtn.style.display = 'inline-block';
      }} else {{
        moreBtn.style.display = 'none';
      }}
      renderList.forEach(r => {{
        const links = parseMulti(r.external_links);
        const localImgs = parseMulti(r.images_local);
        const remoteImgs = parseMulti(r.images_remote);
        const imgs = localImgs.length ? localImgs : remoteImgs;
        const div = document.createElement('article');
        div.className = 'post';
        div.innerHTML = `
          <div class="meta"><span class="tag">${{esc(r.category)}}</span>${{esc(r.author)}} | ${{esc(r.time)}}</div>
          <div class="text">${{esc(r.text)}}</div>
          <div class="links">
            ${{r.tweet_link ? `<a href="${{esc(r.tweet_link)}}" target="_blank">推文</a>` : ''}}
            ${{links.slice(0,4).map(x => `<a href="${{esc(x)}}" target="_blank">外链</a>`).join(' ')}}
          </div>
          <div class="images">
            ${{imgs.slice(0,4).map(x => `<img src="${{esc(x)}}" alt="img" onerror="this.style.display='none'" />`).join('')}}
          </div>
        `;
        root.appendChild(div);
      }});
    }}

    function parseEvidence(text) {{
      try {{ return JSON.parse(text || '[]'); }} catch {{ return []; }}
    }}
    function evidenceHref(s) {{
      const ex = parseMulti(s && s.external_links);
      if (s && s.tweet_link) return s.tweet_link;
      return ex.length ? ex[0] : '';
    }}
    function renderCompare() {{
      const root = document.getElementById('compare');
      const table = document.createElement('table');
      table.className = 'cmp';
      table.innerHTML = `
        <thead>
          <tr>
            <th>方案</th>
            <th>净得分</th>
            <th>支持/冲突</th>
            <th>参与帖子</th>
            <th>描述</th>
            <th>证据</th>
          </tr>
        </thead>
        <tbody id="cmp_body"></tbody>
      `;
      root.innerHTML = '';
      root.appendChild(table);
      const body = document.getElementById('cmp_body');

      compare.forEach((r, idx) => {{
        const supports = parseEvidence(r['支持证据']);
        const conflicts = parseEvidence(r['冲突证据']);

        const supportHtml = supports.length
          ? supports.map(s => {{
              const href = evidenceHref(s);
              return `<div class="ev_item">${{esc(s.author)}} | ${{esc(s.category)}} | ${{href ? `<a href="${{esc(href)}}" target="_blank">链接</a>` : ''}} | ${{inlineMd(s.text)}}</div>`;
            }}).join('')
          : '<div class="ev_item">无</div>';
        const conflictHtml = conflicts.length
          ? conflicts.map(s => {{
              const href = evidenceHref(s);
              return `<div class="ev_item">${{esc(s.author)}} | ${{esc(s.category)}} | ${{href ? `<a href="${{esc(href)}}" target="_blank">链接</a>` : ''}} | ${{inlineMd(s.text)}}</div>`;
            }}).join('')
          : '<div class="ev_item">无</div>';

        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td>
            <div class="name">${{esc(r['方案'])}}</div>
          </td>
          <td><div class="score">${{esc(r['净得分'])}}</div></td>
          <td>
            <span class="chip ok">支持 ${{esc(r['支持证据数'])}}</span>
            <span class="chip bad">冲突 ${{esc(r['冲突证据数'])}}</span>
          </td>
          <td>${{esc(r['参与对比帖子数'] ?? '')}}</td>
          <td class="evi">${{mdBlock(r['描述'])}}</td>
          <td class="evi">
            <details class="ev_box" ${{idx === 0 ? 'open' : ''}}>
              <summary>支持证据</summary>
              ${{supportHtml}}
            </details>
            <details class="ev_box">
              <summary>冲突证据</summary>
              ${{conflictHtml}}
            </details>
          </td>
        `;
        body.appendChild(tr);
      }});
    }}

    document.getElementById('search').addEventListener('input', () => renderFeed(true));
    document.getElementById('cat').addEventListener('change', () => renderFeed(true));
    document.getElementById('author').addEventListener('change', () => renderFeed(true));
    document.getElementById('more_btn').addEventListener('click', () => {{
      feedLimit += 20;
      renderFeed(false);
    }});

    renderFeed();
    renderCompare();
  </script>
</body>
</html>
"""
    OUT_HTML.write_text(html_doc, encoding="utf-8")


def main():
    if not TOOLS_CSV.exists() and not EXP_CSV.exists() and not NEWS_CSV.exists():
        raise FileNotFoundError("report csv files not found. Run analysis first.")

    feed_df = build_feed()
    if len(feed_df) == 0:
        raise ValueError("No feed rows found in source csv files.")

    feed_df.to_csv(OUT_FEED_CSV, index=False, encoding="utf-8-sig")
    daily_md = make_daily_brief(feed_df)
    OUT_DAILY_MD.write_text(daily_md, encoding="utf-8")

    ideas = load_ideas()
    compare_df = run_compare(feed_df, ideas)
    compare_df.to_csv(OUT_COMPARE_CSV, index=False, encoding="utf-8-sig")

    render_html(feed_df, compare_df, daily_md)

    print(OUT_DAILY_MD.as_posix())
    print(OUT_FEED_CSV.as_posix())
    print(OUT_COMPARE_CSV.as_posix())
    print(OUT_HTML.as_posix())


if __name__ == "__main__":
    main()
