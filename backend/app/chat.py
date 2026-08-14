"""游戏对话引擎：两阶段协议。

阶段一：LLM 收到玩家行动后，如需机械判定则调用规则工具（roll/ability_check/attack/lookup）；
阶段二：后端执行工具并把结果注入对话，LLM 依据真实结果写叙事。
LLM 永远不能自行编造骰子结果。
"""
import json
from typing import AsyncIterator

from . import game, tools
from .llm import stream_chat

MAX_TOOL_ROUNDS = 4

# 攻击意图关键词（后端兜底检测）
ATTACK_INTENT = ("攻击", "挥剑", "砍", "刺", "劈", "斩", "杀", "打", "射", "放箭", "冲锋")


def build_system_prompt(character: dict) -> str:
    return f"""你是《龙与地下城 5e》文字冒险游戏的地下城主（DM）。你负责叙事，玩家负责行动。

## 世界观
剑与魔法的大陆「艾瑟兰」，冒险者公会、悬赏告示、幽暗地牢与龙语传说交织。
开篇场景：醉龙酒馆——冒险者们聚集的起点。随着剧情推进，场景自由展开。

## 铁律
1. 玩家行动需要判定成败时（潜行/攀爬/说服/察觉/开锁/追踪/搜索/威吓/哄骗等），
   必须先调用 ability_check 工具，拿到真实结果后才能叙述成败。严禁直接叙述成功或失败。
2. 攻击怪物必须用 attack 工具（含命中与伤害）；掷任意骰子用 roll_dice；需要怪物/法术/装备数据用 lookup。
3. 玩家使用主动能力（二次呼吸/狂暴/吐息武器/圣疗/吟游激励/狡诈行动）时，
   必须调用 use_feature 工具，引擎结算效果并扣次数；叙事以工具结果为准。
4. 严禁自行编造骰子结果、伤害数值或技能成功与否——所有判定结果以工具返回为准。
4. 叙事中出现任务/悬赏/委托（告示板、委托信、NPC 委托等）时，必须调用 post_quest 工具
   把任务注册到告示栏（title/description/reward/status）。玩家接下任务后，用
   post_quest(status="accepted") 更新状态。
5. 玩家获得/拾取/购买/搜刮到物品时，必须调用 add_item 入背包；消耗/使用/丢弃/交出物品时
   必须调用 remove_item。物品数量以引擎状态为准，严禁在叙事中自行增减。
6. 用中文叙事，第二人称"你"，营造 D&D 奇幻冒险氛围。叙事简洁但生动，一次 2-4 句话。
7. 只有玩家明确说要攻击时才算战斗；普通对话不主动攻击。

## 叙事风格
- 多用感官细节（光影、气味、声响），让场景活起来；对话中的 NPC 要有鲜明个性。
- 每段叙事末尾，可以给玩家 1-3 个可选的行动方向（用「你可以：」引导），但不要强迫。
- 玩家第一次行动前，先描绘酒馆场景与当前可做的事，等待玩家选择。

## 战斗规则
- 战斗状态（敌人 HP、玩家 HP、敌人数量）由引擎维护，以 combat 列表为准，叙事必须与之一致。
- 战斗中的每一轮：玩家攻击必须调用 attack；敌人行动必须调用 enemy_attack（每只存活敌人各一次）。
- 新敌人出现必须调用 encounter 拉入战斗，禁止在叙事中凭空描述敌人状态变化。
- 敌人死亡/逃跑等状态变化只能发生在工具调用之后（引擎返回 killed/剩余列表），禁止自行宣布。
- 玩家 HP 归零时（player_dead=true）必须立即宣布玩家倒下，故事进入败局收尾。

## 当前角色卡
{json.dumps(character, ensure_ascii=False)}
"""


async def game_chat(session_id: str, message: str) -> AsyncIterator[dict]:
    """一轮游戏对话：返回事件流（delta=叙事文本 / tool=工具结果 / error）。"""
    session = game.get_session(session_id)
    if not session:
        yield {"type": "error", "text": "会话不存在"}
        return
    character = session["character"]

    messages = [{"role": "system", "content": build_system_prompt(character)}]
    for h in session["history"][-12:]:  # 最近 12 条历史
        if h["role"] in ("user", "assistant"):
            # 过滤 LLM 幻觉写进文本的假工具调用（如 "call attack(...)"）
            content = h["content"]
            if "call " in content and any(
                f"call {t}(" in content for t in ("attack", "ability_check", "roll_dice", "enemy_attack", "encounter", "lookup", "use_feature")
            ):
                continue
            messages.append({"role": h["role"], "content": content})
    messages.append({"role": "user", "content": message})

    assistant_text = ""
    forced = False  # 后端强制攻击只触发一次
    for _round in range(MAX_TOOL_ROUNDS):
        calls = []
        texts = []
        async for event in stream_chat(messages, tools=tools.TOOLS, max_tokens=700):
            if event["type"] == "delta":
                texts.append(event["text"])
            elif event["type"] == "tool_call":
                calls.append(event["call"])
        if calls:
            # 工具调用：执行并注入结果
            messages.append({
                "role": "assistant",
                "content": "".join(texts) or None,
                "tool_calls": [
                    {"id": c["id"], "type": "function",
                     "function": {"name": c["name"], "arguments": c["arguments"]}}
                    for c in calls
                ],
            })
            for call in calls:
                try:
                    args = json.loads(call["arguments"] or "{}")
                except json.JSONDecodeError:
                    args = {}
                result = tools.execute_tool(call["name"], args, character)
                messages.append(tools.tool_result_message(call, result))
                yield {"type": "tool", "call": {"name": call["name"], "arguments": call["arguments"]}, "result": result}
            game.update_character(session_id, character)  # 工具副作用（战斗状态/经验）持久化
            continue
        # 无工具调用：检测"战斗攻击意图但 LLM 没调工具"（幻觉/退化），后端强制攻击一次
        if not forced:
            enemies = tools._combat(character)["enemies"]
            if enemies and any(k in message for k in ATTACK_INTENT):
                forced = True
                target = enemies[0]["name"]
                result = tools.attack(character, target)
                game.update_character(session_id, character)
                yield {"type": "tool", "call": {"name": "attack", "arguments": json.dumps({"target": target}, ensure_ascii=False)}, "result": result}
                # 丢弃幻觉文本，注入引擎真实结果，要求重新叙事
                messages.append({
                    "role": "user",
                    "content": f"（引擎已判定你的攻击：{json.dumps(result, ensure_ascii=False)}。"
                               f"请忽略你上一段未调用工具的叙述，严格依据这个真实结果重新叙事。）",
                })
                continue
        assistant_text += "".join(texts)
        break
    else:
        if not assistant_text:  # 超限且无叙事：至少提示工具已执行
            yield {"type": "error", "text": "行动判定过多，请稍后再试"}
        # 有叙事则正常输出（工具结果已由 tool 事件展示）

    if assistant_text:
        yield {"type": "delta", "text": assistant_text}

    # 持久化对话历史（供存档与上下文）
    game.append_history(session_id, "user", message)
    if assistant_text:
        game.append_history(session_id, "assistant", assistant_text)
