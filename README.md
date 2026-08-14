# 🗡️ DNDF 文字冒险

**LLM 驱动的 D&D 5e 跑团文字冒险游戏**（网页端）。

AI 地下城主实时生成剧情，玩家通过文字自由行动——但**所有骰子判定由规则引擎执行，LLM 永远不能自行造数**。

## ✨ 核心亮点

| 亮点 | 说明 |
|---|---|
| **两阶段协议（LLM 不能造数）** | 玩家行动 → LLM 决定是否判定 → 规则引擎执行掷骰/检定/攻击/伤害 → 真实结果注入 → LLM 据此写叙事。杜绝 AI 跑团最常见的「瞎编骰子」问题 |
| **function calling 工具层（11 个）** | roll_dice / ability_check / attack / encounter / enemy_attack / lookup / post_quest / add_item / remove_item / use_feature，OpenAI 兼容 function calling 驱动 |
| **BG3 式 6 步创建向导** | 种族 → 职业 → 属性（标准购点 27 点严格按 PHB 花费表 / 4d6 骰点）→ 技能 → 专长·背景（2024 SRD）→ 名字；每步可查看中文特性详情 |
| **5e SRD 规则数据底座** | 本地导入 [5e-database](https://github.com/5e-bits/5e-database)（2014 SRD + 2024 专长/背景，共 1870 条），SQLite 查询；117 条规则描述由 LLM 生成「一句话剧本用途」中文摘要 |
| **技能栏位系统（用了即消耗）** | ⚡可用能力栏（二次呼吸/狂暴/吐息武器/圣疗/吟游激励/狡诈行动）：动作类型 + 次数徽章（×N·短休/长休），引擎结算效果并扣减次数，耗尽灰态「已用完」；🎯技能面板 18 技能一句话用途 + 点击即用 |
| **完整游戏循环** | 角色创建 → 自由冒险 → 遭遇战（敌人 HP 条）→ 击杀得经验 → 自动升级（新特性随等级解锁） |
| **幻觉防御** | 检测 LLM 文本假工具调用（"call attack(...)" 退化），后端强制执行 + 丢弃幻觉叙事 + 历史过滤 |
| **存档系统** | 角色卡 + 战斗状态 + 对话历史持久化，主页「继续冒险」随时读档 |
| **任务告示栏** | LLM 叙事出现悬赏/委托时通过 post_quest 工具注册到引擎状态，前端以「告示板便条」呈现（赏金徽章 / 已接下 / 悬赏中） |
| **羊皮纸桌游风 UI** | 深橡木桌面 + 羊皮纸角色卡 + 图钉任务便条 + 金色描边 + 楷体标题，界面全中文 |

## 🏗️ 架构

```
┌─────────────┐   SSE 流式   ┌──────────────────────────┐   OpenAI 兼容   ┌──────────────┐
│  React 前端  │ ──────────► │  FastAPI 后端             │ ─────────────► │  OpenCode Go │
│  Vite + SSE  │ ◄────────── │  chat.py 两阶段协议引擎   │ ◄───────────── │ (deepseek-v4 │
└─────────────┘              │  tools.py 规则工具层      │                │  -flash)     │
                             │  character.py 角色/升级   │                └──────────────┘
                             │  db.py / game.py (SQLite) │
                             └──────────────────────────┘
```

- **前端**：React 18 + Vite，SSE 流式渲染叙事，行动快捷按钮，实时角色卡/敌人 HP 条/技能栏/任务告示/背包
- **后端**：FastAPI + httpx 异步流式代理 + SQLite
- **LLM**：OpenCode Go（OpenAI 兼容端点，默认 `deepseek-v4-flash`，可 `LLM_MODEL=kimi-k3` 换叙事质量更高的模型）

## 🚀 快速启动

### 前置
- Python 3.11+，Node 18+
- LLM API Key：设置环境变量 `LLM_API_KEY`（或放在 `%APPDATA%/reasonix/.env` 的 `OPENCODE_GO_API_KEY`）
- 代理（可选，OpenCode Go 需能访问 opencode.ai，默认代理 `http://127.0.0.1:7890`，可用 `LLM_PROXY` 覆盖）

### 步骤

```bash
# 1. 导入 5e 规则数据（首次）
cd backend
pip install -r requirements.txt
python scripts/import_5e.py

# 2. 可选：批量翻译规则描述为中文（117 条一句话剧本用途，断点续跑）
python scripts/translate_srd.py --summary

# 3. 启动后端（端口 8000）
python -m uvicorn app.main:app --port 8000

# 4. 启动前端（新终端，端口 5173）
cd frontend
npm install
npm run dev
```

浏览器打开 http://localhost:5173 → 创建角色 → 开始冒险 🎲

## 🔧 配置（环境变量）

| 变量 | 默认值 | 说明 |
|---|---|---|
| `LLM_API_KEY` | 读取 `%APPDATA%/reasonix/.env` | API Key |
| `LLM_BASE_URL` | `https://opencode.ai/zen/go/v1` | OpenAI 兼容端点 |
| `LLM_MODEL` | `deepseek-v4-flash` | 模型名 |
| `LLM_PROXY` | `http://127.0.0.1:7890` | HTTP 代理 |
| `DNDF_DB` | `backend/data/dndf.db` | SQLite 路径 |

## 📡 API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/races` `/api/classes` | 种族/职业列表 |
| GET | `/api/races/{name}` `/api/classes/{name}` | 详情（中文特性一句话 + 完整规则） |
| GET | `/api/feats` `/api/backgrounds` | 1 级可选专长 / 背景（2024 SRD） |
| GET | `/api/roll-abilities` | 4d6 骰点预览 |
| POST | `/api/character` | 创建角色（point-buy 严格校验 27 点/8-15，返回 session_id + 角色卡） |
| POST | `/api/chat` | SSE 流式对话（两阶段协议，事件：delta/tool/error） |
| GET | `/api/session/{id}` `/api/sessions` | 读档 / 存档列表 |

## 🧪 测试

```bash
cd backend && python -m pytest tests/ -v   # 63 个测试
```

覆盖：属性/修正/HP/AC 计算、严格购点校验（27 点预算/范围）、4d6 骰点、技能熟练、升级（XP 阈值/熟练加值重算/2 级解锁狡诈行动）、骰子数学、攻击命中/重击/击杀（同名敌人逐只结算）、遭遇战、敌人反击、两阶段协议工具往返、幻觉兜底、历史注入、主动能力（二次呼吸回血/圣疗池不超支/狂暴伤害+2 与战斗结束重置/吐息豁免）。

## 📜 许可证与数据合规

- 本项目代码：MIT（见 [LICENSE](LICENSE)）
- 规则数据：[5e-bits/5e-database](https://github.com/5e-bits/5e-database)（MIT），底层 D&D 5e SRD 内容依 **OGL 1.0a / CC-BY-4.0** 许可使用，仅使用 SRD 内容，不含 WotC Product Identity

## 🧠 技术要点（面试可讲）

1. **LLM × 工具调用 × 规则引擎**：function calling 两阶段协议，机械结果永不来自 LLM
2. **LLM 幻觉的工程防御**：文本假工具调用检测、强制重试、历史清洗——真实线上问题与解法
3. **规则引擎的边界设计**：主动能力白名单（FEATURE_ACTIONS）由引擎结算次数与效果，LLM 只负责叙事；升级/战斗结束自动维护状态机
4. **SSE 流式全栈**：FastAPI 异步流式代理 + 浏览器 ReadableStream 解析
5. **数据工程**：5e SRD 1870 条数据导入与查询层设计 + LLM 批量翻译（断点续跑）流水线
