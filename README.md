# 网易云音乐 Claude Code 技能包 (Netease Music Skills for Claude Code)

一套完整的网易云音乐 Claude Code 技能集合，包含智能推荐助手、CLI 操作、安装配置和音乐策展工具。

## 包含的技能

| 技能 | 说明 |
|------|------|
| **netease-music-assistant** | 智能音乐助手 — 偏好分析、多关键词搜索策略、智能推荐（含两层推荐理由）、调度推送、飞书推送 |
| **netease-music-cli** | CLI 操作 — 播放控制、搜索、歌单管理、队列管理、TUI 播放器 |
| **ncm-cli-setup** | 安装配置 — 一键安装 ncm-cli + mpv、API Key 配置、登录引导 |
| **music-curator** | 音乐策展 — 本地标签库搜索、MusicBrainz 自动标注、红心歌单同步 |

## 前置要求

- **Node.js >= 18**（用于 ncm-cli）
- **Python >= 3.8**（用于 tools/ 下的脚本）
- **mpv**（可选，用于本地播放；安装脚本自动检测系统并安装）
- **网易云音乐 API Key**：前往[网易云音乐开放平台](https://developer.music.163.com/st/developer/apply/account?type=INDIVIDUAL) 申请

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/KinoJian/netease-music-skills.git
cd netease-music-skills
```

### 2. 安装技能到 Claude Code

将技能目录复制或链接到 Claude Code 的 skills 目录：

**macOS / Linux:**
```bash
ln -s "$(pwd)/skills/ncm-cli-setup" ~/.claude/skills/ncm-cli-setup
ln -s "$(pwd)/skills/netease-music-cli" ~/.claude/skills/netease-music-cli
ln -s "$(pwd)/skills/netease-music-assistant" ~/.claude/skills/netease-music-assistant
ln -s "$(pwd)/skills/music-curator" ~/.claude/skills/music-curator
```

**Windows (PowerShell):**
```powershell
New-Item -ItemType Junction -Path "$env:USERPROFILE\.claude\skills\ncm-cli-setup" -Target (Resolve-Path "skills\ncm-cli-setup")
# ... 以此类推
```

或直接复制：
```bash
cp -r skills/* ~/.claude/skills/
```

### 3. 初始化配置

首先安装 ncm-cli 和 mpv（在 Claude Code 中输入 `/ncm-cli-setup` 即可自动引导），然后配置 API Key：

```bash
ncm-cli config set appId <你的AppId>
ncm-cli config set privateKey <你的PrivateKey>
ncm-cli login --background
```

### 4. （可选）同步红心歌单到本地数据库

如果你要使用 music-curator 的本地标签搜索功能：

```bash
export NCM_LIKED_PLAYLIST_ID="你的红心歌单ID"
python tools/sync.py
```

## 使用方式

在 Claude Code 中直接对话即可触发技能：

- 输入「网易云 推荐爵士乐」→ 自动触发 netease-music-assistant 进行智能推荐
- 输入「播放周杰伦的晴天」→ 触发 netease-music-cli 搜索并播放
- 输入「帮我分析我的音乐偏好」→ 触发偏好分析
- 输入「在我歌单里找钢琴曲」→ 触发 music-curator 本地搜索

## 项目结构

```
netease-music/
├── README.md
├── LICENSE
├── .gitignore
├── skills/
│   ├── ncm-cli-setup/           # 安装配置技能
│   │   ├── SKILL.md
│   │   └── scripts/
│   │       └── install_mpv.py
│   ├── netease-music-cli/       # CLI 操作技能
│   │   └── SKILL.md
│   ├── netease-music-assistant/ # 智能推荐技能
│   │   └── SKILL.md
│   └── music-curator/           # 音乐策展技能
│       └── SKILL.md
└── tools/
    ├── sync.py                  # 红心歌单同步
    ├── tag.py                   # 标签管理
    ├── batch_tag.py             # 批量标注（MusicBrainz）
    ├── musicbrainz.py           # MusicBrainz API 封装
    └── init_db.py               # 数据库初始化
```

## 常见问题

| 问题 | 解决方法 |
|------|----------|
| `ncm-cli: command not found` | 运行 `npm install -g @music163/ncm-cli` |
| `mpv not found` | 运行 `python skills/ncm-cli-setup/scripts/install_mpv.py` |
| 登录超时 | 运行 `ncm-cli login --background` |
| `NCM_LIKED_PLAYLIST_ID not set` | 设置环境变量后重试 |
| tools 脚本报找不到数据库 | 先运行 `python tools/sync.py` 同步红心歌单 |

## 许可证

[Apache License 2.0](LICENSE)
