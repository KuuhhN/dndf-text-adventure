"""游戏对话引擎（两阶段协议）测试：mock LLM，验证工具循环与历史持久化。"""
import asyncio
import sys
import os
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import game
from app.chat import build_system_prompt, game_chat
from app.character import create_character


def _make_session():
    c = create_character("测试者", "Human", "Fighter", chosen_skills=["Athletics", "Perception"])
    return game.create_session("测试者", c)


def test_system_prompt_contains_character_and_rules():
    c = create_character("T", "Human", "Fighter")
    p = build_system_prompt(c)
    assert "Fighter" in p
    assert "ability_check" in p and "attack" in p  # 工具指引
    assert "严禁" in p  # 铁律


def _fake_stream_with_tool_then_text():
    """第一轮返回 attack 工具调用，第二轮返回叙事文本。"""
    calls = {"n": 0}

    async def fake(messages, tools=None, max_tokens=900):
        calls["n"] += 1
        if calls["n"] == 1:
            yield {"type": "tool_call", "call": {
                "id": "c1", "name": "attack", "arguments": '{"target": "Goblin"}'}}
        else:
            yield {"type": "delta", "text": "你挥剑斩向哥布林，剑刃划破空气！"}

    return fake


def test_game_chat_tool_round_trip():
    """攻击全流程：LLM 请求工具 -> 引擎执行 -> 结果注入 -> 叙事。"""
    sid = _make_session()

    async def run():
        with patch("app.chat.stream_chat", _fake_stream_with_tool_then_text()):
            return [e async for e in game_chat(sid, "攻击哥布林")]

    events = asyncio.run(run())
    types = [e["type"] for e in events]
    assert "tool" in types and "delta" in types

    # state 事件：in_combat 与引擎最终战斗状态一致（骰子可能击杀清场 → False）
    from app import game as _game
    state_evt = next(e for e in events if e["type"] == "state")
    assert state_evt["in_combat"] == bool(
        _game.get_session(sid)["character"].get("combat", {}).get("enemies"))

    tool_evt = next(e for e in events if e["type"] == "tool")
    assert tool_evt["call"]["name"] == "attack"
    assert tool_evt["call"]["arguments"] == '{"target": "Goblin"}'
    assert "hit" in tool_evt["result"]  # 真实执行了 attack（与骰子一致）
    assert "target_ac" in tool_evt["result"]

    text = "".join(e["text"] for e in events if e["type"] == "delta")
    assert "挥剑" in text

    # 历史持久化：user + assistant 各一条
    s = game.get_session(sid)
    assert [h["role"] for h in s["history"]] == ["user", "assistant"]


def test_game_chat_no_tool_plain_narrative():
    """普通对话：无工具调用，直接叙事。"""
    sid = _make_session()
    calls = {"n": 0}

    async def fake(messages, tools=None, max_tokens=900):
        calls["n"] += 1
        yield {"type": "delta", "text": "酒馆里炉火正旺。"}

    async def run():
        with patch("app.chat.stream_chat", fake):
            return [e async for e in game_chat(sid, "我环顾酒馆")]

    events = asyncio.run(run())
    # delta 叙事 + state 行动状态（战斗标志）
    assert [e["type"] for e in events] == ["delta", "state"]
    assert calls["n"] == 1  # 只请求一次


def test_game_chat_missing_session():
    async def run():
        return [e async for e in game_chat("nope", "你好")]

    events = asyncio.run(run())
    assert events[0]["type"] == "error"


def test_game_chat_history_used_in_messages():
    """历史应注入下一轮对话（最近 12 条）。"""
    sid = _make_session()
    game.append_history(sid, "user", "上一轮的问题")
    game.append_history(sid, "assistant", "上一轮的回应")
    captured = {}

    async def fake(messages, tools=None, max_tokens=900):
        captured["messages"] = messages
        yield {"type": "delta", "text": "ok"}

    async def run():
        with patch("app.chat.stream_chat", fake):
            await anext(game_chat(sid, "继续"))

    asyncio.run(run())
    roles = [m["role"] for m in captured["messages"]]
    assert roles == ["system", "user", "assistant", "user"]
    assert captured["messages"][1]["content"] == "上一轮的问题"


