import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(".")
REPORT_DIR = ROOT / "report"
FEED_CSV = REPORT_DIR / "post_feed_v1.csv"
OUT_DIR = REPORT_DIR / "longreads"
ARTICLES_DIR = OUT_DIR / "articles"

HISTORY_JSON = OUT_DIR / "brief_history.json"
HISTORY_MD = OUT_DIR / "brief_history.md"  # internal fallback
HISTORY_HTML = OUT_DIR / "brief_history.html"
INDEX_HTML = OUT_DIR / "index.html"
FACTS_HTML = OUT_DIR / "facts_all_events.html"
MANIFEST_JSON = OUT_DIR / "manifest.json"
MODEL_CONFIG_PATH = ROOT / "config" / "deep_writing_model_v1.json"

DEFAULT_DEEP_MODEL = "google/gemini-3.1-pro-preview"

AD_KEYWORDS = [
    "广告",
    "推广",
    "赞助",
    "商务合作",
    "抽奖",
    "转发抽奖",
    "关注并转发",
    "coupon",
    "sponsor",
    "sponsored",
    "promo",
    "promotion",
    "giveaway",
    "affiliate",
    "ad:",
    "#ad",
]


def safe(v):
    if v is None:
        return ""
    t = str(v).strip()
    if t.lower() == "nan":
        return ""
    return t


def split_multi(v):
    t = safe(v)
    if not t:
        return []
    return [x.strip() for x in t.split("|") if x.strip()]


def html_escape(text):
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def linkify(text):
    esc = html_escape(text)
    pattern = r"(https?://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+)"
    return re.sub(pattern, r'<a href="\1" target="_blank">\1</a>', esc)


def load_deep_model():
    model = os.environ.get("DEEP_WRITING_MODEL", "").strip()
    if model:
        return model
    if MODEL_CONFIG_PATH.exists():
        try:
            obj = json.loads(MODEL_CONFIG_PATH.read_text(encoding="utf-8"))
            m = str(obj.get("model", "")).strip()
            if m:
                return m
        except Exception:
            pass
    return DEFAULT_DEEP_MODEL


def ad_reasons_from_text(text):
    low = safe(text).lower()
    hits = []
    for kw in AD_KEYWORDS:
        if kw.lower() in low:
            hits.append(kw)
    return hits


def detect_ad(event):
    text = safe(event.get("text", ""))
    refs = " ".join(event.get("external_links", []))
    blob = f"{text} {refs}"
    hits = ad_reasons_from_text(blob)
    # High-confidence ad if explicit keyword appears.
    if hits:
        return True, ",".join(sorted(set(hits)))
    return False, ""


def to_int(v, default=0):
    t = safe(v)
    if not t:
        return default
    try:
        return int(float(t))
    except Exception:
        return default


def normalize_time(v):
    t = safe(v)
    if not t:
        return ""
    try:
        return pd.to_datetime(t).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return t


def read_feed(path):
    if not path.exists():
        raise FileNotFoundError(f"feed not found: {path}")
    df = pd.read_csv(path, encoding="utf-8-sig")
    if len(df) == 0:
        raise ValueError("feed is empty")
    return df


def dedup(df):
    def key(row):
        link = safe(row.get("tweet_link", ""))
        if link:
            return "link::" + link
        base = " ".join(safe(row.get("text", "")).lower().split())
        return (
            f"txt::{safe(row.get('author',''))}::{safe(row.get('category',''))}::"
            f"{safe(row.get('time',''))[:10]}::{base[:320]}"
        )

    out = df.copy()
    out["_k"] = out.apply(key, axis=1)
    out = out.drop_duplicates(subset=["_k"], keep="first").drop(columns=["_k"])
    return out


def to_events(df):
    rows = []
    for _, r in df.iterrows():
        event = {
            "category": safe(r.get("category", "")),
            "author": safe(r.get("author", "")),
            "time": normalize_time(r.get("time", "")),
            "text": safe(r.get("text", "")),
            "tweet_link": safe(r.get("tweet_link", "")),
            "external_links": split_multi(r.get("external_links", "")),
            "images_local": split_multi(r.get("images_local", "")),
            "images_remote": split_multi(r.get("images_remote", "")),
            "quality_score": to_int(r.get("quality_score", 0), 0),
        }
        is_ad, reason = detect_ad(event)
        event["is_ad"] = is_ad
        event["ad_reason"] = reason
        rows.append(event)
    rows.sort(key=lambda x: (x["quality_score"], x["time"]), reverse=True)
    return rows


