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


def test_feature_uses_initialized_by_class():
    """创建角色时按职业/种族初始化可用能力次数。"""
    from app.character import create_character
    from app.tools import FEATURE_ACTIONS

    fighter = create_character("F", "Human", "Fighter", chosen_skills=["Athletics"])
    uses = fighter["combat"]["feature_uses"]
    assert "second-wind" in uses and uses["second-wind"]["remaining"] == 1
    assert "rage" not in uses

    barb = create_character("B", "Human", "Barbarian", chosen_skills=["Athletics"])
    assert barb["combat"]["feature_uses"]["rage"]["remaining"] == 2

    dragon = create_character("D", "Dragonborn", "Fighter", chosen_skills=["Athletics"])
    assert "breath-weapon" in dragon["combat"]["feature_uses"]

    rogue1 = create_character("R", "Human", "Rogue", chosen_skills=["Stealth"])
    assert "cunning-action" not in rogue1["combat"]["feature_uses"]  # 2 级才解锁


def test_use_feature_second_wind_heals_and_consumes():
    """二次呼吸：回 1d10+等级 血，次数 1->0，再使用报错。"""
    from app.character import create_character
    from app.tools import use_feature

    c = create_character("F", "Human", "Fighter", chosen_skills=["Athletics"])
    c["current_hp"] = 3
    r = use_feature(c, "second-wind")
    assert r["healed"] >= 1
    assert c["current_hp"] == 3 + r["healed"]
    assert c["combat"]["feature_uses"]["second-wind"]["remaining"] == 0
    r2 = use_feature(c, "second-wind")
    assert "error" in r2


def test_use_feature_breath_weapon_damages_enemy():
    """吐息武器：对敌人造成伤害（豁免成功免伤），击杀给经验。"""
    from app.character import create_character
    from app.tools import use_feature, encounter

    c = create_character("D", "Dragonborn", "Fighter", chosen_skills=["Athletics"])
    encounter(c, ["Goblin"])
    enemy = c["combat"]["enemies"][0]
    hp_before = enemy["hp"]
    r = use_feature(c, "breath-weapon", "Goblin")
    assert r["saved"] in (True, False)
    assert enemy["hp"] == hp_before - r["damage"]
    assert c["combat"]["feature_uses"]["breath-weapon"]["remaining"] == 0


def test_use_feature_rage_boosts_damage():
    """狂暴后 attack 近战伤害 +2。"""
    from app.character import create_character
    from app.tools import use_feature, attack, encounter

    c = create_character("B", "Human", "Barbarian", chosen_skills=["Athletics"])
    encounter(c, ["Goblin"])
    use_feature(c, "rage")
    assert c["combat"]["rage"] is True
    r = attack(c, "Goblin")
    if r["hit"]:
        assert r.get("rage_bonus") is True
        assert r["damage"] >= 2


def test_use_feature_lay_on_hands_pool():
    """圣疗：治疗量从 5 点池扣，池为 0 时无法再治疗。"""
    from app.character import create_character
    from app.tools import use_feature

    c = create_character("P", "Human", "Paladin", chosen_skills=["Athletics"])
    c["current_hp"] = 2
    r = use_feature(c, "lay-on-hands")
    assert r["healed"] == min(5, c["max_hp"] - 2)
    assert c["combat"]["feature_uses"]["lay-on-hands"]["remaining"] == 5 - r["healed"]
    # 池耗尽
    c["current_hp"] = 0
    for _ in range(5):
        r = use_feature(c, "lay-on-hands")
        if "error" in r:
            break
    assert "error" in r