def test_game_chat_forced_attack_fallback():
    """LLM 幻觉退化（纯文本假工具调用）时：后端强制攻击一次，幻觉文本被丢弃。"""
    sid = _make_session()
    s = game.get_session(sid)
    s["character"]["combat"]["enemies"].append({"name": "Goblin", "max_hp": 7, "hp": 7, "ac": 15})
    game.update_character(sid, s["character"])

    calls = {"n": 0}

    async def fake(messages, tools=None, max_tokens=900):
        calls["n"] += 1
        if calls["n"] == 1:
            yield {"type": "delta", "text": 'call attack(target="Goblin") 的结果：命中！伤害 20！'}
        else:
            yield {"type": "delta", "text": "你一剑刺中哥布林！"}

    async def run():
        with patch("app.chat.stream_chat", fake):
            return [e async for e in game_chat(sid, "我挥剑攻击哥布林！")]

    events = asyncio.run(run())
    types = [e["type"] for e in events]
    assert types.count("tool") == 1  # 只强制一次
    tool_evt = next(e for e in events if e["type"] == "tool")
    assert tool_evt["call"]["name"] == "attack"
    assert "hit" in tool_evt["result"]  # 真实引擎结果
    texts = "".join(e["text"] for e in events if e["type"] == "delta")
    assert "call attack" not in texts  # 幻觉文本未展示
    # 历史中的幻觉消息也被过滤（下一轮不再污染）
    s2 = game.get_session(sid)
    assert not any("call attack" in h["content"] for h in s2["history"])


def test_game_chat_empty_return_gets_error():
    """LLM 空返回（不抛错）：必须发 error 提示，绝不静默（静默=「没剧情」假象）。"""
    sid = _make_session()

    async def fake(messages, tools=None, max_tokens=900):
        return
        yield  # 使其成为 async 生成器（空迭代），模拟 LLM 空返回不抛错

    async def run():
        with patch("app.chat.stream_chat", fake):
            return [e async for e in game_chat(sid, "冒险开始！")]

    events = asyncio.run(run())
    errors = [e for e in events if e["type"] == "error"]
    assert errors, "空返回必须出现 error 事件"
    assert "模型无返回" in errors[0]["text"]
    assert [e["type"] for e in events][-1] == "state"  # 行动状态仍正常补发


def test_game_chat_unexpected_error_gets_error():
    """未预期异常冒泡：兜底 except 发 error，不静默断流。"""
    sid = _make_session()

    async def fake(messages, tools=None, max_tokens=900):
        raise RuntimeError("boom")
        yield  # 使其成为真 async 生成器：异常在迭代中抛出（非协议层 TypeError）

    async def run():
        with patch("app.chat.stream_chat", fake):
            return [e async for e in game_chat(sid, "继续")]

    events = asyncio.run(run())
    errors = [e for e in events if e["type"] == "error"]
    assert errors, "未预期异常必须兜底发 error"
    assert "DM 失联" in errors[0]["text"]
    assert [e["type"] for e in events].count("state") == 1  # state 恰好一次


def test_system_prompt_injects_location_and_neighbors():
    """当前位置注入：LLM 每轮知道所在区域与邻接可达区域（防叙事地点与地图脱节）。"""
    from app.chat import build_system_prompt
    from app.character import create_character
    c = create_character("LocTest", "Human", "Fighter", start_location="capital")
    prompt = build_system_prompt(c)
    assert "当前位置" in prompt
    assert "王都艾瑟兰" in prompt
    # 邻接区域中文名全部注入
    for name in ("狮鹫酒馆", "矿洞镇", "灰塔法师塔", "海岸城"):
        assert name in prompt, f"邻接区域 {name} 应注入 prompt"
    # 跨区域指代约束
    assert "禁止跨区域指代" in prompt
    # 村庄酒馆开局：注入村庄邻接
    c2 = create_character("LocTest2", "Human", "Fighter", start_location="tavern")
    prompt2 = build_system_prompt(c2)
    assert "醉龙酒馆" in prompt2 and "村庄集市" in prompt2


def test_system_prompt_location_fallback():
    """旧存档无 location 字段/未知 key：fallback 酒馆，不抛错。"""
    from app.chat import build_system_prompt
    c = {"name": "Legacy", "race": "Human", "class_name": "Fighter",
         "abilities": {}, "skills": {}, "inventory": [], "lore": [], "world_state": {}}
    prompt = build_system_prompt(c)
    assert "醉龙酒馆" in prompt, "无 location 字段应 fallback 酒馆"
    c["location"] = "unknown_zone"
    prompt2 = build_system_prompt(c)
    assert "当前位置" not in prompt2, "未知区域跳过注入（容错不抛错）"
