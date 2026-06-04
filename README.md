# 网易云音乐标签管理 — Claude Code 技能

一枚自研 Claude Code 技能：**红心歌单标签管理 + MusicBrainz 自动标注 + 本地标签搜索**。

> ℹ️ ncm-cli-setup、netease-music-cli、netease-music-assistant 为网易官方技能，
> 通过 `npx skills add https://github.com/NetEase/skills` 安装。

## 前置要求

- **Node.js >= 18**
- **Python >= 3.8**
- **网易云 API Key**：[开放平台申请](https://developer.music.163.com/st/developer/apply/account?type=INDIVIDUAL)

## 快速开始

```bash
# 1️⃣ 安装 ncm-cli（必须先装）
npm install -g @music163/ncm-cli
ncm-cli --version   # 验证安装成功

# 2️⃣ 配置 API Key + 登录
ncm-cli config set appId <你的AppId>
ncm-cli config set privateKey <你的PrivateKey>
ncm-cli login --background

# 3️⃣ 安装网易官方技能（推荐，包含安装引导 + CLI 操作 + 智能推荐）
npx skills add https://github.com/NetEase/skills

# 4️⃣ 安装本仓库自研技能（标签管理 + 搜索）
npx netease-music-skills

# 5️⃣ 同步红心歌单
export NCM_LIKED_PLAYLIST_ID="你的红心歌单ID(32位hex)"
python tools/sync.py
```

## 技能一览

| 来源 | 技能 | 说明 |
|------|------|------|
| 网易官方 | `ncm-cli-setup` | 一键安装 ncm-cli + mpv、配置 API Key |
| 网易官方 | `netease-music-cli` | CLI 操作 — 播放控制、搜索、歌单管理 |
| 网易官方 | `netease-music-assistant` | 智能推荐 — 偏好分析、搜索策略、调度推送 |
| **自研** | **`music-curator`** | **标签管理 + MusicBrainz 标注 + 本地搜索** |

---

## music-curator 详解

### 整体架构

```
网易云红心歌单 ──sync.py──→ songs_db.json ──tag.py──→ 标签查询/搜索
                               │
                    MusicBrainz API ──musicbrainz.py──→ 流派/年代/风格标注
```

### 标签体系

标签采用 **分类:值** 格式，共 9 个维度，分三层自动标注：

| 层级 | 维度 | 来源 | 示例 |
|------|------|------|------|
| **Tier 1** | 流派、风格、年代 | MusicBrainz 自动查询 | `流派:爵士` `年代:1990s` `风格:jazz-funk` |
| **Tier 2** | 地域、来源类型、节奏 | 规则推理 | `地域:日本` `来源:动漫OST` `节奏:短曲` |
| **Tier 3** | 情绪、器乐、氛围、人声 | AI 分析（需用户交互确认） | `情绪:浪漫` `器乐:萨克斯` `氛围:夜晚` |

#### Tier 1 — MusicBrainz 自动标注

调用 [MusicBrainz API](https://musicbrainz.org/doc/MusicBrainz_API)（免费、无需 Key），按艺人+歌名搜索录音，匹配分数 ≥90 才采纳。返回的原始标签经过映射为中文分类：

```
jazz → 流派:爵士    post-rock → 流派:后摇
soundtrack → 流派:原声    piano → 流派:钢琴    ambient → 流派:氛围
```

同时提取 `first-release-date` 作为年代标签，自动写入 DB。

#### Tier 2 — 规则推理

不需要外部 API，直接用歌曲元数据推断：

- **地域**：检测艺人名是否含日文/中文 → `地域:日本` / `地域:华语`
- **来源**：检测歌名/专辑名是否含 `ost`、`soundtrack`、`アニメ` → `来源:动漫OST` / `来源:电影OST`
- **节奏**：根据时长 → 短于 2 分钟标记 `节奏:短曲`，长于 7 分钟标记 `节奏:长篇`

#### Tier 3 — 用户 + AI 交互标注

当用户描述某首歌的感受时，模型按五维度给出标签建议 → 用户确认 → 写入。支持同维度替换。

### 搜索能力

```bash
# 结构化搜索 — 精确匹配分类:值
python tools/tag.py search "流派:爵士 器乐:钢琴"

# 模糊搜索 — 在所有字段中匹配
python tools/tag.py search "钢琴 古典"

# 标签浏览 — 按分类列出所有标签
python tools/tag.py tags
```

搜索逻辑：将用户输入拆为多个词，在所有歌曲的「歌名 + 艺人 + 专辑 + 标签」中匹配，按命中词数排序返回。

---

## 使用示例

```
# 同步红心歌单
$ python tools/sync.py

Fetching liked songs from ncm-cli...
  Looking up: Fly Me To The Moon — Olivia Ong
    -> 流派:爵士, 风格:jazz, 年代:2005
  ...

=== Sync Report ===
  Total:  362 songs  |  New: 5  |  Unchanged: 357

# 搜索相似歌曲
$ python tools/tag.py search "流派:爵士 器乐:钢琴"

Search "流派:爵士 器乐:钢琴": 20 results
  Fly Me To The Moon — Olivia Ong  [流派:爵士, 器乐:钢琴, 氛围:夜晚]
  Autumn Leaves — Eric Clapton  [流派:爵士, 器乐:钢琴, 年代:2010s]
  ...

# 查看歌曲详情（含 MusicBrainz）
$ python tools/tag.py show "Fly Me To The Moon" --mb

  URL:      https://music.163.com/#/song?id=28692537
  Tags:
  流派:  爵士, 波萨诺瓦
  器乐:  钢琴
  氛围:  夜晚
  MB Year:   2005
  MB Score:  98
```

---

## 项目结构

```
netease-music-skills/
├── README.md
├── LICENSE
├── install.js                    # npm 安装脚本
├── package.json
├── skills/
│   └── music-curator/            # 自研：标签管理 + 搜索
│       └── SKILL.md
└── tools/
    ├── sync.py                   # 红心歌单同步 + 自动标签
    ├── tag.py                    # 标签 CRUD + 搜索
    ├── batch_tag.py              # 全量 MusicBrainz 批量标注
    ├── musicbrainz.py            # MusicBrainz API 封装（30天缓存）
    └── init_db.py                # 从原始数据初始化数据库
```

## 常见问题

| 问题 | 解决方法 |
|------|----------|
| `ncm-cli: command not found` | `npm install -g @music163/ncm-cli` |
| 登录超时 | `ncm-cli login --background` |
| `NCM_LIKED_PLAYLIST_ID not set` | `export NCM_LIKED_PLAYLIST_ID="你的32位hex歌单ID"` |
| tools 报找不到数据库 | 先执行 `python tools/sync.py` 同步红心歌单 |
| MusicBrainz 查不到 | 小众日本独立音乐约 12% 无数据，正常 |

## 许可证

[Apache License 2.0](LICENSE)