def test_lay_on_hands_pool_never_overdraws():
    """圣疗池剩 2 点时最多治疗 2 点（回归：之前固定按 5 点池超支）。"""
    from app.character import create_character
    from app.tools import use_feature

    c = create_character("P", "Human", "Paladin", chosen_skills=["Athletics"])
    c["current_hp"] = 1
    use_feature(c, "lay-on-hands")  # 第一次：满缺口，耗 5
    assert c["combat"]["feature_uses"]["lay-on-hands"]["remaining"] == 0
    # 重置池为 2，缺口 5：只能治 2
    c["combat"]["feature_uses"]["lay-on-hands"]["remaining"] = 2
    c["current_hp"] = 1
    r = use_feature(c, "lay-on-hands")
    assert r["healed"] == 2
    assert c["current_hp"] == 3
    assert c["combat"]["feature_uses"]["lay-on-hands"]["remaining"] == 0


def test_rage_resets_when_combat_ends():
    """狂暴在战斗结束（敌人清空）和新遭遇时重置（回归：之前永久生效）。"""
    from app.character import create_character
    from app.tools import use_feature, attack, encounter

    c = create_character("B", "Human", "Barbarian", chosen_skills=["Athletics"])
    encounter(c, ["Goblin"])
    use_feature(c, "rage")
    assert c["combat"]["rage"] is True
    # 连续攻击直到击杀（敌方 Goblin 不反击也行，直接调用 attack）
    for _ in range(20):
        attack(c, "Goblin")
        if not c["combat"]["enemies"]:
            break
    assert c["combat"]["enemies"] == []
    assert c["combat"]["rage"] is False, "战斗结束狂暴应消退"
    # 新遭遇再次重置
    encounter(c, ["Goblin"])
    assert c["combat"]["rage"] is False


def test_same_name_enemies_killed_one_by_one():
    """同名敌人（两只哥布林）击杀一只不应移除另一只（回归：之前按 name 全移除）。"""
    from app.character import create_character
    from app.tools import attack, encounter

    c = create_character("F", "Human", "Fighter", chosen_skills=["Athletics"])
    encounter(c, ["Goblin", "Goblin"])
    assert len(c["combat"]["enemies"]) == 2
    kills = 0
    for _ in range(30):
        if not c["combat"]["enemies"]:
            break  # 两只都杀掉即停（attack 会自动拉新怪，不能继续打）
        r = attack(c, "Goblin")
        if r["hit"] and r["target_hp"] <= 0:
            kills += 1
    assert kills == 2, f"应恰好击杀 2 只同名哥布林，实际 {kills}"
    assert c["combat"]["enemies"] == []


def test_rogue_unlocks_cunning_action_at_level_2():
    """盗贼升到 2 级解锁狡诈行动（回归：之前 init 只在创建时跑一次）。"""
    from app.character import create_character, check_level_up

    c = create_character("R", "Human", "Rogue", chosen_skills=["Stealth"])
    assert "cunning-action" not in c["combat"]["feature_uses"]
    c["xp"] = 300  # 1->2 阈值
    check_level_up(c)
    assert c["level"] == 2
    assert "cunning-action" in c["combat"]["feature_uses"]


def test_execute_tool_malformed_args_returns_error():
    """LLM 传畸形参数（数字而非字符串）返回 error 不抛异常（回归：AttributeError 漏捕）。"""
    from app.tools import execute_tool

    r = execute_tool("roll_dice", {"dice": 123}, None)
    assert "error" in r, f"roll_dice 数字参数应转 error，实际 {r}"
    r2 = execute_tool("ability_check", {"skill_or_ability": 42}, None)
    assert "error" in r2
    r3 = execute_tool("attack", {"target": 7}, None)
    assert "error" in r3


def test_feat_dedup_with_background():
    """背景赠送专长与自选专长重复时自动去重（回归：罪犯背景送警觉，不能再选警觉）。"""
    from app.character import create_character

    c = create_character("C", "Human", "Fighter", background="Criminal", feat="Alert",
                          chosen_skills=["Athletics", "Perception"])
    assert c["feats"].count("Alert") == 1, f"Alert 不应重复: {c['feats']}"


def _mk(race, cls, **kw):
    """固定属性创建角色（避免 standard 随机属性导致断言不稳）。"""
    from app.character import create_character
    return create_character("T", race, cls, method="point-buy",
                            abilities={"STR": 15, "DEX": 14, "CON": 13, "INT": 10, "WIS": 10, "CHA": 8}, **kw)


