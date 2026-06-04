---
name: music-curator
description: >
  网易云音乐智能策展助手。双模式搜索（本地标签库 + 全网易云发现）、
  歌曲标签管理（MusicBrainz + AI分析）、红心歌单同步。
  触发：用户想找歌、推荐歌、管理音乐收藏、分析歌曲风格时。
---

# 音乐策展助手 (Music Curator)

## 工具文件

| 文件 | 用途 |
|------|------|
| `tools/songs_db.json` | 歌曲数据库（360 首 JSON） |
| `tools/sync.py` | 同步：拉红心歌单 → 增量更新 + MusicBrainz 标注 |
| `tools/tag.py` | 标签管理：增删查改 |
| `tools/batch_tag.py` | 批量标注：全量 MusicBrainz 查询 |
| `tools/musicbrainz.py` | MusicBrainz API + 30 天缓存 |
| `tools/genre_db.py` | 风格数据库（qiaomu/RateYourMusic 5947 条） |

> **依赖**：`genre_db.py` 需要先安装 `qiaomu-music-player-spotify` 技能获取风格数据：
> ```bash
> npx qiaomu-music-player-spotify
> ```
> 仅需风格 DB（`~/.claude/skills/qiaomu-music-player-spotify/references/`），不需要 Spotify API。

---

## 第一条：意图识别

收到搜索/推荐请求后，**先问**：

> 先搜你的本地歌单（360 首），还是搜索网易云全站？[本地/全局/都要]

- **本地** → 流程 A：标签库搜索
- **全局** → 流程 B：多关键词发现搜索
- **都要** → 先本地，再全局

若用户已明确指定范围（如"在我歌单里找"、"网易云上搜"），则直接进入对应流程，不询问。

---

## 流程 A：本地标签库搜索

```
用户描述 → 拆解为标签关键词 → tag.py search → 人工补充 → 输出
```

### A1. 结构化搜索

```bash
python tools/tag.py search "流派:爵士 器乐:钢琴"
python tools/tag.py search "情绪:浪漫 氛围:夜晚"
python tools/tag.py search "钢琴 古典"               # 模糊搜索
python tools/tag.py list --tag "动漫OST"               # 按标签列
python tools/tag.py tags                                # 标签统计
```

### A2. 标签稀疏 → 推理发现闭环

**触发条件**：标签搜索返回 < 3 条结果时，说明标签库对该维度覆盖不足，**不允许直接结束**，必须进入以下闭环：

```
标签搜索（结果<3）→ 多维度推理发现 → 标签补全 → 重新搜索验证
```

#### A2a. 多维度推理发现

不依赖现有标签，用以下信号在本地 DB 中推理候选歌曲：

```
维度1: 艺人背景
   已知萨克斯主导的艺人/乐队：
     John Coltrane、SOIL & "PIMP" SESSIONS、BLU-SWING、JABBERLOOP、
     Spyro Gyra、椎名林檎(+SOIL)
   已知钢琴主导：Bill Evans、Ahmad Jamal、広橋真紀子
   已知吉他主导：Cory Wong、Andy McKee、Polyphia

维度2: 风格/流派推理
   硬波普(hard bop) → 萨克斯标志主奏
   爆裂爵士(death jazz) → 萨克斯+激进鼓
   爵士嘻哈(jazz hip-hop) → 萨克斯+采样
   后摇(post-rock) → 吉他主导
   氛围(ambient) → 合成器/电子

维度3: 器乐来源推断
   来源:器乐演奏 + 地域:日本 + 爵士风格 → 大概率萨克斯/钢琴
   来源:动漫OST + 器乐演奏 → 大概率钢琴/弦乐

维度4: 歌名/专辑关键词
   sax、saxophone、萨克斯、bop、swing、big band
```

#### A2b. 标签补全（直接写 DB）

推理出候选人后，**直接操作 JSON 补全标签**（不经过 tag.py 的替换逻辑，保证多值追加）：

