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

### A2. 人工补充

MusicBrainz 覆盖了流派/年代/来源，但情绪/氛围/器乐标签较少。搜索时需结合对歌单的已知知识手动补充高质量结果。

---

## 流程 B：全局发现搜索

**核心策略：将自然语言需求分解为多组关键词，并行搜索，模型筛选。** 
（借鉴自 netease-music-assistant 的搜索策略）

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

| 分类 | 示例 | 来源 |
|------|------|------|
| `情绪:` | 浪漫, 梦幻, 慵懒, 温暖 | 用户 → AI |
| `流派:` | 爵士, 古典, 电子, 灵魂 | MusicBrainz |
| `器乐:` | 钢琴, 萨克斯, 人声, 弦乐 | 用户 → AI |
| `氛围:` | 夜晚, 水边, 宫廷风, 电影感 | 用户 → AI |
| `节奏:` | 中慢速, 中快速, 摇摆律动 | 用户 / 推理 |
| `年代:` | 2020s, 1998s | MusicBrainz |
| `来源:` | 动漫OST, 电影OST, 器乐演奏 | MusicBrainz + 推理 |
| `地域:` | 日本, 华语 | 推理 |
| `风格:` | jazz-funk, ambient, post-rock | MusicBrainz 原始 |

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
