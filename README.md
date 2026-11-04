# 📰 视野日报

> 每日自动生成复古报纸风格的新闻简报

## 🎨 特色

- **复古报纸风格**：经典报纸排版，还原纸媒质感
- **AI 智能编辑**：Claude AI 自动筛选头版新闻并生成中文摘要
- **多领域新闻**：独立游戏、AI 科技、文化艺术、社会观察、宗教与意识形态
- **图文并茂**：自动提取新闻配图
- **每日更新**：GitHub Actions 每天早上 8 点自动生成
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

### GitHub Actions 自动化

1. **Fork 或克隆本仓库到你的 GitHub**

2. **配置 Secrets**
   - 进入仓库的 Settings → Secrets and variables → Actions
   - 添加以下 secrets：
     - `OPENAI_API_KEY`: 你的 OpenAI API Key
     - `OPENAI_BASE_URL`: API 基础 URL（可选）

3. **自动运行**
   - 每天北京时间 08:00 自动生成
   - 也可以在 Actions 页面手动触发

## 📰 新闻源

- **独立游戏与视觉小说**: IndieGames, Reddit, Ren'Py, Itch.io
- **AI 与科技**: MIT Tech Review, TechCrunch, The Verge, AI News
- **文化艺术**: ArtNews, Hyperallergic, Creative Bloq
- **社会与文化**: 纽约时报中文网, BBC 中文
- **宗教与意识形态**: Christian Science Monitor, Aeon, Philosophy Now

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

## 📅 查看日报

每日生成的日报保存在 `digests/` 目录下，文件名格式为 `YYYY-MM-DD.html`。

用浏览器打开即可查看完整的复古报纸页面。

---

*由 GitHub Actions 每日自动更新 | Powered by Claude AI*
