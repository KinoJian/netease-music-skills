# 网易云音乐标签管理 — Claude Code 技能包

两枚自研 Claude Code 技能：**一键安装 CLI 环境** + **红心歌单标签管理与搜索**。

> ℹ️ 智能推荐（netease-music-assistant）和 CLI 播放（netease-music-cli）是网易官方技能，
> 请通过以下命令安装：
> ```bash
> npx skills add https://github.com/NetEase/skills
> ```

## 技能一览

| 技能 | 说明 |
|------|------|
| **ncm-cli-setup** | 一键安装 ncm-cli + mpv 播放器、配置 API Key、登录引导 |
| **music-curator** | 红心歌单同步 → MusicBrainz 自动标注 → 本地标签搜索 → 相似歌曲发现 |

## 前置要求

- **Node.js >= 18**（ncm-cli 依赖）
- **Python >= 3.8**（标签脚本依赖）
- **ncm-cli**：`npm install -g @music163/ncm-cli`
- **网易云 API Key**：[开放平台申请](https://developer.music.163.com/st/developer/apply/account?type=INDIVIDUAL)

## 快速开始

### 一行命令安装（推荐）

```bash
npx netease-music-skills
```

这会自动把 ncm-cli-setup 和 music-curator 安装到 `~/.claude/skills/`。

### 或手动克隆

```bash
git clone https://github.com/KinoJian/netease-music-skills.git
cd netease-music-skills
ln -s "$(pwd)/skills/ncm-cli-setup" ~/.claude/skills/ncm-cli-setup
ln -s "$(pwd)/skills/music-curator" ~/.claude/skills/music-curator
```

### 初始化配置

```bash
# 安装 ncm-cli（或输入 /ncm-cli-setup 让技能引导安装）
npm install -g @music163/ncm-cli
ncm-cli config set appId <AppId>
ncm-cli config set privateKey <PrivateKey>
ncm-cli login --background
```

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

调用 [MusicBrainz API](https://musicbrainz.org/doc/MusicBrainz_API)（免费、无需 Key），按艺人+歌名搜索录音，匹配分数 ≥90 才采纳。返回的原始标签（如 `jazz`、`piano`）经过 `_classify()` 映射为中文分类：

```
jazz → 流派:爵士
post-rock → 流派:后摇
soundtrack → 流派:原声
piano → 流派:钢琴
ambient → 流派:氛围
```

同时提取 `first-release-date` 作为年代标签，自动写入 DB，不打扰用户。

#### Tier 2 — 规则推理

不需要外部 API，直接用歌曲元数据推断：

- **地域**：检测艺人名是否含日文/中文 → `地域:日本` / `地域:华语`
- **来源**：检测歌名/专辑名是否含 `ost`、`soundtrack`、`アニメ` → `来源:动漫OST` / `来源:电影OST`
- **节奏**：根据时长 → 短于 2 分钟标记 `节奏:短曲`，长于 7 分钟标记 `节奏:长篇`

#### Tier 3 — 用户 + AI 交互标注

当用户描述某首歌的感受时，模型按五维度给出标签建议 → 用户确认 → 写入。支持同维度替换（新值覆盖旧值）。

### 搜索能力

#### 本地标签搜索（`tag.py search`）

支持三种查询方式：

```bash
# 结构化搜索 — 精确匹配分类:值
python tools/tag.py search "流派:爵士 器乐:钢琴"

# 模糊搜索 — 在所有字段中匹配
python tools/tag.py search "钢琴 古典"

# 标签浏览 — 按分类列出所有标签
python tools/tag.py tags
```

搜索逻辑：将用户输入拆为多个词，每个词在所有歌曲的「歌名 + 艺人 + 专辑 + 标签」中匹配，按命中词数排序返回。

#### 全局发现搜索（借助 ncm-cli）

本地搜不到或需要更多结果时，模型自动拆解需求为多组关键词，并行调用 ncm-cli 搜索网易云全站：

```
用户需求 → 拆解为关键词（中文场景词/英文曲风/情绪词/年代词）
         → 并行搜索 playlist / album / song
         → 模型筛选 → 输出推荐
```

### 红心歌单同步（`sync.py`）

```
ncm-cli playlist tracks --playlistId <ID> --limit 100 --offset 0
ncm-cli playlist tracks --playlistId <ID> --limit 100 --offset 100
...
     ↓
对比本地 songs_db.json → 新歌自动查 MusicBrainz → 增量写入
     ↓
输出同步报告（新增/删除/未变）
```

---

## 使用示例

下面是一次完整的实操演示：**同步红心歌单 → 自动打标签 → 搜索相似歌曲**。

### 前置条件

- 已安装 ncm-cli 并登录
- 已设置 `NCM_LIKED_PLAYLIST_ID` 环境变量
- `python tools/sync.py` 已执行过（本地有 songs_db.json）

### 场景：我想找到红心歌单里那些「钢琴爵士」风格的歌

#### Step 1 — 同步最新红心歌单

```bash
$ python tools/sync.py

Fetching liked songs from ncm-cli...
  Looking up: Dreamer's Ball — Meg Birch
    -> 流派:爵士, 风格:jazz, 年代:2000
  Looking up: 海の見える街 — 広橋真紀子
    -> 流派:钢琴, 风格:piano, 年代:2009
  ...

=== Sync Report ===
  Total:  362 songs
  New:    5
  Unchanged: 357
```

每首新歌自动完成 MusicBrainz 查询（Tier 1），无需手动操作。

#### Step 2 — 批量补全标签（可选）

如果之前同步的歌还没标签，一次性补齐：

```bash
$ python tools/batch_tag.py

Found 120 songs to batch-tag (out of 362)
MusicBrainz rate limit: ~1 req/sec, ETA: ~2 min

[1/120] Fly Me To The Moon — Olivia Ong -> 流派:爵士, 风格:jazz, 年代:2005
[2/120] Autumn Leaves — Eric Clapton -> 流派:爵士, 风格:blues, 年代:2010
...
=== Batch Tag Complete ===
  Tagged:  105
  Skipped: 15
```

#### Step 3 — 搜索相似歌曲

```bash
# 按标签搜索
$ python tools/tag.py search "流派:爵士 器乐:钢琴"

Search "流派:爵士 器乐:钢琴": 23 results
  3* Fly Me To The Moon -- Olivia Ong [3:16]  [流派:爵士, 器乐:钢琴, 氛围:夜晚]
  3* Autumn Leaves -- Eric Clapton [5:42]  [流派:爵士, 器乐:钢琴, 年代:2010s]
  2* Misty -- Erroll Garner [2:46]  [流派:爵士, 器乐:钢琴, 情绪:浪漫]
  ...
```

#### Step 4 — 查看某首歌详情（含 MusicBrainz）

```bash
$ python tools/tag.py show "Fly Me To The Moon" --mb

  [7a2e8b...] Fly Me To The Moon
  Artist:   Olivia Ong
  Album:    Best of Olivia
  Duration: 3:16
  URL:      https://music.163.com/#/song?id=28692537
  Tags:
  流派:  爵士, 波萨诺瓦
  器乐:  钢琴
  氛围:  夜晚
  年代:  2005s

  --- MusicBrainz ---
  MB Genres: jazz, bossa nova
  MB Tags:   piano, vocal, lounge
  MB Year:   2005
  MB Score:  98
```

#### Step 5 — 全局发现（模型辅助）

在 Claude Code 中直接对话：

> 「帮我在网易云上找类似 Fly Me To The Moon 的歌，偏爵士钢琴女声的」

模型会拆解关键词（`jazz piano female vocal`、`爵士 女声 钢琴`），并行搜索歌单和专辑，筛选后给出推荐。

---

## 项目结构

```
netease-music-skills/
├── README.md
├── LICENSE
├── .gitignore
├── skills/
│   ├── ncm-cli-setup/              # 安装配置技能
│   │   ├── SKILL.md
│   │   └── scripts/install_mpv.py
│   └── music-curator/              # 标签管理 + 搜索技能
│       └── SKILL.md
└── tools/
    ├── sync.py                     # 红心歌单同步 + 自动标签
    ├── tag.py                      # 标签 CRUD + 搜索
    ├── batch_tag.py                # 全量 MusicBrainz 批量标注
    ├── musicbrainz.py              # MusicBrainz API 封装（30天缓存）
    └── init_db.py                  # 从原始数据初始化数据库
```

## 常见问题

| 问题 | 解决方法 |
|------|----------|
| `ncm-cli: command not found` | `npm install -g @music163/ncm-cli` |
| `mpv not found` | `python skills/ncm-cli-setup/scripts/install_mpv.py` |
| 登录超时 | `ncm-cli login --background` |
| `NCM_LIKED_PLAYLIST_ID not set` | `export NCM_LIKED_PLAYLIST_ID="你的32位hex歌单ID"` |
| tools 报找不到数据库 | 先执行 `python tools/sync.py` 同步红心歌单 |
| MusicBrainz 查不到 | 小众日本独立音乐约 12% 无数据，正常 |
| batch_tag.py 慢 | ~1 首/秒（API 限速），360 首约 6 分钟 |

## 许可证

[Apache License 2.0](LICENSE)