```python
# 示例：给 Coltrane 歌曲追加器乐:萨克斯 + 子流派
python -c "
import json
with open('tools/songs_db.json') as f:
    db = json.load(f)
for s in db['songs']:
    if 'John Coltrane' in str(s['artists']):
        # 追加而非替换
        for t in ['器乐:萨克斯', '流派:硬波普', '流派:莫代尔爵士']
            if t not in s['tags']:
                s['tags'].append(t)
...
"
```

#### A2c. 重新搜索验证

补全后重新 `tag.py search`，确认搜索结果 ≥3 条，再将结果输出给用户。

---

### A3. 结构化搜索

```bash
python tools/tag.py search "流派:爵士 器乐:钢琴"
python tools/tag.py search "情绪:浪漫 氛围:夜晚"
python tools/tag.py search "钢琴 古典"               # 模糊搜索
python tools/tag.py list --tag "动漫OST"               # 按标签列
python tools/tag.py tags                                # 标签统计
```

## 流程 B：全局发现搜索

**核心策略：将自然语言需求分解为多组关键词，并行搜索，模型筛选。**

### B1. 关键词分解（模型判断）

```
用户需求 → 拆解为多种搜索关键词

维度：
  ├─ 中文场景词: "深夜" "咖啡厅" "公路" "专注"
  ├─ 英文曲风标签: "ambient" "jazz" "bossa nova" "post-rock"
  ├─ 情绪词: "放松" "燃" "温暖" "忧郁"
  ├─ 年代/地域: "90年代" "日系" "法语"
  ├─ 用途/场景: "跑步" "学习" "通勤" "睡前"
  └─ 类比: "像坂本龙一" "类似Nujabes"
```

### B2. 执行搜索（并行 2~4 次）

```bash
ncm-cli search playlist --keyword "关键词组合1"
ncm-cli search playlist --keyword "关键词组合2"
ncm-cli search album --keyword "关键词组合3"
ncm-cli search song --keyword "关键词组合4"
```

**搜索策略**：
- 描述心情/场景 → 优先 `search playlist`（歌单标题匹配度最高）
- 找特定风格/艺人 → 优先 `search album` 或 `search song`
- 电影/动漫/游戏原声 → 优先 `search album`

### B3. 筛选（模型判断）

1. **排除**：用户在网易云已收藏的歌单/专辑
2. **匹配度评估**：名称语义 + 标签 + 描述 vs 用户需求
3. **质量考量**：播放量 (playCount)、曲目数 (trackCount)、封面质量
4. 选出 **4~6 条**最佳结果

### B4. 输出格式（每一条）

```
🎵 音乐推荐 · [时间戳]

  ① 🎶 [歌单/专辑/单曲名]
     ⭐ 评分：[0-100]
     📝 理由：
       偏好关联：[引用用户红心艺人/曲风/偏好，说明为什么推荐]
       内容特质：[描述该资源的核心亮点与适配场景]
     🔗 https://music.163.com/#/playlist?id=[明文ID]
```

**强制规则**：
- 链接中的 ID **必须用明文 originalId（数字）**，禁止加密 ID
- 每条推荐必须有两层理由（40~80 字合计）
- 如果结果包含 `coverImgUrl`，可选输出 `🖼️ <url>`
- 如果搜索结果是单曲，提供创建歌单的选项

---

## 流程 C：同步 + 分析

### C1. 同步新歌

```bash
python tools/sync.py
```

拉取红心歌单 → 对比本地 → 新歌自动查 MusicBrainz → 输出报告。
用户说「同步歌曲」时执行。

### C2. 用户描述分析

用户描述某首歌的感受时：