def test_skilled_feat_adds_3_proficiencies():
    """技能熟练专长：额外 3 个未熟练技能获得熟练。"""
    base = _mk("Human", "Fighter", chosen_skills=["Athletics", "Perception"])
    skilled = _mk("Human", "Fighter", feat="Skilled", chosen_skills=["Athletics", "Perception"])
    gained = set(skilled["proficient_skills"]) - set(base["proficient_skills"])
    assert len(gained) == 3, f"应新增 3 个熟练技能: {gained}"
    # 新熟练的技能修正 = 属性修正 + 2
    for s in gained:
        assert skilled["skills"][s] == base["skills"][s] + 2, f"{s}: {skilled['skills'][s]} vs {base['skills'][s]}+2"


def test_passives_initialized():
    """被动能力按种族/专长初始化：龙裔火抗+吐息主动；半身人幸运；盗贼无专长被动。"""
    from app.character import create_character

    dragon = create_character("D", "Dragonborn", "Fighter", chosen_skills=["Athletics"])
    assert "draconic-ancestry" in dragon["passives"] or "damage-resistance" in dragon["passives"]
    halfling = create_character("H", "Halfling", "Rogue", chosen_skills=["Stealth"])
    assert "lucky" in halfling["passives"]
    alert = create_character("A", "Human", "Fighter", feat="Alert", chosen_skills=["Athletics"])
    assert "alert" in alert["passives"]


def test_savage_attacker_damage_reroll():
    """野蛮攻击者：命中时伤害骰掷两次取高（多次攻击验证 damage 取高逻辑）。"""
    from app.character import create_character
    from app.tools import attack, encounter

    c = _mk("Human", "Fighter", feat="Savage Attacker", chosen_skills=["Athletics"])
    encounter(c, ["Goblin"])
    hit_dmg = []
    for _ in range(30):
        r = attack(c, "Goblin", weapon_dice="1d4")  # 1d4 便于验证取高
        if r["hit"] and r.get("savage_attacker"):
            hit_dmg.append((r["damage_rolls"], r["damage"]))
        if not c["combat"]["enemies"]:
            encounter(c, ["Goblin"])
        if len(hit_dmg) >= 5:
            break
    assert len(hit_dmg) >= 5, "应有多次野蛮攻击命中"
    str_mod = c["modifiers"]["STR"]
    for rolls, dmg in hit_dmg:
        assert len(rolls) == 2, f"伤害骰应掷两次: {rolls}"
        assert dmg == max(rolls) + str_mod, f"伤害应取高+力量修正: {rolls} + {str_mod} -> {dmg}"


def test_alert_initiative_bonus():
    """警觉专长：encounter 返回先攻 +5。"""
    from app.character import create_character
    from app.tools import encounter

    c = create_character("AL", "Human", "Fighter", feat="Alert", chosen_skills=["Athletics"])
    r = encounter(c, ["Goblin"])
    assert r["initiative"]["alert_bonus"] == 5
    plain = create_character("PL", "Human", "Fighter", chosen_skills=["Athletics"])
    r2 = encounter(plain, ["Goblin"])
    assert r2["initiative"]["alert_bonus"] == 0


def test_lucky_rerolls_fumble():
    """幸运：检定大失败自动重掷一次，次数扣减。"""
    import random
    from unittest.mock import patch
    from app.character import create_character
    from app.tools import ability_check

    c = create_character("LK", "Halfling", "Rogue", chosen_skills=["Stealth"])
    assert "lucky" in c["passives"]
    # 强制第一次掷 1（大失败），第二次掷 10
    with patch("app.tools.roll") as mock_roll:
        mock_roll.side_effect = [{"type": "roll", "expression": "1d20", "rolls": [1], "total": 1, "crit": False, "fumble": True},
                                 {"type": "roll", "expression": "1d20", "rolls": [10], "total": 10, "crit": False, "fumble": False}]
        r = ability_check(c, "Stealth")
    assert r.get("lucky_reroll") is True
    assert r["d20_original"] == 1 and r["d20"] == 10
    assert c["combat"]["lucky_uses"]["remaining"] == 0


