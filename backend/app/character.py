"""D&D 5e 角色创建与规则计算（SRD 数据驱动）。"""
import random

from . import db

ABILITY_ORDER = ["STR", "DEX", "CON", "INT", "WIS", "CHA"]
STANDARD_ARRAY = [15, 14, 13, 12, 10, 8]

# 技能 -> 对应属性（5e SRD 18 技能）
SKILL_ABILITIES = {
    "Acrobatics": "DEX", "Animal Handling": "WIS", "Arcana": "INT",
    "Athletics": "STR", "Deception": "CHA", "History": "INT",
    "Insight": "WIS", "Intimidation": "CHA", "Investigation": "INT",
    "Medicine": "WIS", "Nature": "INT", "Perception": "WIS",
    "Performance": "CHA", "Persuasion": "CHA", "Religion": "INT",
    "Sleight of Hand": "DEX", "Stealth": "DEX", "Survival": "WIS",
}


def ability_modifier(score: int) -> int:
    return (score - 10) // 2


# 标准购点（5e PHB 严格规则）
POINT_BUY_COSTS = {8: 0, 9: 1, 10: 2, 11: 3, 12: 4, 13: 5, 14: 7, 15: 9}
POINT_BUY_BUDGET = 27


def validate_point_buy(abilities: dict) -> list[str]:
    """校验标准购点结果：每项 8-15，总花费 <= 27。返回错误列表（空=合法）。"""
    errors = []
    for ab in ABILITY_ORDER:
        v = abilities.get(ab)
        if v is None:
            errors.append(f"缺少属性 {ab}")
        elif v < 8 or v > 15:
            errors.append(f"{ab}={v} 超出购点范围（8-15）")
    if not errors:
        total = sum(POINT_BUY_COSTS[abilities[a]] for a in ABILITY_ORDER)
        if total > POINT_BUY_BUDGET:
            errors.append(f"购点超出预算（{total}/{POINT_BUY_BUDGET}）")
    return errors


def roll_abilities() -> list[int]:
    """4d6 取 3 高 ×6。"""
    return [sum(sorted(random.randint(1, 6) for _ in range(4))[1:]) for _ in range(6)]


def _parse_bonus(bonus) -> int:
    """SRD bonus 字段可能是 int 或 '2d4' 字符串。"""
    if isinstance(bonus, int):
        return bonus
    if isinstance(bonus, str) and "d" in bonus:  # 如 '2d4' -> 期望值
        n, d = bonus.split("d")
        return (int(n) * (int(d) + 1)) // 2
    return 0


def _race_ability_bonuses(race: dict) -> dict:
    """race.ability_bonuses -> {STR: +2, ...}"""
    out = {}
    for ab in race.get("ability_bonuses") or []:
        score = (ab.get("ability_score") or {}).get("name", "")
        out[score] = out.get(score, 0) + _parse_bonus(ab.get("bonus", 0))
    return out


def _class_proficient_skills(class_data: dict) -> set[str]:
    """从 class.proficiencies 提取熟练技能名（去 'skill-' 前缀）。"""
    out = set()
    for p in class_data.get("proficiencies") or []:
        idx = (p.get("proficiency") or {}).get("index", "")
        if idx.startswith("skill-"):
            out.add(idx[len("skill-"):].replace("-", " ").title())
    return out


def class_skill_choices(class_name: str) -> dict:
    """职业可选熟练技能（proficiency_choices）：{desc, choose, options: [技能名]}。"""
    cls = db.get_class(class_name)
    if not cls:
        return {}
    for pc in cls.get("proficiency_choices") or []:
        if pc.get("type") != "proficiencies":
            continue
        options = []
        for opt in pc.get("from", {}).get("options", []):
            idx = (opt.get("item") or {}).get("index", "")
            if idx.startswith("skill-"):
                options.append(idx[len("skill-"):].replace("-", " ").title())
        if options:
            return {"desc": pc.get("desc", ""), "choose": pc.get("choose", 1), "options": options}
    return {}


