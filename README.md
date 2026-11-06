# 📰 视野日报

> 每日自动生成复古报纸风格的新闻简报

## 📅 查看日报

### 📰 在线阅读（推荐）

**点击直接查看最新一期报纸：**

🔗 **[阅读最新一期报纸](https://yz2020china.github.io/visual-novel-news-digest/digests/latest.html)**

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
- **多领域新闻**：独立游戏、AI 科技、经济与市场、文化艺术（含电影）、社会事件、宗教与意识形态
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

- **独立游戏与视觉小说**: IndieGames, Reddit, Ren'Py, Itch.io
- **AI 与科技**: MIT Tech Review, TechCrunch, The Verge, AI News
- **经济与市场**: BBC Business、CNBC Economy、CNBC Markets、The Guardian Economics，涵盖全球宏观经济、央行政策与金融市场
- **文化艺术**: ArtNews, Hyperallergic, Creative Bloq，以及 Variety Film、The Guardian Film 的电影新闻
- **社会事件**: 纽约时报中文网, BBC 中文
- **宗教与意识形态**: Christian Science Monitor, Aeon, Philosophy Now

经济与市场栏目收录生成时最近 24 小时内发布的新闻，覆盖北京时间凌晨出报时欧美前一交易时段的动态；按新闻链接去重，每个来源最多 5 条。无日期、过期和未来时间的条目会跳过，不用旧闻填充；若来源全部不可用或没有符合时间条件的报道，该期不显示空栏目。已有历史日报保留原始内容，新配置用于后续生成。

## 🎨 版面设计

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
