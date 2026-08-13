"""角色创建与规则计算测试。"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.character import (
    ABILITY_ORDER,
    STANDARD_ARRAY,
    ability_modifier,
    create_character,
    roll_abilities,
)


def test_ability_modifier():
    cases = {1: -5, 8: -1, 9: -1, 10: 0, 11: 0, 12: 1, 14: 2, 15: 2, 16: 3, 20: 5}
    for score, expected in cases.items():
        assert ability_modifier(score) == expected, f"{score} -> {ability_modifier(score)}"


def test_standard_array_abilities():
    """标准购点：加成前六属性必须是标准数组的排列。"""
    c = create_character("Test", "Human", "Fighter")
    base = {k: v for k, v in c["abilities"].items()}
    # Human 全属性 +1，减去后应为标准数组
    raw = sorted(v - 1 for v in base.values())
    assert raw == sorted(STANDARD_ARRAY)


def test_dwarf_con_bonus():
    """矮人种族加成解析：CON +2。"""
    from app import db
    from app.character import _race_ability_bonuses

    bonuses = _race_ability_bonuses(db.get_race("Dwarf"))
    assert bonuses == {"CON": 2}


def test_fighter_hp_ac():
    """战士 1 级 HP = 10 + CON 修正；AC = 10 + DEX 修正。"""
    c = create_character("FighterTest", "Human", "Fighter")
    assert c["max_hp"] == 10 + c["modifiers"]["CON"]
    assert c["current_hp"] == c["max_hp"]
    assert c["ac"] == 10 + c["modifiers"]["DEX"]


def test_wizard_hit_die():
    c = create_character("WizTest", "Human", "Wizard")
    assert c["hit_die"] == 6
    assert c["max_hp"] == 6 + c["modifiers"]["CON"]


def test_skills_use_ability_modifier():
    """技能修正 = 对应属性修正（无熟练时，法师不熟练杂技）。"""
    c = create_character("SkillTest", "Human", "Wizard")
    assert c["skills"]["Acrobatics"] == c["modifiers"]["DEX"]
    assert c["skills"]["Athletics"] == c["modifiers"]["STR"]


def test_fighter_proficient_skills():
    """战士熟练技能（玩家选择）= 属性修正 + 2。"""
    c = create_character("ProfTest", "Human", "Fighter", chosen_skills=["Athletics", "Perception"])
    assert c["skills"]["Athletics"] == c["modifiers"]["STR"] + 2
    assert c["skills"]["Perception"] == c["modifiers"]["WIS"] + 2
    # 未选的技能不加熟练
    assert c["skills"]["Arcana"] == c["modifiers"]["INT"]


def test_fighter_skill_choices_default():
    """未指定时默认取 SRD 列表前 choose 个。"""
    c = create_character("ProfTest2", "Human", "Fighter")
    from app.character import class_skill_choices

    ch = class_skill_choices("Fighter")
    defaults = ch["options"][: ch["choose"]]
    for s in defaults:
        assert c["skills"][s] == c["modifiers"][
            {"Acrobatics": "DEX", "Animal Handling": "WIS", "Arcana": "INT", "Athletics": "STR",
             "Deception": "CHA", "History": "INT", "Insight": "WIS", "Intimidation": "CHA",
             "Investigation": "INT", "Medicine": "WIS", "Nature": "INT", "Perception": "WIS",
             "Performance": "CHA", "Persuasion": "CHA", "Religion": "INT",
             "Sleight of Hand": "DEX", "Stealth": "DEX", "Survival": "WIS"}[s]] + 2


def test_roll_abilities_range():
    """4d6 取 3 高：每项在 3-18 之间。"""
    for _ in range(20):
        scores = roll_abilities()
        assert len(scores) == 6
        assert all(3 <= s <= 18 for s in scores)


def test_rolled_method():
    c = create_character("RolledTest", "Human", "Fighter", method="rolled")
    assert len(c["abilities"]) == 6


def test_unknown_race_rejected():
    import pytest
    with pytest.raises(ValueError):
        create_character("X", "NotARace", "Fighter")


def test_level_up_at_300_xp():
    """300 XP 升 2 级：HP + d10/2+1+CON，回满血。"""
    from app.character import check_level_up

    c = create_character("LvTest", "Human", "Fighter")
    old_hp = c["max_hp"]
    c["xp"] = 300
    leveled = check_level_up(c)
    assert leveled == [2]
    assert c["level"] == 2
    assert c["max_hp"] == old_hp + c["hit_die"] // 2 + 1 + c["modifiers"]["CON"]
    assert c["current_hp"] == c["max_hp"]  # 升级回满


def test_level_up_no_xp():
    from app.character import check_level_up

    c = create_character("NoLv", "Human", "Fighter")
    assert check_level_up(c) == []
    assert c["level"] == 1


def test_level_5_proficiency_bonus():
    """5 级熟练加值 2 -> 3，熟练技能重算。"""
    from app.character import check_level_up

    c = create_character("P5", "Human", "Rogue", chosen_skills=["Stealth", "Perception"])
    old_stealth = c["skills"]["Stealth"]
    c["xp"] = 6500
    leveled = check_level_up(c)
    assert 5 in leveled
    assert c["proficiency_bonus"] == 3
    assert c["skills"]["Stealth"] == old_stealth + 1  # 熟练技能 +1
    assert c["skills"]["Acrobatics"] == c["modifiers"]["DEX"]  # 非熟练不变