1. 先查已有标签 + MB：`python tools/tag.py show "歌名" --mb`
2. 按五维度生成标签建议：
   - **情绪**: 浪漫/忧郁/梦幻/慵懒/温暖/怀旧/典雅/积极/…
   - **流派**: 爵士/古典/电子/摇滚/灵魂/嘻哈/…
   - **器乐**: 钢琴/弦乐/萨克斯/人声/鼓/贝斯/吉他/…
   - **氛围**: 夜晚/水边/都市/宫廷/电影感/游戏感/…
   - **节奏**: 快速/中速/慢速/摇摆律动/自由/…
3. **展示推理 → 用户确认 → 写入**

```bash
python tools/tag.py add "歌名" --tags "情绪:浪漫, 流派:波萨诺瓦, 器乐:萨克斯, 器乐:人声, 氛围:水边, 氛围:夜晚, 节奏:中慢速"
```

同一分类下的标签自动替换旧值。

---

## 流程 D：风格数据库查询与标签增强

利用 qiaomu 技能的 5947 条 RateYourMusic 风格数据库，增强标签质量和搜索能力。

### D1. 风格查询

```bash
# 查看风格详情（英文名）
python tools/genre_db.py lookup "Hard Bop"
# → 返回：描述、父分类、子分类、RYM链接

# 查看某分类下的所有子风格
python tools/genre_db.py children "Jazz"
# → 返回 38 个爵士子分类及描述

# 中文标签 → 英文风格匹配
python tools/genre_db.py match "硬波普"
# → 返回：RYM 中的对应风格、描述、连接
```

### D2. 搜索关键词扩展

当标签搜索返回结果少时，用 genre_db 扩展搜索词：

```bash
# 中文标签 → 一组英文/中文搜索关键词
python tools/genre_db.py expand "硬波普"
# → ["hard bop", "bebop", "bluesy jazz", "saxophone jazz", "art blakey", ...]
```

然后用这些关键词去 ncm-cli 做全局搜索：

```bash
ncm-cli search playlist --keyword "hard bop saxophone jazz"
ncm-cli search playlist --keyword "art blakey jazz messengers"
```

### D3. 标签增强写入

对于已有「流派」标签的歌曲，用 genre_db 补充：

1. **查风格描述** → 写入 DB 的注释字段或作为展示用
2. **补充英文风格名** → `流派:Hard Bop` 追加到中文标签旁
3. **关联子风格** → 如果 RYM 有子分类，补充为候选标签
4. **未匹配标签也要保留** → `爆裂爵士` 是个人理解，虽然 RYM 没有，但它描述了你对 SOIL & "PIMP" SESSIONS 的感受，不删除

### D4. 风格浏览发现

当用户想拓展音乐视野时：

```
用户：「爵士下面有什么分支？我想发现新类型」
  → genre_db.py children "Jazz" → 列出 38 个子分类
  → 用户选「Dark Jazz 是什么样的？」
  → genre_db.py lookup "Dark Jazz" → 描述 + 子分类
  → 推荐艺人/歌单（模型知识 + 搜索）
```

---

### C3. 批量打标签

```bash
python tools/batch_tag.py
```

遍历所有无标签歌曲，查 MusicBrainz。~350 首约 6 分钟。

### C4. 查看歌曲

```bash
python tools/tag.py show "关键词"
python tools/tag.py show "关键词" --mb    # 含 MusicBrainz
```

---

## 标签体系

### 格式：`分类:值`