def create_character(
    name: str,
    race_name: str,
    class_name: str,
    method: str = "standard",
    chosen_skills: list[str] | None = None,
    abilities: dict | None = None,
    background: str = "",
    feat: str = "",
) -> dict:
    race = db.get_race(race_name)
    cls = db.get_class(class_name)
    if not race:
        raise ValueError(f"未知种族: {race_name}")
    if not cls:
        raise ValueError(f"未知职业: {class_name}")

    if method == "point-buy":
        if not abilities:
            raise ValueError("point-buy 模式需要提供 abilities")
        errors = validate_point_buy(abilities)
        if errors:
            raise ValueError("；".join(errors))
        scores = [abilities[a] for a in ABILITY_ORDER]
    elif method == "rolled":
        scores = roll_abilities()
    else:
        scores = list(STANDARD_ARRAY)
        random.shuffle(scores)
    base_abilities = dict(zip(ABILITY_ORDER, scores))
    abilities = dict(base_abilities)
    # 种族加成（人类 +1 全属性，含在 SRD 数据里）
    for ab, bonus in _race_ability_bonuses(race).items():
        abilities[ab] = abilities.get(ab, 0) + bonus

    hit_die = cls.get("hit_die") or 8
    con_mod = ability_modifier(abilities["CON"])
    max_hp = hit_die + con_mod  # 1 级取满

    prof_bonus = 2  # 1 级
    proficient = _class_proficient_skills(cls)
    # 职业可选技能（proficiency_choices）：玩家选择，未提供则默认取前 choose 个
    choices = class_skill_choices(class_name)
    if choices:
        want = chosen_skills or []
        valid = set(choices["options"])
        picked = [s for s in want if s in valid][: choices["choose"]]
        if not picked:  # 默认：SRD 列表前 N 个
            picked = choices["options"][: choices["choose"]]
        proficient |= set(picked)

    # 背景（2024 SRD）：技能熟练 + 赠送专长
    feats: list[str] = []
    if background:
        bg = db.get_item("backgrounds", background)
        if not bg:
            raise ValueError(f"未知背景: {background}")
        for p in bg.get("proficiencies", []):
            skill_name = (p.get("name") or "").replace("Skill: ", "")
            if skill_name in SKILL_ABILITIES:
                proficient.add(skill_name)
        bg_feat = (bg.get("feat") or {}).get("name")
        if bg_feat:
            feats.append(bg_feat)

    # 1 级专长（2024 SRD：origin/general，无 minimum_level > 1 前置）
    if feat:
        f = db.get_item("feats", feat)
        if not f:
            raise ValueError(f"未知专长: {feat}")
        prereq = f.get("prerequisites") or {}
        min_lv = prereq.get("minimum_level", 1) if isinstance(prereq, dict) else 1
        if min_lv > 1:
            raise ValueError(f"专长「{feat}」需要 {min_lv} 级才能选择")
        if f.get("type") not in ("origin", "general"):
            raise ValueError(f"专长「{feat}」不是 1 级可选类型（{f.get('type')}）")
        feats.append(feat)

    skills = {
        skill: ability_modifier(abilities[SKILL_ABILITIES[skill]]) + (prof_bonus if skill in proficient else 0)
        for skill in SKILL_ABILITIES
    }

    character = {
        "name": name,
        "race": race_name,
        "class": class_name,
        "level": 1,
        "background": background or "",
        "feats": feats,
        "abilities": abilities,
        "modifiers": {a: ability_modifier(abilities[a]) for a in ABILITY_ORDER},
        "max_hp": max_hp,
        "current_hp": max_hp,
        "ac": 10 + ability_modifier(abilities["DEX"]),
        "speed": race.get("speed", 30),
        "size": race.get("size", "Medium"),
        "proficiency_bonus": prof_bonus,
        "proficient_skills": sorted(proficient),
        "skills": skills,
        "hit_die": hit_die,
        "inventory": [],
        "spells": [],
        "xp": 0,
        "combat": {"enemies": [], "feature_uses": {}, "rage": False},
        "quests": [],
    }
    from .tools import init_feature_uses  # 循环导入防护：tools 也 import character
    init_feature_uses(character)
    return character


# 5e 升级 XP 阈值（1->2 起）
XP_THRESHOLDS = {2: 300, 3: 900, 4: 2700, 5: 6500, 6: 14000, 7: 23000, 8: 34000,
                 9: 48000, 10: 64000, 11: 85000, 12: 100000, 13: 120000, 14: 140000,
                 15: 165000, 16: 195000, 17: 225000, 18: 265000, 19: 305000, 20: 355000}
PROF_BONUS_BY_LEVEL = {5: 3, 9: 4, 13: 5, 17: 6}


def check_level_up(character: dict) -> list[int]:
    """xp 达标自动升级：HP + hit_die/2+1+CON，熟练加值按等级提升，升级回满血。"""
    leveled = []
    while character["level"] < 20 and character["xp"] >= XP_THRESHOLDS.get(character["level"] + 1, 10**9):
        character["level"] += 1
        gain = character["hit_die"] // 2 + 1 + character["modifiers"]["CON"]
        character["max_hp"] += gain
        character["current_hp"] = character["max_hp"]
        if character["level"] in PROF_BONUS_BY_LEVEL:
            character["proficiency_bonus"] = PROF_BONUS_BY_LEVEL[character["level"]]
        leveled.append(character["level"])
    if leveled:
        # 熟练加值变化后重算技能
        prof_bonus = character["proficiency_bonus"]
        proficient = set(character["proficient_skills"])
        character["skills"] = {
            skill: ability_modifier(character["abilities"][SKILL_ABILITIES[skill]])
            + (prof_bonus if skill in proficient else 0)
            for skill in SKILL_ABILITIES
        }
    return leveled
