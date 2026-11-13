# 📰 视野日报

> 每日自动生成复古报纸风格的新闻简报

## 📅 查看日报

### 📰 在线阅读（推荐）

**点击直接查看最新一期报纸：**

🔗 **[阅读最新一期报纸](https://yz2020china.github.io/visual-novel-news-digest/digests/latest.html)**

### ✉ 邮箱订阅

📬 **[点击订阅，填写邮箱即可每天收到新一期](https://buttondown.com/visiondaily)**

在订阅页填写邮箱，再点击确认邮件中的链接即可生效（双重确认，防止他人冒用邮箱）。之后每期日报生成并发布后，邮箱会收到一封包含各栏目要闻和原文链接的邮件，并附完整一期的在线阅读链接。每封邮件底部都有退订链接，点击即可取消订阅。订阅名单由 [Buttondown](https://buttondown.com) 托管，不保存在本仓库。

每天计划于北京时间凌晨 04:12 触发自动生成任务；GitHub Actions 调度可能延迟，实际发布时间还需加上生成和部署耗时。生成成功后，这个固定链接会指向最新一期。生成失败时保留上一期，打开即可查看完整的复古报纸样式。

### 📁 历史存档

- [查看全部日报存档](https://github.com/YZ2020CHINA/visual-novel-news-digest/tree/main/digests)
- [下载最新一期 HTML](https://github.com/YZ2020CHINA/visual-novel-news-digest/raw/main/digests/latest.html)

阅读和下载链接均随新一期日报生成自动更新，无需手动修改日期；历史日报仍按日期保存。

### 💻 本地查看

克隆仓库后，直接用浏览器打开 `digests/` 目录下的 HTML 文件。

---

## 🎨 特色

- **复古报纸风格**：经典报纸排版，还原纸媒质感
- **AI 智能编辑**：Claude AI 自动筛选头版新闻并生成中文摘要
- **多领域新闻**：社会事件、经济与市场、AI 与科技、文化艺术（含电影）、独立游戏与视觉小说、宗教与意识形态
- **图文并茂**：自动提取新闻配图
- **彩色报纸印刷照片**：自动为新闻配图添加褪色、油墨网点和轻微套印偏移，直接嵌入 HTML
- **每日更新**：GitHub Actions 计划每天北京时间 04:12 触发生成
- **名人生日**：版尾附带当天诞生的名人小故事

## 📁 项目结构

```
视野日报/
├── .github/workflows/    # GitHub Actions 自动化配置
├── templates/            # HTML 模板
├── static/              # 静态资源（CSS）
├── digests/             # 生成的日报存档
├── news_digest.py       # 主程序
└── requirements.txt     # Python 依赖
```

## 🚀 使用方法

### 邮箱订阅部署（仓库维护者）

1. 在 [Buttondown](https://buttondown.com) 注册账号（前 100 位订阅者免费），在 Settings 中确认用户名；订阅页地址为 `https://buttondown.com/<用户名>`。
2. 若用户名不是 `visiondaily`，修改 `newsletter.json` 中的 `buttondown_username`，并同步替换本 README 中的订阅链接，然后运行 `python newsletter.py backfill` 更新已有存档的报头。
3. 在 Buttondown Settings → API 复制密钥，加入 GitHub 仓库 **Settings → Secrets and variables → Actions**，名称为 `BUTTONDOWN_API_KEY`。不要写进代码或提交到 Git。
4. 未配置密钥时，日报照常生成，仅跳过发信。每次发信使用 `daily-YYYY-MM-DD` 作为固定标识，同一天重跑不会重复发送；当天没有新生成的日报时也不会重发旧报。

邮件是精简的要闻摘要（不含内嵌配图），完整配图版请点击邮件中的在线阅读链接。订阅、确认、退订和投递均由 Buttondown 处理；超出免费额度后需按其[定价](https://buttondown.com/pricing)付费。

### 本地运行

1. **安装依赖**
```bash
pip install -r requirements.txt
```

2. **配置环境变量**
```bash
export OPENAI_API_KEY="your_api_key"
export OPENAI_BASE_URL="your_base_url"  # 可选
```

3. **运行程序**
```bash
python news_digest.py
```

生成的 HTML 文件会保存在 `digests/` 目录下。

### 彩色报纸印刷照片

生成日报时，程序会下载提取到的新闻图片，保留彩色和照片细节，添加轻微褪色、密集油墨网点、套印偏移和纸张颗粒。结果压缩为 JPEG 并内嵌到 HTML 中，转换后的配图无需再次访问图片源，适合下载保存和离线查看。

- 采用暖纸色，保留图片比例和相机方向，透明区域用浅色背景填充。
- 同一个图片地址在一次生成中只处理一次；下载失败、文件损坏或超过限制时保留原图地址。
- 单张图片下载上限为 8 MiB，解码上限为 2000 万像素；输出长边不超过 1000 像素。
- 图片转换不调用 AI 接口。额外下载图片会增加生成时间，内嵌图片会增加 HTML 大小。
- 此效果用于新生成的日报，已有存档不会自动改变。

安装依赖后，可独立运行图片转换和日报 HTML 集成测试（无需 API Key）：

```bash
python -m unittest test_newsprint -v
```

核心转换代码位于 `newsprint.py`。每日自动任务会先运行上述测试，再生成日报。

### GitHub Actions 自动化

1. **Fork 或克隆本仓库到你的 GitHub**

2. **配置 Secrets**
   - 进入仓库的 Settings → Secrets and variables → Actions
   - 添加以下 secrets：
     - `OPENAI_API_KEY`: 你的 OpenAI API Key
     - `OPENAI_BASE_URL`: API 基础 URL（可选）

3. **自动运行**
   - 计划每天北京时间 04:12 触发（cron：`12 20 * * *`，即前一天 UTC 20:12），实际运行可能因 GitHub 调度而延迟
   - 报头、刊号和存档文件名均按北京时间计算，避免凌晨运行生成前一天日期的日报
   - 也可以在 Actions 页面手动触发

## 📰 新闻源

- **社会事件**: 纽约时报中文网, BBC 中文, [Bloomberg Businessweek](https://www.bloomberg.com/businessweek)、Bloomberg Politics（官方 RSS）
- **经济与市场**: BBC Business、CNBC Economy、CNBC Markets、The Guardian Economics、Bloomberg Markets、Bloomberg Economics，涵盖全球宏观经济、央行政策与金融市场
- **AI 与科技**: MIT Tech Review, TechCrunch, The Verge, AI News, Bloomberg Technology
- **文化艺术**: ArtNews, Hyperallergic, Creative Bloq，以及 Variety Film、The Guardian Film 的电影新闻
- **独立游戏与视觉小说**: IndieGames, Reddit, Ren'Py, Itch.io，以及机核、IGN 中国、WayTooManyGames 的游戏资讯与评测
- **宗教与意识形态**: Christian Science Monitor, Aeon, Philosophy Now

游戏栏目新增订阅入口：[机核 RSS](https://www.gcores.com/rss)、[IGN 中国 RSS](https://www.ign.com.cn/feed.xml)、[WayTooManyGames RSS](https://waytoomany.games/feed/)。每个来源读取订阅中的前 5 条有效文章，沿用中文翻译、摘要、配图和原文阅读链接流程；单个来源抓取失败不会中断其他来源。游戏栏目包含综合游戏资讯与评测，不额外限制为视觉小说。

经济与市场栏目收录生成时最近 24 小时内发布的新闻，覆盖北京时间凌晨出报时欧美前一交易时段的动态；按新闻链接去重，每个来源最多 5 条。无日期、过期和未来时间的条目会跳过，不用旧闻填充；若来源全部不可用或没有符合时间条件的报道，该期不显示空栏目。已有历史日报保留原始内容，新配置用于后续生成。

## 🎨 版面设计

### Telegram、X、Hacker News 独立板块

新增三个平台栏目，每个平台从最近 **24 小时**候选内容中，先排除已刊登内容和重复新闻，再按热度取 **最多 5 条**。不足 5 条时显示实际数量，不用旧帖凑数。页面保留帖文原链接、来源及热度，并显示来源故障或未配置状态。

配置文件为 `platform_sources.json`：

| 平台 | 默认采集范围 | 排序规则 |
| --- | --- | --- |
| Telegram | solidot、TestFlightCN 公开频道网页预览 | 浏览量降序 |
| X | Reuters、BBCWorld、TechCrunch、verge、OpenAI、AnthropicAI | 点赞 + 2 × 转发 + 回复 |
| Hacker News | 官方 Firebase API 热榜前 150 个候选 | 积分降序 |

这是指定来源及候选范围内的热门内容，不是全平台完整热榜。Telegram 预览通常只返回近期的一页消息，高频频道可能无法覆盖全天；HN 可通过 `hn_candidates` 调整候选数（上限 500）。频道、账号列表可直接修改配置文件。

Telegram 和 Hacker News 无需密钥。X 参考 [Horizon](https://github.com/Thysrael/Horizon) 的 Apify 接入方式，使用 `altimis/scweet` actor；在 GitHub 仓库 **Settings → Secrets and variables → Actions** 添加 `APIFY_TOKEN` 即可启用。Apify 运行可能消耗该账户额度，每次日报最多发起一次采集，最多请求 100 条候选，不额外采集评论。未配置凭据时仍生成其他新闻，X 栏目会明确提示未启用。不要把密钥写进 JSON 或提交到 Git。

费用提示（2026-11-11 核对）：该 actor 文档另外规定免费试用累计 3,000 条，不是每月重置。每天 100 条约可运行 30 次，测试运行也可能消耗额度。Apify 平台免费额度与 actor 试用限制是两回事；长期运行前请检查 [actor 当前说明](https://apify.com/altimis/scweet) 和账户订阅、用量，程序不会自动替你升级套餐。

### 防止每天重复刊登

- 全部栏目共同去重，清除链接中的 `utm_*`、`fbclid` 等追踪参数，统一 X/Twitter、Telegram 域名别名；保留用于区分新闻的查询参数。
- 相同规范化标题（至少 16 个字符）只保留一条；Telegram/HN 指向同一外部文章时也会合并。不同语言、完全改写标题的同一事件仍可能重复，本功能不是语义事件聚类。
- 默认回看最近 30 天（含当日）的日报 HTML 和 `digests/YYYY-MM-DD.news.json` 刊登记录，首次启用也能从已有存档排除旧链接。旧存档只有翻译后的标题时，原文标题匹配从新记录开始生效。
- 每个 RSS 来源先读最多 50 条候选，去重后保留最多 5 条，再获取配图，避免旧条目占满名额。原经济栏目的 24 小时时效规则继续保留。
- 只有日报保存成功后才写入刊登记录，并随日报一起提交 Git；同一天重跑会合并记录，已刊登内容不会重新入选。没有任何新内容时保留上一期。

验证全部功能（无需真实 API 密钥）：

```bash
python -X utf8 -m unittest test_newsprint test_latest_digest test_layout test_news_sources test_platform_news test_news_history -v
```

三个平台的适配实现根据 Horizon 公开接口和字段独立编写，没有引入其完整运行环境。

### 工作室报头

每期报头展示自动代谢工作室 Logo 和 [@johnvauk](https://x.com/johnvauk)，两者均可点击进入工作室 X 页面。Logo 已裁去多余空白，保留完整图形和文字，使用黑白印刷风格与自适应布局，并内嵌到 HTML，下载日报后无需外链加载。既有存档也已补上该报头，新闻内容保持原样。

- **报头**：视野日报 + 日期 + 刊号
- **头版**：当日最重要新闻，配大幅图片
- **分栏内容**：各板块新闻，采用双栏布局
- **版尾**：当天生日的名人小故事

## 📄 技术栈

- **Python 3.11**
- **AI**: Claude Opus 5.5
- **RSS 解析**: feedparser
- **网页抓取**: BeautifulSoup4
- **自动化**: GitHub Actions

---

*由 GitHub Actions 每日自动更新 | Powered by Claude AI*