| 分类 | 示例 | 来源 | 写入策略 |
|------|------|------|----------|
| `流派:` | 硬波普, 爆裂爵士, 爵士嘻哈 | MusicBrainz + 推理 | **追加** — 一首歌可有多个子流派 |
| `器乐:` | 钢琴, 萨克斯, 人声, 弦乐 | 用户 + AI | **追加** — 一首歌可有多种乐器 |
| `情绪:` | 浪漫, 梦幻, 慵懒, 温暖 | 用户 → AI | **替换** — 同一时段主导情绪只有一个 |
| `氛围:` | 夜晚, 水边, 爵士酒吧, 都市夜 | 用户 → AI | **追加** — 可同时适配多个场景 |
| `节奏:` | 中慢速, 中快速, 摇摆律动 | 用户 / 推理 | **替换** — 一首歌只有一个主节奏 |
| `风格:` | jazz-funk, ambient, post-rock | MusicBrainz 原始 | **追加** — MB 英文标签原样保留 |
| `年代:` | 2020s, 1998s | MusicBrainz | **替换** |
| `来源:` | 动漫OST, 电影OST, 器乐演奏 | MusicBrainz + 推理 | **追加** |
| `地域:` | 日本, 华语 | 推理 | **替换** |

### 标签写入策略（重要！）

**追加 vs 替换**：
- 多值维度（`流派`、`器乐`、`氛围`、`来源`、`风格`）→ **追加**，直接用 Python 操作 JSON
- 单值维度（`情绪`、`节奏`、`年代`、`地域`）→ **替换**，可用 `tag.py add`

**流派必须细化到子分类**，禁止只写"爵士"：

| 泛标签 ❌ | 细化标签 ✅ | 说明 |
|-----------|------------|------|
| 流派:爵士 | 流派:硬波普 | 50s末兴起的蓝调+波普，萨克斯主导 |
| | 流派:莫代尔爵士 | 基于音阶而非和弦进行，Coltrane标志 |
| | 流派:爆裂爵士 | 日本地下，高速+激进+萨克斯咆哮 |
| | 流派:爵士嘻哈 | 爵士采样+嘻哈鼓点，Nujabes/JABBERLOOP |
| | 流派:爵士流行 | 流行结构+爵士编曲，BLU-SWING |
| | 流派:融合爵士 | 爵士+摇滚/放克，Spyro Gyra |
| | 流派:灵魂爵士 | 福音+蓝调+硬波普 |
| | 流派:平滑爵士 | 商业化器乐流行爵士 |
| | 流派:酸性爵士 | 电子+放克+爵士 |
| | 流派:自由爵士 | 无调性即兴，Coltrane晚期 |

**标签可附带简短说明**：写入时用分类:值格式，但在向用户展示时可以用自然语言解释标签含义。

### `tag.py` 命令行

```bash
python tools/tag.py search "流派:爆裂爵士"            # 搜子流派
python tools/tag.py search "流派:爵士嘻哈 器乐:萨克斯"   # 组合搜索
python tools/tag.py tags                              # 标签统计
python tools/tag.py list --tag "流派:硬波普"            # 按标签列出歌曲
python tools/tag.py show "歌名" --mb                   # 歌曲详情+MusicBrainz
```

> **注意**：`tag.py add` 会替换同分类下的旧值，多值标签（流派/器乐/氛围）请直接操作 JSON 追加。

### 标签分级

| 级别 | 来源 | 处理 |
|------|------|------|
| Tier 1 | MusicBrainz | 自动写入，不打扰 |
| Tier 2 | 推理（地域/来源/时长） | 自动写入，不打扰 |
| Tier 3 | 用户描述 + AI 分析 | **展示推理 → 确认 → 写入** |

批量导入时 Tier 1+2 全自动；Tier 3 仅在用户主动描述时触发。

---

## 环境要求

- Python 3.8+
- ncm-cli（已安装并登录，参考 ncm-cli-setup skill）
- mpv（可选，用于播放）
- MusicBrainz：免费 API，无需 Key，30 天缓存
- 首次使用请设置环境变量并同步：
  ```bash
  export NCM_LIKED_PLAYLIST_ID="你的红心歌单ID"
  python tools/sync.py
  ```

## 限制

- 网易云 API 不返回流派/风格 → MusicBrainz 补充（小众日本独立 ~12% 无数据）
- 情绪/氛围/器乐 需用户主动描述
- Windows Python subprocess 需 `encoding='utf-8'` + 强制 UTF-8 stdout
