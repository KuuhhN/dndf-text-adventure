"""规则工具层：LLM 只能请求、不能自行造数。

所有机械结果（掷骰/检定/攻击/查询）由本模块执行，LLM 拿到结果后写叙事。
"""
import json
import random
import re

from . import db
from .character import check_level_up

DICE_RE = re.compile(r"(\d*)d(\d+)([+-]\d+)?")


def roll(expression: str) -> dict:
    """解析并执行骰子表达式，如 '1d20+4' / '2d6'。"""
    m = DICE_RE.match(expression.strip().lower())
    if not m:
        raise ValueError(f"无效骰子表达式: {expression}")
    n = int(m.group(1) or 1)
    d = int(m.group(2))
    mod = int(m.group(3) or 0)
    if n < 1 or n > 100 or d < 1 or d > 1000:
        raise ValueError(f"骰子参数越界: {expression}")
    rolls = [random.randint(1, d) for _ in range(n)]
    total = sum(rolls) + mod
    result = {"expression": expression, "rolls": rolls, "total": total}
    if d == 20:
        result["crit"] = max(rolls) == 20
        result["fumble"] = min(rolls) == 1
    return result


def _modifier(character: dict, ability: str) -> int:
    return character["modifiers"].get(ability, 0)


def ability_check(character: dict, skill_or_ability: str) -> dict:
    """属性/技能检定：D20 + 修正（+熟练）。返回完整结果供叙事引用。"""
    skills = character.get("skills", {})
    if skill_or_ability in skills:
        mod = skills[skill_or_ability]
        label = f"技能检定: {skill_or_ability}"
    else:
        ability = skill_or_ability.upper()
        if ability not in character["abilities"]:
            raise ValueError(f"未知属性/技能: {skill_or_ability}")
        mod = _modifier(character, ability)
        label = f"属性检定: {ability}"
    r = roll("1d20")
    return {
        "type": "ability_check",
        "label": label,
        "d20": r["rolls"][0],
        "modifier": mod,
        "total": r["total"] + mod,
        "crit": r.get("crit", False),
        "fumble": r.get("fumble", False),
        "success": None,  # 由 LLM 依 DC 判断
    }


def _monster_ac(monster: dict) -> int:
    ac = monster.get("armor_class")
    if isinstance(ac, list):
        ac = ac[0].get("value", 10) if ac else 10
    return ac


def _combat(character: dict) -> dict:
    return character.setdefault("combat", {"enemies": []})


def encounter(character: dict, monsters: list[str]) -> dict:
    """把怪物拉入战斗。返回每个怪物的 HP/AC。"""
    combat = _combat(character)
    added = []
    for name in monsters:
        monster = db.get_monster(name)
        if not monster:
            raise ValueError(f"未知怪物: {name}")
        hp = monster.get("hit_points", 1)
        combat["enemies"].append({"name": name, "max_hp": hp, "hp": hp, "ac": _monster_ac(monster)})
        added.append({"name": name, "hp": hp, "ac": _monster_ac(monster)})
    return {"type": "encounter", "enemies": added}


def attack(character: dict, target: str, weapon_dice: str = "1d8") -> dict:
    """近战攻击：D20 + 力量修正 + 熟练 vs 目标 AC；命中后掷武器伤害。

    副作用：扣敌人 HP；击杀后移除敌人并加经验；经验达标自动升级。
    """
    combat = _combat(character)
    enemy = next((e for e in combat["enemies"] if e["name"] == target), None)
    if not enemy:  # 目标不在战斗列表：查规则库自动拉入
        monster = db.get_monster(target)
        if not monster:
            raise ValueError(f"未知怪物: {target}")
        enemy = {"name": target, "max_hp": monster.get("hit_points", 1),
                 "hp": monster.get("hit_points", 1), "ac": _monster_ac(monster)}
        combat["enemies"].append(enemy)
    ac = enemy["ac"]
    to_hit = _modifier(character, "STR") + character["proficiency_bonus"]
    r = roll("1d20")
    hit = r["total"] + to_hit >= ac or r.get("crit", False)
    result = {
        "type": "attack",
        "target": target,
        "target_ac": ac,
        "attack_roll": r["rolls"][0],
        "to_hit_bonus": to_hit,
        "attack_total": r["total"] + to_hit,
        "hit": hit,
        "crit": r.get("crit", False),
        "weapon_dice": weapon_dice,
    }
    if hit:
        dmg = roll(weapon_dice)
        if r.get("crit", False):  # 重击：伤害骰翻倍
            m = DICE_RE.match(weapon_dice)
            n, d, mod = int(m.group(1) or 1), int(m.group(2)), int(m.group(3) or 0)
            dmg = roll(f"{n * 2}d{d}{mod:+d}")
            result["crit_damage"] = True
        result["damage_rolls"] = dmg["rolls"]
        result["damage"] = dmg["total"] + _modifier(character, "STR")
        enemy["hp"] -= result["damage"]
        result["target_hp"] = enemy["hp"]
        if enemy["hp"] <= 0:  # 击杀：移除 + 经验
            result["killed"] = True
            monster = db.get_monster(target)
            result["xp_gained"] = monster.get("xp", 0) if monster else 0
            character["xp"] = character.get("xp", 0) + result["xp_gained"]
            combat["enemies"] = [e for e in combat["enemies"] if e["name"] != target]
            leveled = check_level_up(character)
            if leveled:
                result["level_up"] = leveled
    else:
        result["damage"] = 0
    return result