def test_relentless_endurance_saves_from_death():
    """不屈坚韧：濒死时回到 1 HP（1次/长休）。"""
    from unittest.mock import patch
    from app.character import create_character
    from app.tools import enemy_attack, encounter

    c = create_character("RE", "Half-Orc", "Barbarian", chosen_skills=["Athletics"])
    encounter(c, ["Goblin"])
    c["current_hp"] = 1
    c["ac"] = 0  # 保证被命中
    with patch("app.tools.roll") as mock_roll:
        mock_roll.side_effect = [{"type": "roll", "expression": "1d20", "rolls": [20], "total": 20},
                                 {"type": "roll", "expression": "1d6", "rolls": [6], "total": 6}]
        r = enemy_attack(c, "Goblin")
    assert r.get("relentless_endurance") is True
    assert c["current_hp"] == 1, "不屈坚韧应回 1 HP"
    assert c["combat"]["relentless_uses"]["remaining"] == 0


def test_resistance_halves_damage():
    """抗性被动：敌人伤害减半。"""
    from unittest.mock import patch
    from app.character import create_character
    from app.tools import enemy_attack, encounter

    c = create_character("RS", "Dragonborn", "Fighter", chosen_skills=["Athletics"])
    encounter(c, ["Goblin"])
    c["ac"] = 0
    with patch("app.tools.roll") as mock_roll:
        mock_roll.side_effect = [{"type": "roll", "expression": "1d20", "rolls": [20], "total": 20, "crit": True, "fumble": False},
                                 {"type": "roll", "expression": "1d6", "rolls": [5], "total": 5}]
        r = enemy_attack(c, "Goblin")
    assert r.get("resisted") is True
    assert r["damage"] == 3, f"6 伤害减半应 3，实际 {r['damage']}"


def test_skilled_feat_user_picked_skills():
    """技能熟练专长：用户自选的 3 个技能生效（回归：之前引擎自动选）。"""
    from app.character import create_character

    c = create_character("SP", "Human", "Fighter", feat="Skilled",
                         chosen_skills=["Athletics", "Perception"],
                         skilled_skills=["Stealth", "Arcana", "Deception"])
    for s in ["Stealth", "Arcana", "Deception"]:
        assert s in c["proficient_skills"], f"{s} 应熟练"
    assert c["skills"]["Stealth"] == c["modifiers"]["DEX"] + 2


def test_skilled_feat_filters_duplicates_and_backfills():
    """技能熟练专长：背景已熟练的自选被过滤，总数仍补满 3 个新熟练，不抛错。"""
    from app.character import create_character

    # Sleight of Hand 是罪犯背景熟练 → 过滤；Athletics（未熟练）保留；补齐 1 个；总数 = 4 基础 + 3 专长
    c = create_character("SF", "Human", "Fighter", feat="Skilled", background="Criminal",
                         chosen_skills=["Insight", "History"],
                         skilled_skills=["Athletics", "Sleight of Hand", "Medicine"])
    assert len(c["proficient_skills"]) == 7, f"应 4+3=7 个熟练，实际 {c['proficient_skills']}"
    assert "Athletics" in c["proficient_skills"], "未熟练的自选应保留"
    assert "Medicine" in c["proficient_skills"], "未熟练的自选应保留"
    assert "Sleight of Hand" in c["proficient_skills"], "背景熟练不受影响"


def test_skilled_feat_backfills_when_short():
    """技能熟练专长：只传 2 个有效自选时自动补齐到 3 个。"""
    from app.character import create_character

    c = create_character("SS", "Human", "Fighter", feat="Skilled",
                         chosen_skills=["Athletics", "Perception"],
                         skilled_skills=["Medicine", "Persuasion"])
    assert len(c["proficient_skills"]) == 5, f"应 2+3=5 个熟练，实际 {c['proficient_skills']}"
    assert "Medicine" in c["proficient_skills"] and "Persuasion" in c["proficient_skills"]