def event_ref(event):
    if event["tweet_link"]:
        return event["tweet_link"]
    if event["external_links"]:
        return event["external_links"][0]
    return ""


def rebase_report_path(path_value, page_dir):
    p = safe(path_value)
    if not p:
        return ""
    if p.startswith("http://") or p.startswith("https://"):
        return p
    abs_path = (REPORT_DIR / p).resolve()
    return os.path.relpath(abs_path, page_dir.resolve()).replace("\\", "/")


def build_concise_entries(events, topn=16):
    out = []
    for e in events[:topn]:
        out.append(
            {
                "category": e["category"],
                "author": e["author"],
                "quality_score": e["quality_score"],
                "time": e["time"],
                "text": " ".join(e["text"].split())[:180],
                "ref": event_ref(e),
            }
        )
    return out


def render_history_markdown(records):
    lines = ["# AI 今日精简信息历史", ""]
    for rec in records:
        lines.append(f"## {rec.get('date','')}")
        lines.append(f"- 事件总数：{rec.get('event_count', 0)}")
        for item in rec.get("concise", []):
            ref = f" | {item['ref']}" if item.get("ref") else ""
            lines.append(
                f"- [{item.get('category','')}][Q{item.get('quality_score',0)}] "
                f"{item.get('author','')}: {item.get('text','')}{ref}"
            )
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def load_history_records():
    if not HISTORY_JSON.exists():
        return []
    try:
        data = json.loads(HISTORY_JSON.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []


def upsert_history(date_str, concise_entries, event_count):
    records = load_history_records()
    records = [r for r in records if safe(r.get("date", "")) != date_str]
    records.append(
        {
            "date": date_str,
            "event_count": int(event_count),
            "concise": concise_entries,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    )
    records = sorted(records, key=lambda x: safe(x.get("date", "")))
    HISTORY_JSON.write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    HISTORY_MD.write_text(render_history_markdown(records), encoding="utf-8")
    return records


def history_excerpt(records, date_str, limit_days=4):
    older = [r for r in records if safe(r.get("date", "")) < date_str]
    return older[-limit_days:]


def category_color(category):
    if category == "工具分享":
        return ("#e7f4ee", "#115a49")
    if category == "使用体验":
        return ("#e9eefb", "#1e4f91")
    return ("#f9efe2", "#8b4a12")


def media_gallery(event, page_dir, max_images=4):
    imgs = []
    for p in event["images_local"]:
        src = rebase_report_path(p, page_dir)
        if src:
            imgs.append(src)
    for p in event["images_remote"]:
        p = safe(p)
        if p:
            imgs.append(p)
    imgs = imgs[:max_images]
    if not imgs:
        return ""
    nodes = []
    for src in imgs:
        nodes.append(
            '<img src="{src}" loading="lazy" alt="event-image" onerror="this.style.display=\'none\'"/>'.format(
                src=html_escape(src)
            )
        )
    return "<div class='img_grid'>{}</div>".format("".join(nodes))


def source_links(event):
    links = []
    if event["tweet_link"]:
        links.append(("推文原文", event["tweet_link"]))
    for idx, x in enumerate(event["external_links"], start=1):
        links.append((f"外部链接{idx}", x))
    if not links:
        return ""
    nodes = []
    for label, url in links[:4]:
        nodes.append(
            '<a href="{url}" target="_blank">{label}</a>'.format(
                url=html_escape(url), label=html_escape(label)
            )
        )
    return "<div class='src_links'>{}</div>".format("".join(nodes))


def role_events(events, role):
    out = []
    for e in events:
        c = e["category"]
        t = e["text"].lower()
        if role == "karpathy":
            if c in {"工具分享", "新闻/论文"} or any(
                k in t for k in ["paper", "benchmark", "模型", "推理", "agent", "论文"]
            ):
                out.append(e)
        elif role == "amjad":
            if c in {"工具分享", "使用体验"} or any(
                k in t for k in ["workflow", "体验", "交互", "效率", "skill"]
            ):
                out.append(e)
        elif role == "elad":
            if c in {"工具分享", "新闻/论文"} or any(
                k in t for k in ["market", "增长", "融资", "成本", "商业", "收入"]
            ):
                out.append(e)
    return out[:8] if out else events[:8]


def role_paragraph(role, idx, event):
    transitions = [
        "先说我看到的事实：",
        "接下来我解释这个事实：",
        "再往下，我把判断落到执行：",
        "换个角度，我补一个风险点：",
        "回到目标，我给出优先动作：",
    ]
    lead = transitions[(idx - 1) % len(transitions)]
    short = " ".join(event["text"].split())[:180]
    ref = event_ref(event)
    who = safe(event.get("author", "unknown"))
    cat = safe(event.get("category", "未分类"))

    if role == "karpathy":
        insight = "我更在意它能否稳定复现，而不是叙事是否新。"
        action = "我会先做小规模复现实验，再决定是否扩大投入。"
    elif role == "amjad":
        insight = "我优先看任务链路是否变短，以及失败后是否容易恢复。"
        action = "我会放进真实工作流压测完成率和返工率。"
    else:
        insight = "我会先判断价值能不能沉淀成长期防御力。"
        action = "我会把短期热度和长期价值拆开评估，再给出建议。"

    text = f"{lead}我观察到 {who} 在“{cat}”里提到：{short}。{insight}{action}"
    if ref:
        text += f" 证据链接：{ref}"
    return text


def build_rule_analysis_html(cfg, events):
    paragraphs = [
        f"<p>{linkify(role_paragraph(cfg['role'], i, e))}</p>"
        for i, e in enumerate(events, start=1)
    ]
    if not paragraphs:
        paragraphs = ["<p>今天进入深度写作的非广告信号不足，我先不做结论，等待更多有效证据。</p>"]
    return "".join(paragraphs)


def build_model_analysis_html(cfg, events, history_records, deep_model):
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        return None
    if not events:
        return None

    samples = []
    for e in events[:8]:
        samples.append(
            {
                "category": e.get("category", ""),
                "author": e.get("author", ""),
                "text": e.get("text", "")[:240],
                "ref": event_ref(e),
                "quality_score": e.get("quality_score", 0),
            }
        )
    history_samples = []
    for rec in history_records[-3:]:
        history_samples.append(
            {
                "date": rec.get("date", ""),
                "event_count": rec.get("event_count", 0),
                "concise": rec.get("concise", [])[:3],
            }
        )

    system_prompt = (
        "你是资深分析作者。写作必须：第一人称、段落单意、段间有过渡、少排比、每段尽量给证据链接。"
    )
    user_prompt = (
        f"角色:{cfg.get('role','')}\n"
        f"标题:{cfg.get('title','')}\n"
        "请写 8-10 段“深度解读”正文。"
        "每段 2-4 句，中文输出，直接给正文，不要列表。\n"
        f"事件样本:\n{json.dumps(samples, ensure_ascii=False)}\n"
        f"历史样本:\n{json.dumps(history_samples, ensure_ascii=False)}\n"
    )

    payload = {
        "model": deep_model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
        data = json.loads(body)
        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )
        if not content:
            return None
        parts = [p.strip() for p in re.split(r"\n\s*\n", content) if p.strip()]
        if not parts:
            parts = [content]
        return "".join([f"<p>{linkify(p)}</p>" for p in parts])
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError):
        return None


def article_evidence_list(events):
    rows = []
    for e in events:
        bg, fg = category_color(e["category"])
        ref = event_ref(e)
        rows.append(
            """
            <li>
              <span class="badge" style="background:{bg};color:{fg};">{cat}</span>
              <strong>Q{q}</strong> {author}：{text}
              {ref}
            </li>
            """.format(
                bg=bg,
                fg=fg,
                cat=html_escape(e["category"]),
                q=e["quality_score"],
                author=html_escape(e["author"]),
                text=linkify(" ".join(e["text"].split())[:140]),
                ref=(
                    f' <a href="{html_escape(ref)}" target="_blank">查看证据</a>'
                    if ref
                    else ""
                ),
            )
        )
    return "".join(rows)


def article_history_html(history_records):
    if not history_records:
        return "<p class='muted'>暂无历史记录。</p>"
    blocks = []
    for rec in history_records:
        items = []
        for x in rec.get("concise", [])[:3]:
            ref = (
                f' <a href="{html_escape(x["ref"])}" target="_blank">来源</a>'
                if x.get("ref")
                else ""
            )
            items.append(
                "<li><strong>{cat}</strong> Q{q} {author}：{text}{ref}</li>".format(
                    cat=html_escape(x.get("category", "")),
                    q=to_int(x.get("quality_score", 0)),
                    author=html_escape(x.get("author", "")),
                    text=linkify(x.get("text", "")),
                    ref=ref,
                )
            )
        blocks.append(
            """
            <section class="history_day">
              <h3>{date}</h3>
              <div class="muted">当日事件数：{count}</div>
              <ul>{items}</ul>
            </section>
            """.format(
                date=html_escape(rec.get("date", "")),
                count=to_int(rec.get("event_count", 0)),
                items="".join(items),
            )
        )
    return "".join(blocks)


def medium_article_html(date_str, cfg, events, history_records, analysis_html):
    return """<!doctype html>
<html lang="zh">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>{title}</title>
  <style>
    :root {{
      --bg:#f5f4f1; --ink:#1f2429; --muted:#5f6670; --line:#e2e4df; --brand:{brand};
    }}
    * {{ box-sizing:border-box; }}
    body {{
      margin:0;
      background: radial-gradient(circle at 5% 0%, #d9eee8 0, transparent 24%),
                  radial-gradient(circle at 95% 5%, #f6e8dd 0, transparent 25%),
                  var(--bg);
      color:var(--ink);
      font-family: Charter, "Noto Serif SC", Georgia, serif;
    }}
    .hero {{ background:linear-gradient(135deg,#0f2c42,var(--brand)); color:#f1fff9; padding:52px 20px 44px; text-align:center; }}
    .hero h1 {{ margin:0; font-size:52px; line-height:1.15; }}
    .hero p {{ margin:16px auto 0; max-width:760px; font-size:24px; opacity:.95; }}
    .meta {{ margin-top:18px; font-size:15px; opacity:.85; font-family:"Noto Sans SC",system-ui,sans-serif; }}
    .post {{ max-width:780px; margin:20px auto 54px; background:#fff; border:1px solid var(--line); border-radius:14px; box-shadow:0 14px 30px rgba(22,30,20,.08); padding:34px 30px 38px; }}
    h2 {{ margin:30px 0 12px; font-size:30px; line-height:1.25; }}
    h3 {{ margin:16px 0 8px; font-size:22px; }}
    p {{ margin:12px 0; font-size:22px; line-height:1.9; }}
    ul {{ margin:8px 0 0 24px; padding:0; }}
    li {{ margin:10px 0; font-size:20px; line-height:1.8; }}
    a {{ color:#115db0; text-decoration:none; }}
    .muted {{ color:var(--muted); font-size:14px; font-family:"Noto Sans SC",system-ui,sans-serif; }}
    .note {{ background:#f7fbf8; border:1px solid #deebe2; border-radius:10px; padding:12px 14px; font-family:"Noto Sans SC",system-ui,sans-serif; line-height:1.65; }}
    .badge {{ display:inline-block; border-radius:999px; padding:2px 9px; font-size:13px; margin-right:6px; font-family:"Noto Sans SC",system-ui,sans-serif; font-weight:700; }}
    .history_day {{ border-top:1px solid var(--line); padding-top:12px; margin-top:12px; }}
    @media (max-width:860px) {{
      .hero h1 {{ font-size:40px; }}
      .hero p {{ font-size:22px; }}
      .post {{ margin:0 auto 40px; border-radius:0; border-left:0; border-right:0; padding:24px 16px 30px; }}
      h2 {{ font-size:32px; }}
      p, li {{ font-size:20px; line-height:1.75; }}
      .muted, .meta {{ font-size:14px; }}
    }}
  </style>
</head>
<body>
  <header class="hero">
    <h1>{title}</h1>
    <p>{subtitle}</p>
    <div class="meta">{date} · 面向业务决策的一体化深度阅读</div>
  </header>
  <article class="post">
    <div class="note">{opening}</div>
    <h2>分析框架</h2>
    <ul>{framework}</ul>
    <h2>今日关键事件（证据优先）</h2>
    <ul>{evidence}</ul>
    <h2>深度解读</h2>
    {analysis}
    <h2>历史精简信息回看</h2>
    {history}
    <h2>建议动作</h2>
    <ul>{actions}</ul>
  </article>
</body>
</html>""".format(
        title=html_escape(cfg["title"]),
        subtitle=html_escape(cfg["subtitle"]),
        date=html_escape(date_str),
        brand=cfg["brand"],
        opening=html_escape(cfg["opening"]),
        framework="".join([f"<li>{html_escape(x)}</li>" for x in cfg["framework"]]),
        evidence=article_evidence_list(events),
        analysis=analysis_html,
        history=article_history_html(history_records),
        actions="".join([f"<li>{html_escape(x)}</li>" for x in cfg["actions"]]),
    )


def write_article(date_str, cfg, events, history_records, analysis_html):
    ARTICLES_DIR.mkdir(parents=True, exist_ok=True)
    html_doc = medium_article_html(date_str, cfg, events, history_records, analysis_html)
    out = ARTICLES_DIR / f"{date_str}_{cfg['role']}.html"
    out.write_text(html_doc, encoding="utf-8")
    return out


def facts_event_card(event, idx):
    bg, fg = category_color(event["category"])
    return """
    <article class="item" data-cat="{cat}" data-author="{author}">
      <div class="meta">
        <span class="idx">#{idx}</span>
        <span>{time}</span>
        <span class="tag" style="background:{bg};color:{fg};">{cat}</span>
        <span>Q{q}</span>
        <span>{author}</span>
      </div>
      <div class="text">{text}</div>
      {media}
      {links}
    </article>
    """.format(
        idx=idx,
        time=html_escape(event["time"]),
        bg=bg,
        fg=fg,
        cat=html_escape(event["category"]),
        q=event["quality_score"],
        author=html_escape(event["author"]),
        text=linkify(event["text"]),
        media=media_gallery(event, OUT_DIR, max_images=6),
        links=source_links(event),
    )


def build_facts_events_html(date_str, events):
    cards = [facts_event_card(e, idx) for idx, e in enumerate(events, start=1)]
    html_doc = """<!doctype html>
<html lang="zh">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>全事件事实页 {date}</title>
  <style>
    body {{ margin:0; background:#f4f6f2; color:#1f2630; font-family:"Noto Sans SC",system-ui,sans-serif; }}
    .wrap {{ max-width:1120px; margin:0 auto; padding:18px 14px 34px; }}
    .hero {{ background:linear-gradient(140deg,#12324a,#12534b); color:#effff8; border-radius:16px; padding:18px; }}
    .hero h1 {{ margin:0 0 8px; font-size:40px; }}
    .hero p {{ margin:0; opacity:.96; font-size:20px; }}
    .bar {{ display:grid; grid-template-columns:1fr 180px 180px; gap:8px; margin:12px 0; }}
    .bar input,.bar select {{ border:1px solid #d4ddd3; border-radius:10px; padding:10px; font-size:14px; background:#fff; }}
    .list {{ display:grid; gap:9px; }}
    .item {{ background:#fff; border:1px solid #dae2d8; border-radius:12px; padding:11px 12px; }}
    .meta {{ display:flex; flex-wrap:wrap; gap:8px; color:#596372; font-size:12px; margin-bottom:6px; }}
    .idx {{ font-weight:700; color:#425162; }}
    .tag {{ border-radius:8px; padding:2px 7px; font-weight:700; }}
    .text {{ white-space:pre-wrap; line-height:1.55; font-size:15px; }}
    .src_links {{ margin-top:8px; display:flex; flex-wrap:wrap; gap:8px; }}
    .src_links a {{ color:#145db0; text-decoration:none; font-size:13px; font-weight:700; }}
    .img_grid {{ margin-top:8px; display:grid; grid-template-columns:repeat(auto-fill,minmax(140px,1fr)); gap:8px; }}
    .img_grid img {{ width:100%; height:120px; object-fit:cover; border:1px solid #d9e3d8; border-radius:8px; background:#f4f7f4; }}
    @media (max-width:900px) {{ .bar {{ grid-template-columns:1fr; }} }}
  </style>
</head>
<body>
  <main class="wrap">
    <header class="hero">
      <h1>基本事实提取（全事件）</h1>
      <p>日期：{date}，事件总数：{count}。这里是完整事件清单，不是摘要。</p>
    </header>
    <section class="bar">
      <input id="q" placeholder="搜索事件文本/作者..."/>
      <select id="cat"><option value="">全部分类</option><option>工具分享</option><option>使用体验</option><option>新闻/论文</option></select>
      <select id="author"><option value="">全部作者</option></select>
    </section>
    <section id="list" class="list">{cards}</section>
  </main>
  <script>
    const items=[...document.querySelectorAll('.item')];
    const authorSel=document.getElementById('author');
    [...new Set(items.map(i=>i.dataset.author).filter(Boolean))].sort().forEach(a=>{{
      const op=document.createElement('option'); op.value=a; op.textContent=a; authorSel.appendChild(op);
    }});
    function apply(){{
      const q=(document.getElementById('q').value||'').toLowerCase();
      const c=document.getElementById('cat').value;
      const a=document.getElementById('author').value;
      items.forEach(it=>{{
        const txt=it.innerText.toLowerCase();
        const okQ=!q||txt.includes(q);
        const okC=!c||it.dataset.cat===c;
        const okA=!a||it.dataset.author===a;
        it.style.display=(okQ&&okC&&okA)?'block':'none';
      }});
    }}
    document.getElementById('q').addEventListener('input',apply);
    document.getElementById('cat').addEventListener('change',apply);
    document.getElementById('author').addEventListener('change',apply);
  </script>
</body>
</html>""".format(date=html_escape(date_str), count=len(events), cards="".join(cards))
    FACTS_HTML.write_text(html_doc, encoding="utf-8")


def history_day_card(rec):
    items = []
    for x in rec.get("concise", []):
        ref = (
            f' <a href="{html_escape(x["ref"])}" target="_blank">证据</a>'
            if x.get("ref")
            else ""
        )
        items.append(
            "<li><span class='cat'>{cat}</span> <strong>Q{q}</strong> {author}：{text}{ref}</li>".format(
                cat=html_escape(x.get("category", "")),
                q=to_int(x.get("quality_score", 0)),
                author=html_escape(x.get("author", "")),
                text=linkify(x.get("text", "")),
                ref=ref,
            )
        )
    return """
    <section class="day">
      <h2>{date}</h2>
      <div class="muted">事件总数：{count} · 更新时间：{updated}</div>
      <ul>{items}</ul>
    </section>
    """.format(
        date=html_escape(rec.get("date", "")),
        count=to_int(rec.get("event_count", 0)),
        updated=html_escape(rec.get("updated_at", "")),
        items="".join(items),
    )


def build_history_html(records):
    day_cards = [history_day_card(rec) for rec in reversed(records)]
    html_doc = """<!doctype html>
<html lang="zh">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>AI 今日精简历史</title>
  <style>
    body {{ margin:0; background:#f6f8f4; color:#212a33; font-family:"Noto Sans SC",system-ui,sans-serif; }}
    .wrap {{ max-width:980px; margin:0 auto; padding:16px 14px 36px; }}
    .hero {{ background:linear-gradient(140deg,#13324a,#14534c); color:#ecfff8; border-radius:14px; padding:16px; }}
    .hero h1 {{ margin:0 0 6px; }}
    .day {{ margin-top:12px; background:#fff; border:1px solid #d8e1d7; border-radius:12px; padding:12px; }}
    .day h2 {{ margin:0 0 5px; }}
    .muted {{ color:#5d6773; font-size:13px; margin-bottom:8px; }}
    ul {{ margin:0 0 0 18px; padding:0; }}
    li {{ margin:8px 0; line-height:1.52; }}
    .cat {{ display:inline-block; border-radius:7px; background:#e6f3ee; color:#125a49; font-size:12px; font-weight:700; padding:2px 8px; margin-right:6px; }}
    a {{ color:#135db0; text-decoration:none; }}
  </style>
</head>
<body>
  <main class="wrap">
    <header class="hero">
      <h1>AI 今日精简历史</h1>
      <div>只保存“今天发生了什么”的精简事实条目，供后续三篇长文回看。</div>
    </header>
    {days}
  </main>
</body>
</html>""".format(days="".join(day_cards))
    HISTORY_HTML.write_text(html_doc, encoding="utf-8")


def build_index_page(date_str, article_infos, records, event_count):
    cards = []
    for item in article_infos:
        cards.append(
            """
            <article class="card">
              <h2>{title}</h2>
              <p>{desc}</p>
              <a href="{href}" target="_blank">阅读全文</a>
            </article>
            """.format(
                title=html_escape(item["label"]),
                desc=html_escape(item["desc"]),
                href=html_escape(item["href"]),
            )
        )

    timeline = []
    for rec in list(reversed(records))[:5]:
        lines = []
        for x in rec.get("concise", [])[:3]:
            lines.append(
                "<li><strong>{cat}</strong> Q{q} {author}：{text}</li>".format(
                    cat=html_escape(x.get("category", "")),
                    q=to_int(x.get("quality_score", 0)),
                    author=html_escape(x.get("author", "")),
                    text=linkify(x.get("text", "")),
                )
            )
        timeline.append(
            """
            <section class="timeline_day">
              <h3>{date}</h3>
              <div class="muted">事件总数：{count}</div>
              <ul>{items}</ul>
            </section>
            """.format(
                date=html_escape(rec.get("date", "")),
                count=to_int(rec.get("event_count", 0)),
                items="".join(lines),
            )
        )

    html_doc = """<!doctype html>
<html lang="zh">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>深度阅读中心</title>
  <style>
    body {{ margin:0; background:#f4f6f3; color:#1d2430; font-family:"Noto Sans SC",system-ui,sans-serif; }}
    .wrap {{ max-width:1160px; margin:0 auto; padding:20px 14px 40px; }}
    .hero {{ background:linear-gradient(140deg,#102c43,#0f5f5a); color:#ecfff7; border-radius:16px; padding:18px; }}
    .hero h1 {{ margin:0 0 8px; }}
    .quick {{ display:grid; grid-template-columns:1fr 1fr; gap:10px; margin:12px 0; }}
    .quick a {{ display:block; background:#fff; border:1px solid #d6ddd5; border-radius:12px; padding:12px; text-decoration:none; color:#0d56a0; font-weight:800; }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(270px,1fr)); gap:10px; }}
    .card {{ background:#fff; border:1px solid #d6ddd5; border-radius:12px; padding:12px; }}
    .card h2 {{ margin:0 0 8px; font-size:28px; }}
    .card p {{ color:#5a6470; min-height:48px; line-height:1.5; }}
    .card a {{ color:#0f593a; text-decoration:none; font-weight:800; }}
    .timeline {{ margin-top:12px; background:#fff; border:1px solid #d6ddd5; border-radius:12px; padding:12px; }}
    .timeline_day {{ border-top:1px solid #e2e8df; padding-top:10px; margin-top:10px; }}
    .timeline_day:first-child {{ border-top:0; margin-top:0; padding-top:0; }}
    .muted {{ color:#5d6773; font-size:13px; margin-bottom:6px; }}
    ul {{ margin:0 0 0 18px; padding:0; }}
    li {{ margin:6px 0; line-height:1.45; }}
    @media (max-width:900px) {{ .quick {{ grid-template-columns:1fr; }} }}
  </style>
</head>
<body>
  <main class="wrap">
    <header class="hero">
      <h1>深度阅读中心</h1>
      <div>日期：{date} · 事件总数：{count} · 同一入口下完成：三篇长文 + 全事件事实 + 历史回看。</div>
    </header>
    <section class="quick">
      <a href="facts_all_events.html" target="_blank">打开：全事件事实页</a>
      <a href="brief_history.html" target="_blank">打开：AI 今日精简历史</a>
    </section>
    <section class="grid">{cards}</section>
    <section class="timeline">
      <h2 style="margin:0 0 8px;">历史精简信息（可读版）</h2>
      {timeline}
    </section>
  </main>
</body>
</html>""".format(
        date=html_escape(date_str),
        count=event_count,
        cards="".join(cards),
        timeline="".join(timeline),
    )
    INDEX_HTML.write_text(html_doc, encoding="utf-8")


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ARTICLES_DIR.mkdir(parents=True, exist_ok=True)

    date_str = datetime.now().strftime("%Y-%m-%d")
    deep_model = load_deep_model()
    feed = dedup(read_feed(FEED_CSV))
    events_all = to_events(feed)
    events = [e for e in events_all if not e.get("is_ad", False)]
    ad_blocked_count = len(events_all) - len(events)

    concise_today = build_concise_entries(events, topn=16)
    records = upsert_history(date_str, concise_today, event_count=len(events))
    hist = history_excerpt(records, date_str, limit_days=4)

    role_configs = [
        {
            "role": "karpathy",
            "title": "Karpathy 视角：模型机制与系统边界",
            "subtitle": "第一性原理 + 工程可复现 + 系统演化",
            "brand": "#0f5b67",
            "opening": "我先看证据是否可复现，再判断这条信号是否值得规模化投入。",
            "framework": ["机制变化是否真实", "工程成本是否可控", "系统边界是否被改写"],
            "actions": ["我会先做小样本复现实验", "我会记录失败样本并复盘", "我会每周更新技术风险台账"],
            "desc": "技术机制、工程约束、系统边界。",
        },
        {
            "role": "amjad",
            "title": "Amjad 视角：开发者杠杆与产品闭环",
            "subtitle": "任务闭环 + 交互成本 + 执行稳定性",
            "brand": "#175f47",
            "opening": "我会把能力放进真实任务链路，先看是否真的减少步骤和返工。",
            "framework": ["用户门槛是否降低", "任务链路是否缩短", "失败恢复是否可控"],
            "actions": ["我会按任务链路重排工具", "我会持续追踪一次完成率", "我会优先修复高频中断点"],
            "desc": "产品杠杆、工作流闭环、用户成本。",
        },
        {
            "role": "elad",
            "title": "Elad 视角：价值捕获与资本效率",
            "subtitle": "价值流向 + 护城河 + 资本效率",
            "brand": "#7a4f16",
            "opening": "我会先区分短期热度和长期价值，再判断是否形成可防御能力。",
            "framework": ["价值是否可捕获", "是否可被快速复制", "增长是否可持续"],
            "actions": ["我会按证据更新方案优先级", "我会拆分短期热点与长期价值", "我会跟踪护城河相关指标"],
            "desc": "商业防御力、价值捕获与资本效率。",
        },
    ]

    article_infos = []
    for cfg in role_configs:
        selected = role_events(events, cfg["role"])
        analysis_html = build_model_analysis_html(cfg, selected, hist, deep_model)
        if not analysis_html:
            analysis_html = build_rule_analysis_html(cfg, selected)
        out = write_article(date_str, cfg, selected, hist, analysis_html)
        article_infos.append(
            {
                "label": cfg["title"].replace("：", " "),
                "desc": cfg["desc"],
                "href": out.relative_to(OUT_DIR).as_posix(),
                "abs_path": out,
            }
        )

    build_facts_events_html(date_str, events)
    build_history_html(records)
    build_index_page(date_str, article_infos, records, event_count=len(events))

    manifest = {
        "date": date_str,
        "deep_writing_model": deep_model,
        "event_count_raw": len(events_all),
        "event_count_deep": len(events),
        "ad_blocked_count": ad_blocked_count,
        "index": INDEX_HTML.relative_to(REPORT_DIR).as_posix(),
        "facts": FACTS_HTML.relative_to(REPORT_DIR).as_posix(),
        "history_html": HISTORY_HTML.relative_to(REPORT_DIR).as_posix(),
        "history_json": HISTORY_JSON.relative_to(REPORT_DIR).as_posix(),
        "articles": [x["abs_path"].relative_to(REPORT_DIR).as_posix() for x in article_infos],
    }
    MANIFEST_JSON.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(INDEX_HTML.as_posix())
    print(FACTS_HTML.as_posix())
    print(HISTORY_HTML.as_posix())
    print(HISTORY_JSON.as_posix())
    for x in article_infos:
        print(x["abs_path"].as_posix())
    print(MANIFEST_JSON.as_posix())


if __name__ == "__main__":
    main()