def enemy_attack(character: dict, attacker: str) -> dict:
    """敌人攻击玩家（简化）：D20 vs 玩家 AC，命中 1d6+1 伤害，扣玩家 HP。"""
    d20 = roll("1d20")
    hit = d20["total"] >= character["ac"]
    damage = 0
    if hit:
        damage = roll("1d6")["total"] + 1
        character["current_hp"] = max(0, character["current_hp"] - damage)
    return {
        "type": "enemy_attack",
        "attacker": attacker,
        "attack_roll": d20["rolls"][0],
        "target_ac": character["ac"],
        "hit": hit,
        "damage": damage,
        "player_hp": character["current_hp"],
        "player_dead": character["current_hp"] <= 0,
    }


def lookup(kind: str, name: str) -> dict:
    """规则数据查询（怪物/法术/装备），给 LLM 一个精简摘要。"""
    table = {"monster": "monsters", "spell": "spells", "equipment": "equipment"}.get(kind)
    if not table:
        raise ValueError(f"未知查询类型: {kind}（支持 monster/spell/equipment）")
    item = db.get_item(table, name)
    if not item:
        raise ValueError(f"未找到{kind}: {name}")
    if kind == "monster":
        ac = item.get("armor_class")
        if isinstance(ac, list):
            ac = ac[0].get("value", 10) if ac else 10
        return {
            "name": item["name"],
            "hp": item.get("hit_points"),
            "ac": ac,
            "cr": item.get("challenge_rating"),
            "xp": item.get("xp"),
            "actions": [a.get("name") for a in item.get("actions", [])][:5],
        }
    if kind == "spell":
        return {
            "name": item["name"],
            "level": item.get("level"),
            "school": item.get("school", {}).get("name"),
            "casting_time": item.get("casting_time"),
            "range": item.get("range"),
            "components": item.get("components"),
            "duration": item.get("duration"),
            "desc": (item.get("desc") or [""])[0][:300],
        }
    return {
        "name": item["name"],
        "category": (item.get("equipment_category") or {}).get("name"),
        "cost": item.get("cost"),
        "weight": item.get("weight"),
    }


# LLM 工具 schema（OpenAI function calling 格式）
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "roll_dice",
            "description": "掷骰子。玩家想掷任意骰子时使用（如隐藏判定、随机事件）。返回骰子结果。",
            "parameters": {
                "type": "object",
                "properties": {
                    "dice": {"type": "string", "description": "骰子表达式，如 1d20、2d6+3"},
                },
                "required": ["dice"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ability_check",
            "description": "属性/技能检定。玩家尝试攀爬、潜行、说服、察觉等需要判定成败的行动时使用。返回 D20 结果。",
            "parameters": {
                "type": "object",
                "properties": {
                    "skill_or_ability": {
                        "type": "string",
                        "description": "技能名（如 Perception、Stealth、Athletics）或属性名（STR/DEX/CON/INT/WIS/CHA）",
                    },
                },
                "required": ["skill_or_ability"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "attack",
            "description": "近战攻击检定。玩家攻击一个怪物时使用。命中则扣减怪物 HP（引擎维护战斗状态），击杀后玩家获得经验。返回命中与否与伤害。",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "怪物英文名，如 Goblin"},
                    "weapon_dice": {"type": "string", "description": "武器伤害骰，默认 1d8"},
                },
                "required": ["target"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "encounter",
            "description": "遭遇战开始：把怪物拉入战斗状态（DM 宣布敌人出现时使用，战斗中每只怪物只能用一次）。返回各怪物 HP/AC。",
            "parameters": {
                "type": "object",
                "properties": {
                    "monsters": {"type": "array", "items": {"type": "string"}, "description": "怪物英文名列表，如 [\"Goblin\", \"Goblin\"]"},
                },
                "required": ["monsters"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "enemy_attack",
            "description": "敌人攻击玩家。轮到敌人行动（如玩家攻击未命中后敌人反击）时使用，会扣减玩家 HP。返回命中与伤害。",
            "parameters": {
                "type": "object",
                "properties": {
                    "attacker": {"type": "string", "description": "攻击的怪物英文名，如 Goblin"},
                },
                "required": ["attacker"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup",
            "description": "查询 D&D 5e 规则数据（怪物/法术/装备）。玩家询问怪物信息、想施法或购买装备时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": ["monster", "spell", "equipment"]},
                    "name": {"type": "string", "description": "条目英文名，如 Goblin / Fireball / Longsword"},
                },
                "required": ["kind", "name"],
            },
        },
    },
]


def execute_tool(name: str, args: dict, character: dict | None = None) -> dict:
    """执行工具调用，返回结果 dict。异常转成错误结果，不让调用方崩。"""
    try:
        if name == "roll_dice":
            return roll(args["dice"])
        if name == "ability_check":
            return ability_check(character, args["skill_or_ability"])
        if name == "attack":
            return attack(character, args["target"], args.get("weapon_dice", "1d8"))
        if name == "encounter":
            return encounter(character, args["monsters"])
        if name == "enemy_attack":
            return enemy_attack(character, args["attacker"])
        if name == "lookup":
            return lookup(args["kind"], args["name"])
        return {"error": f"未知工具: {name}"}
    except (ValueError, KeyError) as e:
        return {"error": str(e)}


def tool_result_message(call: dict, result: dict) -> dict:
    """工具结果 -> OpenAI tool 消息（供下一轮 LLM 请求）。"""
    return {
        "role": "tool",
        "tool_call_id": call["id"],
        "content": json.dumps(result, ensure_ascii=False),
    }