def test_skilled_feat_deduplicates_duplicate_input():
    """技能熟练专长：重复技能输入只加一次熟练（防双倍熟练 bug）。"""
    from app.character import create_character

    c = create_character("DD", "Human", "Fighter", feat="Skilled",
                         chosen_skills=["Athletics", "Perception"],
                         skilled_skills=["Stealth", "Stealth", "Arcana"])
    mod = c["modifiers"]["DEX"]
    assert c["skills"]["Stealth"] == mod + 2, f"Stealth 应只加一次熟练，实际 {c['skills']['Stealth']}"
    assert len(c["proficient_skills"]) == 5, f"应 2+3=5 个熟练，实际 {c['proficient_skills']}"


def test_skilled_feat_ignores_invalid_names():
    """技能熟练专长：非法技能名/职业重叠项被忽略，补齐到 3 个。"""
    from app.character import create_character

    c = create_character("IN", "Human", "Fighter", feat="Skilled",
                         chosen_skills=["Athletics", "Perception"],
                         skilled_skills=["NotASkill", "Athletics", "Medicine"])
    assert len(c["proficient_skills"]) == 5, f"应 2+3=5 个熟练，实际 {c['proficient_skills']}"
    assert "Medicine" in c["proficient_skills"], "有效自选应保留"


def test_background_skills_auto_granted():
    """背景技能自动熟练（罪犯→巧手/潜行），不占职业选择名额。"""
    from app.character import create_character

    c = create_character("BG", "Human", "Rogue", background="Criminal",
                         chosen_skills=["Athletics", "Perception"])
    assert "Sleight of Hand" in c["proficient_skills"], "背景技能应自动熟练"
    assert "Stealth" in c["proficient_skills"], "背景技能应自动熟练"


def test_rogue_expertise_doubles_proficiency():
    """游荡者专精：选 2 个已熟练技能，熟练加值翻倍（+2 → +4）。"""
    from app.character import create_character

    c = create_character("EX", "Human", "Rogue",
                         chosen_skills=["Stealth", "Sleight of Hand"],
                         expertise_skills=["Stealth", "Sleight of Hand"])
    mod = c["modifiers"]["DEX"]
    assert c["skills"]["Stealth"] == mod + 4, f"专精应翻倍为 +4，实际 {c['skills']['Stealth']}"
    assert c["skills"]["Sleight of Hand"] == mod + 4
    assert c["expertise_skills"] == ["Sleight of Hand", "Stealth"]


def test_rogue_expertise_backfills_from_proficient():
    """游荡者专精：不足 2 个/非法输入时，从已熟练技能自动补齐；非熟练技能被忽略。"""
    from app.character import create_character

    c = create_character("EX2", "Human", "Rogue",
                         chosen_skills=["Stealth", "Perception"],
                         expertise_skills=["Stealth", "Athletics"])  # Athletics 未熟练 → 忽略
    mod = c["modifiers"]["DEX"]
    assert c["skills"]["Stealth"] == mod + 4, "专精技能应翻倍"
    expert = c["expertise_skills"]
    assert len(expert) == 2, f"应补满 2 个专精，实际 {expert}"
    assert "Stealth" in expert and "Athletics" not in expert


def test_expertise_ignored_for_non_rogue():
    """非游荡者职业传 expertise_skills 应被忽略（无 Expertise 特性）。"""
    from app.character import create_character

    c = create_character("NF", "Human", "Fighter", chosen_skills=["Athletics", "Perception"],
                         expertise_skills=["Athletics", "Perception"])
    assert c["expertise_skills"] == [], "非游荡者不应有专精"
    assert c["skills"]["Athletics"] == c["modifiers"]["STR"] + 2, "不应翻倍"
