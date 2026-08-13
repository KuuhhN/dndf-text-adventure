# 🗡️ DNDF 文字冒险

**LLM 驱动的 D&D 5e 跑团文字冒险游戏**（网页端）。

AI 地下城主实时生成剧情，玩家通过文字自由行动——但**所有骰子判定由规则引擎执行，LLM 永远不能自行造数**。

## ✨ 核心亮点

| 亮点 | 说明 |
|---|---|
| **两阶段协议（LLM 不能造数）** | 玩家行动 → LLM 决定是否判定 → 规则引擎执行掷骰/检定/攻击/伤害 → 真实结果注入 → LLM 据此写叙事。杜绝 AI 跑团最常见的「瞎编骰子」问题 |
| **function calling 工具层** | 6 个规则工具（roll_dice / ability_check / attack / encounter / enemy_attack / lookup），OpenAI 兼容 function calling 驱动 |
| **5e SRD 规则数据底座** | 本地导入 [5e-database](https://github.com/5e-bits/5e-database)（1488 条：9 种族/12 职业/319 法术/334 怪物/237 装备），SQLite 查询 |
| **完整游戏循环** | 角色创建（标准购点/骰点 + 技能选择）→ 自由冒险 → 遭遇战（敌人 HP 条）→ 击杀得经验 → 自动升级 |
| **幻觉防御** | 检测 LLM 文本假工具调用（"call attack(...)" 退化），后端强制执行 + 丢弃幻觉叙事 + 历史过滤 |
| **存档系统** | 角色卡 + 战斗状态 + 对话历史持久化，随时继续冒险 |

## 🏗️ 架构

```
┌─────────────┐   SSE 流式   ┌──────────────────────────┐   OpenAI 兼容   ┌──────────────┐
│  React 前端  │ ──────────► │  FastAPI 后端             │ ─────────────► │  OpenCode Go │
│  Vite + SSE  │ ◄────────── │  chat.py 两阶段协议引擎   │ ◄───────────── │  (kimi-k3)   │
└─────────────┘              │  tools.py 规则工具层      │                └──────────────┘
                             │  character.py 角色/升级   │
                             │  db.py / game.py (SQLite) │
                             └──────────────────────────┘
```

- **前端**：React 18 + Vite，SSE 流式渲染叙事，行动快捷按钮，实时角色卡/敌人 HP 条
- **后端**：FastAPI + httpx 异步流式代理 + SQLite
- **LLM**：OpenCode Go（OpenAI 兼容端点，默认 `kimi-k3`），可换任意 OpenAI 兼容模型

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

# 2. 启动后端（端口 8000）
python -m uvicorn app.main:app --port 8000

# 3. 启动前端（新终端，端口 5173）
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
| `LLM_MODEL` | `kimi-k3` | 模型名 |
| `LLM_PROXY` | `http://127.0.0.1:7890` | HTTP 代理 |
| `DNDF_DB` | `backend/data/dndf.db` | SQLite 路径 |

## 📡 API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/races` `/api/classes` | 种族/职业列表 |
| GET | `/api/class/{name}/skill-choices` | 职业可选熟练技能 |
| POST | `/api/character` | 创建角色（返回 session_id + 角色卡） |
| POST | `/api/chat` | SSE 流式对话（两阶段协议，事件：delta/tool/error） |
| GET | `/api/session/{id}` `/api/sessions` | 读档 / 存档列表 |

## 🧪 测试

```bash
cd backend && python -m pytest tests/ -v   # 40 个测试
```

覆盖：属性/修正/HP/AC 计算、4d6 骰点、技能熟练、升级（XP 阈值/熟练加值重算）、骰子数学、攻击命中/重击/击杀、遭遇战、敌人反击、两阶段协议工具往返、幻觉兜底、历史注入。

## 📜 许可证与数据合规

- 本项目代码：MIT（见 [LICENSE](LICENSE)）
- 规则数据：[5e-bits/5e-database](https://github.com/5e-bits/5e-database)（MIT），底层 D&D 5e SRD 内容依 **OGL 1.0a / CC-BY-4.0** 许可使用，仅使用 SRD 内容，不含 WotC Product Identity

## 🧠 技术要点（面试可讲）

1. **LLM × 工具调用 × 规则引擎**：function calling 两阶段协议，机械结果永不来自 LLM
2. **LLM 幻觉的工程防御**：文本假工具调用检测、强制重试、历史清洗——真实线上问题与解法
3. **SSE 流式全栈**：FastAPI 异步流式代理 + 浏览器 ReadableStream 解析
4. **数据工程**：5e SRD 1488 条数据导入与查询层设计
