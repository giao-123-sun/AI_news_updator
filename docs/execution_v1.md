# Execution V1（设计 -> 执行 -> 测试 -> 修复）

## 1) 第一版设计记录
- 目标：日报、帖子浏览、方案对比三位一体。
- 数据来源：`report/tools_share.csv`、`report/experience_share.csv`、`report/news_papers.csv`。
- 输出物：
  - `report/daily_brief_v1.md`
  - `report/post_feed_v1.csv`
  - `report/idea_compare_v1.csv`
  - `report/hub_v1.html`

## 2) 三角色方案
### 麦肯锡顾问（Prompt与分析框架）
- 产出：`docs/prompt_studio_v1.md` 中“策略结论模板”。
- 关注：结论先行、证据回溯、支持/冲突分离。

### 张小龙（呈现方式）
- 产出：三段式阅读路径（日报 -> 帖子 -> 对比）。
- 关注：信息分层、降噪、最短路径。

### 前端女王（UI设计）
- 产出：`hub_v1.html` 的可视化界面（强调可读卡片 + 搜索筛选 + 对比面板）。
- 关注：桌面与移动端可读性、交互一致性、性能。

## 3) 角色分工（谁设计，谁评估，谁给方案）
- 设计Owner：按 `docs/raci_v1.md` 执行。
- 评估Reviewer：截图验收 + 可读性检查 + 交互完整性检查。
- 解决方案Decision：对评估问题直接给改动并复测。

## 4) 测试与问题修复
### 问题A：Markdown 未完整渲染（日报/方案对比）
- 现象：日报和对比文本显示为原始文本。
- 修复：新增前端 Markdown 渲染函数（标题、列表、链接、加粗、代码）。
- 结果：日报与对比区可按结构阅读。

### 问题D：方案对比表格渲染不稳定
- 现象：对比区以卡片形式呈现，阅读密度低且结构不稳定。
- 修复：
  - 改为固定列的表格渲染（方案/净得分/支持冲突/参与帖子/描述/证据）。
  - 证据列改为 `details` 展开（支持证据、冲突证据）。
  - 移动端通过横向滚动容器保证可浏览。
- 结果：对比区结构稳定、可快速横向对齐比较。

### 问题E：日报低信号信息未过滤
- 现象：部分无证据、短回复、低价值噪音进入日报关键区。
- 修复：
  - 新增 `quality_score` 评分（分类权重、链接/图片/长度、好坏关键词、回复噪音惩罚）。
  - 日报使用 `QUALITY_THRESHOLD_DAILY` 过滤（默认 >=2）。
  - 关键帖子增加“可追溯证据门槛”（推文链接或外链）。
- 结果：日报只保留高信号或可回溯证据内容，并展示过滤统计。

### 问题B：帖子浏览图片坏链
- 现象：图片路径无效（`nan` 和相对路径错误）。
- 修复：
  - 数据构建层增加 `safe_text`，避免 `nan` 被当作图片URL。
  - 本地图片路径统一转换为相对 `report/` 的可访问路径。
  - 前端图片 `onerror` 自动隐藏坏图。
- 结果：坏链不再显示；有图数据可正常展示。

### 问题C：移动端帖子页全页截图黑条
- 现象：Chromium 在移动端超长全页截图出现渲染伪影。
- 修复：
  - 帖子页改为分页渲染（默认20条，加载更多）。
  - QA 改为移动端视口截图（稳定且可复现）。
- 结果：移动端验收截图正常可读。

## 5) 截图验收产物
- 桌面：`report/qa/hub_v1_daily_desktop.png`
- 桌面：`report/qa/hub_v1_compare_desktop.png`
- 桌面：`report/qa/hub_v1_posts_desktop.png`
- 移动：`report/qa/hub_v1_daily_mobile.png`
- 移动：`report/qa/hub_v1_posts_mobile.png`
- 移动：`report/qa/hub_v1_compare_mobile.png`

> 截图命令：`python qa_capture_hub_v1.py`

## 6) 新增：去重 + 三篇长文产线
- 去重：
  - 在 `build_insight_hub_v1.py` 中加入去重键与去重流程（优先按推文链接去重，无链接时按作者+分类+日期+文本近似去重）。
  - 日报新增去重统计与低信号过滤统计。
- 三篇长文（写入 `human_comment/3ofthem/`）：
  - `YYYY-MM-DD_karpathy_longread.md`
  - `YYYY-MM-DD_amjad_longread.md`
  - `YYYY-MM-DD_elad_longread.md`
- 同步产物：
  - `facts_YYYY-MM-DD.md`（基本事实梳理）
  - `brief_history.md`（AI 今日精简信息历史）
  - `reading_room.html`（阅读友好页面）
- 运行方式：
  - `python run_daily_pipeline_v1.py`
