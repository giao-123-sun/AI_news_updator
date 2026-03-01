# Design Notes

## Product targets
- 日报: 5 分钟掌握当天有效信息。
- 帖子流: 快速浏览原始帖子与配图，便于二次研判。
- 方案对比: 用证据支持/冲突来评估方案优先级。
- 深度阅读: 三篇长文 + 全事件事实 + 历史回看，形成稳定阅读闭环。

## Data design
- Unified feed schema:
  - `category`, `author`, `time`, `text`
  - `tweet_link`, `external_links`
  - `images_local`, `images_remote`
  - `quality_score`, `quality_level`
- Dedup key priority:
  1. tweet link
  2. normalized text + author + date + category
- Source strategy (learning mode):
  - keep a stable core account set
  - extend with frontier-lab / builder / product accounts for exploration
  - rely on dedup + quality scoring to keep reading output compact
  - broad-then-precise: expand source first, then apply relevance/evidence gates for final reading output

## Quality filtering design
- Keep low-signal posts out of daily/compare primary view.
- Favor evidence-backed events (tweet/external links).
- Keep all events accessible in fact page.
- Evidence-first browsing rule:
  - every key item should expose at least one clickable evidence URL
  - when tweet link is missing, use external link fallback for fast verification

## Reading UX design
- Hub keeps a single entry point, then jumps to full-page longreads.
- Longread article pages use Medium-like patterns:
  - full-width hero
  - limited content width for readability
  - serif reading typography + larger line-height
  - sectioned structure (framework / evidence / analysis / history / actions)
- Facts and history pages are HTML-first, not markdown source view.

## Why this structure
- Fast overview and deep reading are separated but connected.
- Full-event fact page preserves completeness.
- History store gives continuity: each new longread can quickly review prior concise facts.

## Digest clone design
- Target reference: `ai-digest.liziran.com` homepage information architecture.
- Replicated elements:
  - slim top nav
  - centered slogan header
  - daily card list with numbered top 3
  - source-count link per card
  - archive entry and lightweight footer
- Local adaptation:
  - content is generated from `post_feed_v1.csv`
  - quality-ranked daily selection
  - digest and sources pages generated for each day

## Digest clone V2 typography
- Keep the same IA and interaction model as clone V1.
- Adjust typography scale to match target visual density:
  - reduce homepage slogan and card headline sizes
  - reduce mobile card and nav text sizes
  - remove oversized responsive font expansion
- Maintain readability on article pages with smaller but still comfortable line-height.

## Evidence-complete browsing (2026-03-01)
- Primary UX requirement:
  - cards should expose direct source access (`tweet_link`) and optional supporting links/images.
- Current rendering policy:
  - source link order: tweet link first, external link fallback.
  - image source order: local downloaded image first, remote image fallback.
- Expected user outcome:
  - users can quickly read summary and immediately jump to original evidence without copying text.
