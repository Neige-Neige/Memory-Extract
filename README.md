# Memory Extract

一个本地桌面工具，浏览、搜索、深度分析 LLM 对话和聊天记录的导出 JSON。

最初是给 ChatGPT 拆分成多个 `.json` 的导出场景写的，后来加了 Claude.ai 和 Telegram 的格式支持，并把"用 DeepSeek 二次分析这些对话"做成一等公民。

## 主要功能

### 导入与浏览

- **支持三种导出格式**，自动识别：
  - ChatGPT 完整导出（含 `mapping` 树的官方格式）
  - Claude.ai 导出（`chat_messages` + content blocks，含 thinking / tool use）
  - Telegram Desktop 导出（`Export chat history → JSON`，按真名分角色）
  - 还有通用的 `messages: [...]` 简单格式
  - 同一个文件夹里混着不同格式也能加载
- **整文件夹批量加载**或**多选若干 JSON 文件**；`⟳` 按钮可重新加载（往文件夹里新加了 JSON 不用重启）
- 左侧会话列表支持**全文搜索**（不只匹配标题，也搜每条消息正文），按命中数排序
- 排序模式：更新时间新→旧 / 旧→新 / 标题 A→Z / 搜索命中数

### 阅读与定位

- 主对话查看器**实时渲染 Markdown**：`**bold**`、标题、列表、行内/块代码、表格、引用块全部渲染，看 ChatGPT 长回答不再看到一堆 `**`
- **主搜索栏**：在当前对话里搜，◀ ▶ 翻页，F3 / Shift+F3 快捷键
- **多层筛选**（"在此对话中再筛"）：可加 N 层关键词，AND/OR 模式切换，每层独立色高亮 + 独立 ◀▶ 导航；不匹配的消息自动淡化
- **可选侧边栏**（默认收起，按钮手动展开）：
  - 📑 大纲：每条消息一行，点击跳转
  - 🎯 命中：主搜索每个 hit 所在行，点击跳转
  - 🪄 筛选：层筛选命中的消息，点击跳转

### DeepSeek 集成

- 主窗口选中一个或多个会话 → `🪄 DeepSeek 分析` → 弹出对话框
- 多轮对话：模板提示词 → 开始分析 → 持续追问；中途可 `+ 加入对话…`合并新会话进上下文
- **多窗口并行**：可同时开多个分析窗口（独立最小化）
- **🔬 深度研究**：第一轮回答完后亮起；开新窗口、自动切换到 `deepseek-reasoner`、显示 CoT 思考过程（灰色斜体）
- **可点击引用源** `[#3]` / `[对话2-#7]` / `[#5-#12]` 范围：点击跳到主窗口对应消息并高亮闪烁
- 导出分析记录为 Markdown / JSON / TXT
- API key 可选保存到本地 config（明文），密码输入框遮蔽显示

### 个性化

- **🎨 配色**：7 项可自定义色（正文/副文/强调/思考过程/背景/卡片/高亮），含纸纹随背景色自动重新生成
- **👤 用户资料卡**：可选填名字 + 代词，DeepSeek 在分析时会按你的代词写（避免默认全用"他"）
- **📋 此对话资料**：单个对话独立的资料卡，覆盖全局（不同对话里 AI 助手叫不同名字时有用）
- **📜 活动日志**：自动记录加载/分析/导出动作，含"研究进行度"漏斗

## 安装

需要 Python 3.10+ 和 PySide6（Qt 6.4+ 因为用了 GFM markdown）：

```bash
pip install -r requirements.txt
```

## 运行

```bash
# Qt 版（推荐）
python app_qt.py

# Tk 版（旧版，功能略少，仅作为零依赖回退）
python app.py

# 或者用启动器（Windows 双击 启动.bat）
python launcher.py
```

Qt 版第一次启动会在 `assets/` 下生成纸纹缓存，之后启动秒开。

## 配置文件

- 用户配置：`%APPDATA%\memory_extract\config.json`（Windows）或 `~/.memory_extract/config.json`（其他系统）
- 活动日志：同目录下的 `history.jsonl`
- 纸纹缓存：同目录下的 `textures/paper_v2_<hex>.png`（按背景色 hash，自动生成）
- DeepSeek API key：勾选"保存 Key"后写入 config，明文存储——介意的话不要勾

## 打包成 .exe（给不装 Python 的人用）

```bash
pip install pyinstaller
python build_exe.py
```

输出在 `dist/Memory-Extract/`，把整个文件夹打 zip 就能发给别人。
对方解压、双击 `Memory-Extract.exe` 即可，不需要装 Python 或任何依赖。

打包后的文件夹大约 80-100 MB（已经排除掉用不到的 Qt 模块比如 WebEngine、Multimedia 等）。
启动 < 1 秒。所有用户数据仍然走 `%APPDATA%`，bundle 本身保持只读。

## 使用 DeepSeek

需要自己的 API key（[platform.deepseek.com](https://platform.deepseek.com/)）。
应用本身不会上传任何数据到第三方，所有 API 调用直接你的客户端 ↔ DeepSeek 服务器。

## 隐私说明

- 所有数据本地处理，不上传任何云端（除非你主动用 DeepSeek 分析）
- 保存的 API key 是明文存储在本地 config 里
- 资料卡里填的名字 / 代词只用于本地 system prompt 拼接
- 导出 DeepSeek 分析记录时，Markdown/TXT 只保存可见分析过程；JSON 也会默认省略原始对话全文、本机绝对路径和 system prompt，只保留源文件名与后续追问/回复

## 致谢

PySide6 / Qt for Python · DeepSeek API · 你愿意分享导出来折腾的耐心

Built with 🌀 Claude Code
Built with 🌊 Codex