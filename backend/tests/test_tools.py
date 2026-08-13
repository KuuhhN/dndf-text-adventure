"""规则工具层测试：掷骰/检定/攻击/查询（LLM 不能造数）。"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from app.character import create_character
from app.tools import (
    TOOLS,
    ability_check,
    add_item,
    attack,
    encounter,
    enemy_attack,
    execute_tool,
    lookup,
    post_quest,
    remove_item,
    roll,
    tool_result_message,
)


def test_roll_basic():
    r = roll("1d20")
    assert 1 <= r["rolls"][0] <= 20
    assert r["total"] == r["rolls"][0]
    assert "crit" in r and "fumble" in r


def test_roll_multi_with_modifier():
    r = roll("2d6+3")
    assert len(r["rolls"]) == 2
    assert all(1 <= x <= 6 for x in r["rolls"])
    assert r["total"] == sum(r["rolls"]) + 3


def test_roll_bare_d():
    r = roll("d20")
    assert 1 <= r["rolls"][0] <= 20


def test_roll_invalid():
    with pytest.raises(ValueError):
        roll("xyz")
    with pytest.raises(ValueError):
        roll("0d6")
    with pytest.raises(ValueError):
        roll("101d6")


def test_roll_crit_flags():
    import app.tools as tools

    orig = tools.random.randint
    tools.random.randint = lambda a, b: 20  # 固定出 20
    try:
        r = roll("1d20")
        assert r["crit"] is True and r["fumble"] is False
    finally:
        tools.random.randint = orig


def test_ability_check_skill():
    c = create_character("T", "Human", "Rogue", chosen_skills=["Stealth", "Perception"])
    r = ability_check(c, "Stealth")
    assert r["type"] == "ability_check"
    assert r["modifier"] == c["skills"]["Stealth"]
    assert r["total"] == r["d20"] + r["modifier"]


def test_ability_check_ability():
    c = create_character("T", "Human", "Fighter")
    r = ability_check(c, "STR")
    assert r["modifier"] == c["modifiers"]["STR"]


def test_ability_check_invalid():
    c = create_character("T", "Human", "Fighter")
    with pytest.raises(ValueError):
        ability_check(c, "NOPE")


def test_attack_math():
    """攻击：命中判定与伤害数学正确。"""
    import app.tools as tools
    from unittest.mock import patch

    c = create_character("T", "Human", "Fighter", chosen_skills=["Athletics", "Perception"])

    # 固定骰子 15：15 + STR + 2 >= Goblin AC 15 -> 命中；伤害骰也固定 15
    with patch.object(tools.random, "randint", lambda a, b: 15):
        r = attack(c, "Goblin")
    assert r["hit"] is True
    assert r["target_ac"] == 15
    assert r["damage"] == 15 + c["modifiers"]["STR"]

    # 固定骰子 1：必未命中
    with patch.object(tools.random, "randint", lambda a, b: 1):
        r2 = attack(c, "Goblin")
    assert r2["hit"] is False
    assert r2["damage"] == 0


def test_attack_unknown_target():
    c = create_character("T", "Human", "Fighter")
    with pytest.raises(ValueError):
        attack(c, "NotAMonster")


def test_lookup_monster():
    r = lookup("monster", "Goblin")
    assert r["name"] == "Goblin"
    assert r["hp"] == 7
    assert r["ac"] == 15


def test_lookup_spell():
    r = lookup("spell", "Fireball")
    assert r["name"] == "Fireball"
    assert r["level"] == 3


def test_lookup_invalid():
    with pytest.raises(ValueError):
        lookup("monster", "Nope")
    with pytest.raises(ValueError):
        lookup("weapon", "Nope")


def test_execute_tool_dispatch():
    c = create_character("T", "Human", "Fighter")
    r = execute_tool("roll_dice", {"dice": "1d6"}, c)
    assert 1 <= r["total"] <= 6
    r = execute_tool("lookup", {"kind": "monster", "name": "Goblin"}, c)
    assert r["name"] == "Goblin"
    r = execute_tool("nope", {}, c)
    assert "error" in r


def test_tool_schema_valid():
    """工具 schema 满足 function calling 基本结构。"""
    for t in TOOLS:
        assert t["type"] == "function"
        fn = t["function"]
        assert fn["name"] and fn["description"]
        assert fn["parameters"]["type"] == "object"
        assert "properties" in fn["parameters"]


def test_tool_result_message():
    m = tool_result_message({"id": "call_1", "name": "roll_dice", "arguments": "{}"}, {"total": 7})
    assert m["role"] == "tool"
    assert m["tool_call_id"] == "call_1"
    assert "7" in m["content"]


def test_encounter_adds_enemies():
    c = create_character("T", "Human", "Fighter")
    r = encounter(c, ["Goblin", "Goblin"])
    assert r["enemies"] == [{"name": "Goblin", "hp": 7, "ac": 15}] * 2
    assert len(c["combat"]["enemies"]) == 2


def test_encounter_unknown_monster():
    c = create_character("T", "Human", "Fighter")
    with pytest.raises(ValueError):
        encounter(c, ["NotAMonster"])


def test_attack_kill_and_xp():
    """击杀：敌人移除 + 经验 + 状态持久化到 character。"""
    from unittest.mock import patch
    import app.tools as tools

    c = create_character("T", "Human", "Fighter")
    encounter(c, ["Goblin"])  # HP 7
    # 固定骰子 20（重击）：攻击必中，伤害 20 + STR；哥布林 HP 7 必死
    with patch.object(tools.random, "randint", lambda a, b: 20):
        r = attack(c, "Goblin")
    assert r["hit"] is True
    assert r["killed"] is True
    assert r["xp_gained"] == 50
    assert c["xp"] == 50
    assert c["combat"]["enemies"] == []  # 已移除


def test_enemy_attack_damages_player():
    from unittest.mock import patch
    import app.tools as tools

    c = create_character("T", "Human", "Fighter")
    old_hp = c["current_hp"]
    with patch.object(tools.random, "randint", lambda a, b: 20):
        r = enemy_attack(c, "Goblin")
    assert r["hit"] is True
    assert r["damage"] == 20 + 1
    assert c["current_hp"] == max(0, old_hp - r["damage"])
    assert r["player_hp"] == c["current_hp"]
    assert r["player_dead"] == (c["current_hp"] <= 0)


def test_post_quest_adds_and_dedupes():
    c = create_character("T", "Human", "Fighter")
    r = post_quest(c, "幽影矿洞的怪声", "查明矿洞怪声真相", "50 金币")
    assert r["quest"]["title"] == "幽影矿洞的怪声"
    assert c["quests"] == [{"title": "幽影矿洞的怪声", "description": "查明矿洞怪声真相", "reward": "50 金币", "status": "available"}]
    # 同名任务去重 + 状态更新
    r2 = post_quest(c, "幽影矿洞的怪声", status="accepted")
    assert len(c["quests"]) == 1
    assert c["quests"][0]["status"] == "accepted"
    assert "已存在" in r2["note"]


def test_execute_tool_post_quest():
    c = create_character("T", "Human", "Fighter")
    r = execute_tool("post_quest", {"title": "送信", "reward": "10 金币"}, c)
    assert r["quest"]["title"] == "送信"
    assert c["quests"][0]["reward"] == "10 金币"


def test_add_item_merges_quantity():
    c = create_character("T", "Human", "Fighter")
    r = add_item(c, "治疗药水", "恢复 2d4+2 生命", 2)
    assert c["inventory"] == [{"name": "治疗药水", "description": "恢复 2d4+2 生命", "quantity": 2}]
    assert r["total"] == 1
    add_item(c, "治疗药水", quantity=1)  # 同名合并
    assert c["inventory"][0]["quantity"] == 3
    assert len(c["inventory"]) == 1
    add_item(c, "长剑", "精制铁剑", 1)
    assert len(c["inventory"]) == 2


def test_remove_item_consume_and_discard():
    c = create_character("T", "Human", "Fighter")
    add_item(c, "治疗药水", quantity=2)
    r = remove_item(c, "治疗药水", 1)
    assert r["removed"] is False
    assert c["inventory"][0]["quantity"] == 1
    r2 = remove_item(c, "治疗药水", 1)
    assert r2["removed"] is True
    assert c["inventory"] == []  # 归零移除


def test_remove_item_errors():
    import pytest as pt

    c = create_character("T", "Human", "Fighter")
    add_item(c, "火把", quantity=1)
    with pt.raises(ValueError):
        remove_item(c, "火把", 2)  # 数量不足
    with pt.raises(ValueError):
        remove_item(c, "不存在的东西")  # 背包没有


def test_execute_tool_inventory():
    c = create_character("T", "Human", "Fighter")
    r = execute_tool("add_item", {"name": "干粮", "quantity": 3}, c)
    assert r["item"]["name"] == "干粮"
    r2 = execute_tool("remove_item", {"name": "干粮", "quantity": 2}, c)
    assert c["inventory"][0]["quantity"] == 1
