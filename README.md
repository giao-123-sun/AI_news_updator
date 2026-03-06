# AI News Updator

一个面向 AI 前沿信息追踪的抓取与阅读系统。  
核心目标：把“抓到的信息”变成“可快速阅读、可回溯、可持续更新”的网页。

## 先看哪里（最重要）

如果你想看**最新抓取**，先看这个：

- `https://giao-123-sun.github.io/AI_news_updator/reports/daily/twitter_reader.html`

然后再看入口页：

- `https://giao-123-sun.github.io/AI_news_updator/reports/daily/index.html`

项目根入口（已做成导航页）：

- `https://giao-123-sun.github.io/AI_news_updator/`

## 为什么你之前看不到“新爬取”

当前仓库里有两条页面流：

1. `twitter_all_users.csv -> report/* -> twitter_reader`（最新抓取流，更新快）
2. `reports/daily/subagent_dashboard_YYYY-MM-DD.html`（历史专题流，更新频率较低）

你之前主要看的 `subagent_dashboard` 历史页，所以会感觉“没更新”。  
现在已把 `twitter_reader` 放到入口第一位。

## 主要页面说明

- `reports/daily/twitter_reader.html`
  - 面向“看抓取结果”的 reader-friendly 页面
  - 支持搜索、按作者筛选、仅看带图、按时间/点赞排序
- `reports/daily/index.html`
  - 稳定入口页（会提示推荐阅读顺序）
- `reports/daily/latest_dashboard.html`
  - 历史 dashboard 别名
- `reports/daily/source_map.html`
  - 信源映射页
- `reports/daily/replica_digest/index.html`
  - 日报风格归档页

## 一键执行流程

1. 准备 Cookie  
   - 推荐放到：`human_comment/cookies.txt`  
   - 你也可以先放 `config/cookie.txt`，再同步到上述路径

2. 抓取

```bash
python x_user_crawler.py
```

3. 构建页面

```bash
python run_daily_pipeline_v1.py
```

该命令会依次生成：

- `report/*`（分析页）
- `reports/daily/twitter_reader.html`（最新抓取阅读页）
- `reports/daily/index.html` / `latest_dashboard.html` / `source_map.html`
- 根入口页 `index.html`

## 常见问题

- 报错 `cookie file not found: human_comment/cookies.txt`  
  说明 X 登录 Cookie 路径不对或文件缺失。

- 出现 `RateLimited` 等待  
  说明被 X 限流，不是 API key 不够。可以降低抓取频率或减少页数。

- 报错 `report csv files not found. Run analysis first.`  
  说明还没成功跑完 `x_user_crawler.py`。

## 可读性设计（本次重构原则）

这次改版遵循了“先可读、再可扩展”的原则，重点是：

- 首页只做导航，不让用户猜入口
- 最新抓取流和历史专题流明确分开
- reader 页面优先保证信息密度与可检索性
- 移动端单列可读，桌面端信息块化

## 参考（X + 示例站点）

- X thread 发布与阅读结构：  
  `https://help.x.com/en/using-x/create-a-thread`
- X 创意可读性建议（官方）：  
  `https://business.x.com/content/dam/business-twitter/zh/pdf/creative-best-practices-guide.pdf`
- Dashboard 信息层次（Datadog 指南）：  
  `https://www.datadoghq.com/blog/dashboard-best-practices/`
- Dashboard 可读性实践（Datapad）：  
  `https://www.datapad.io/blog/dashboard-design`
- README 结构实践（GitHub Docs）：  
  `https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes`
- 示例 AI 日报站点（排版参考）：  
  `https://www.therundown.ai/`

