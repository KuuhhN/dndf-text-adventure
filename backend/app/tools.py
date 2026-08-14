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


def _quests(character: dict) -> list[dict]:
    return character.setdefault("quests", [])


def _inventory(character: dict) -> list[dict]:
    return character.setdefault("inventory", [])


def add_item(character: dict, name: str, description: str = "", quantity: int = 1) -> dict:
    """获得物品入背包：同名合并数量。返回最新背包状态。"""
    if quantity < 1:
        raise ValueError("数量必须为正整数")
    items = _inventory(character)
    for it in items:
        if it["name"] == name:
            it["quantity"] += quantity
            return {"type": "inventory", "item": it, "total": len(items), "note": "数量增加"}
    item = {"name": name, "description": description, "quantity": quantity}
    items.append(item)
    return {"type": "inventory", "item": item, "total": len(items), "note": "新物品入包"}


def remove_item(character: dict, name: str, quantity: int = 1) -> dict:
    """消耗/丢弃物品：扣减数量，归零移除。数量不足报错。"""
    items = _inventory(character)
    for it in items:
        if it["name"] == name:
            if it["quantity"] < quantity:
                raise ValueError(f"{name} 数量不足（现有 {it['quantity']}）")
            it["quantity"] -= quantity
            removed = it["quantity"] <= 0
            if removed:
                items.remove(it)
            return {"type": "inventory", "item": {"name": name, "quantity": max(it.get("quantity", 0) if not removed else 0, 0)}, "removed": removed, "total": len(items)}
    raise ValueError(f"背包中没有 {name}")


def post_quest(
    character: dict,
    title: str,
    description: str = "",
    reward: str = "",
    status: str = "available",
) -> dict:
    """注册任务到告示栏（引擎状态）。叙事中出现悬赏/委托时由 LLM 调用。"""
    quests = _quests(character)
    for q in quests:
        if q["title"] == title:  # 同名任务去重，仅更新状态
            q["status"] = status
            return {"type": "quest", "quest": q, "note": "任务已存在，状态已更新"}
    quest = {"title": title, "description": description, "reward": reward, "status": status}
    quests.append(quest)
    return {"type": "quest", "quest": quest}


def encounter(character: dict, monsters: list[str]) -> dict:
    """把怪物拉入战斗。返回每个怪物的 HP/AC。新战斗开始，狂暴状态重置。"""
    combat = _combat(character)
    combat["rage"] = False
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
        if _combat(character).get("rage"):
            result["damage"] += 2  # 狂暴：近战伤害 +2
            result["rage_bonus"] = True
        enemy["hp"] -= result["damage"]
        result["target_hp"] = enemy["hp"]
        if enemy["hp"] <= 0:  # 击杀：移除（按对象，同名不误杀）+ 经验
            result["killed"] = True
            monster = db.get_monster(target)
            result["xp_gained"] = monster.get("xp", 0) if monster else 0
            character["xp"] = character.get("xp", 0) + result["xp_gained"]
            combat["enemies"] = [e for e in combat["enemies"] if e is not enemy]
            if not combat["enemies"]:
                combat["rage"] = False  # 战斗结束，狂暴消退
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


# 主动能力白名单：可由引擎结算的特性（LLM 不能编造效果，次数引擎管）
# ponytail: 只覆盖 1-2 级高价值主动能力；其余特性在技能面板标注"被动/由 DM 判定"。
# 作用：技能栏显示剩余次数，用了即消耗（短休/长休恢复由 DM 叙事中引导）。
FEATURE_ACTIONS = {
    "second-wind": {
        "zh": "二次呼吸", "action": "附赠动作", "effect": "heal", "dice": "1d10",
        "extra": "level", "uses": 1, "rest": "短休",
        "summary": "战斗中喘口气，立即恢复 1d10+等级 点生命",
    },
    "rage": {
        "zh": "狂暴", "action": "附赠动作", "effect": "rage", "uses": 2, "rest": "长休",
        "summary": "进入狂暴：本场战斗近战伤害 +2",
    },
    "bardic-inspiration-d6": {
        "zh": "吟游激励", "action": "附赠动作", "effect": "inspiration", "uses": 3, "rest": "长休",
        "summary": "给同伴打气：下一次攻击或检定 +1d6",
    },
    "lay-on-hands": {
        "zh": "圣疗", "action": "动作", "effect": "heal", "pool": 5, "uses": 5, "rest": "长休",
        "summary": "通过触碰治疗同伴或自己，治疗量从每天 5 点的池中扣除",
    },
    "breath-weapon": {
        "zh": "吐息武器", "action": "动作", "effect": "damage", "dice": "2d6",
        "save": "DEX", "uses": 1, "rest": "短休",
        "summary": "喷出元素吐息：敌人 DEX 豁免失败受 2d6 伤害",
    },
    "cunning-action": {
        "zh": "狡诈行动", "action": "附赠动作", "effect": "bonus_action", "uses": None,
        "rest": "每回合", "min_level": 2,
        "summary": "每回合可用附赠动作做：疾走、脱离战斗、或巧手",
    },
}


def _combat(character: dict) -> dict:
    return character.setdefault("combat", {"enemies": [], "feature_uses": {}, "rage": False})


def init_feature_uses(character: dict) -> dict:
    """按职业/种族初始化可用能力次数（创建角色时调用）。"""
    combat = _combat(character)
    uses = combat.setdefault("feature_uses", {})
    race = (character.get("race") or "").lower()
    cls = (character.get("class") or "").lower()
    available = set()
    if "dragonborn" in race:
        available.add("breath-weapon")
    if cls == "fighter":
        available.add("second-wind")
    if cls == "barbarian":
        available.add("rage")
    if cls == "bard":
        available.add("bardic-inspiration-d6")
    if cls == "paladin":
        available.add("lay-on-hands")
    if cls == "rogue" and character.get("level", 1) >= 2:
        available.add("cunning-action")
    for idx in available:
        if idx not in uses:
            spec = FEATURE_ACTIONS[idx]
            uses[idx] = {"remaining": spec["uses"], "total": spec["uses"]}
    return uses


def use_feature(character: dict, feature: str, target: str = "") -> dict:
    """使用主动能力（引擎结算）：治疗/狂暴/吐息/激励。

    副作用：扣次数、改 HP/狂暴标记/敌人 HP；次数用完返回 error 由 LLM 叙述。
    """
    combat = _combat(character)
    uses = combat.setdefault("feature_uses", {})
    spec = FEATURE_ACTIONS.get(feature)
    if not spec:
        raise ValueError(f"未知能力: {feature}（可用: {', '.join(FEATURE_ACTIONS)}）")
    rec = uses.get(feature)
    if rec is None:
        raise ValueError(f"角色不拥有能力「{spec['zh']}」")
    if spec["uses"] is not None and rec["remaining"] <= 0:
        return {"error": f"「{spec['zh']}」已用完，需要{spec['rest']}才能恢复"}
    if character.get("level", 1) < spec.get("min_level", 1):
        return {"error": f"「{spec['zh']}」需要 {spec['min_level']} 级"}

    result = {"type": "use_feature", "feature": feature, "feature_zh": spec["zh"],
              "action": spec["action"], "summary": spec["summary"]}

    if spec["effect"] == "heal":
        if spec.get("pool"):  # 圣疗：从池中扣（按剩余池量，不能超支）
            amt = min(rec["remaining"], character["max_hp"] - character["current_hp"])
            character["current_hp"] += amt
            result["healed"] = amt
        else:
            dice = spec["dice"]
            extra = character["level"] if spec.get("extra") == "level" else 0
            healed = roll(dice)["total"] + extra
            before = character["current_hp"]
            character["current_hp"] = min(character["max_hp"], character["current_hp"] + healed)
            healed = character["current_hp"] - before
            result["healed"] = healed
            result["player_hp"] = character["current_hp"]
    elif spec["effect"] == "rage":
        combat["rage"] = True
        result["rage"] = True
        result["note"] = "本场战斗近战伤害 +2"
    elif spec["effect"] == "damage":
        if not combat["enemies"]:
            raise ValueError("没有敌人在战斗中，无法使用吐息")
        enemy = next((e for e in combat["enemies"] if e["name"] == target), combat["enemies"][0])
        dc = 8 + _modifier(character, "CON") + character["proficiency_bonus"]
        monster = db.get_monster(enemy["name"])
        dex_mod = (monster.get("dexterity", 10) - 10) // 2 if monster else 0
        save_roll = roll("1d20")["total"] + dex_mod
        saved = save_roll >= dc
        dmg = roll(spec["dice"])["total"] if not saved else 0  # 简化为失败全伤/成功免伤
        enemy["hp"] -= dmg
        result.update({
            "target": enemy["name"], "dc": dc, "save_roll": save_roll,
            "saved": saved, "damage": dmg, "target_hp": enemy["hp"],
        })
        if enemy["hp"] <= 0:
            result["killed"] = True
            xp = monster.get("xp", 0) if monster else 0
            character["xp"] = character.get("xp", 0) + xp
            result["xp_gained"] = xp
            combat["enemies"] = [e for e in combat["enemies"] if e is not enemy]  # 按对象移除，同名敌人不误杀
            if not combat["enemies"]:
                combat["rage"] = False  # 战斗结束，狂暴消退
            leveled = check_level_up(character)
            if leveled:
                result["level_up"] = leveled
    elif spec["effect"] == "inspiration":
        result["note"] = "下一次攻击或检定 +1d6（叙事中 DM 应用）"
    elif spec["effect"] == "bonus_action":
        result["note"] = "本回合可用附赠动作：疾走 / 脱离战斗 / 巧手"

    if spec["uses"] is not None:
        if spec.get("pool"):
            rec["remaining"] = max(0, rec["remaining"] - result.get("healed", 0))
        else:
            rec["remaining"] -= 1
    result["remaining"] = rec["remaining"]
    return result



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
            "name": "post_quest",
            "description": "把任务/悬赏注册到告示栏。叙事中出现委托、悬赏、任务公告（告示板、委托信、NPC 委托）时必须调用，把任务标题/简述/赏金记录到引擎状态，供玩家在告示栏查看。",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "任务标题，如 幽影矿洞的怪声"},
                    "description": {"type": "string", "description": "任务简述（1 句话）"},
                    "reward": {"type": "string", "description": "赏金，如 50 金币"},
                    "status": {"type": "string", "enum": ["available", "accepted"], "description": "available=悬赏中（默认），accepted=玩家已接下"},
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_item",
            "description": "物品入背包。玩家获得/拾取/购买/搜刮到物品（战利品、药水、任务物品、金币外的财物）时必须调用，记录名称/简述/数量。",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "物品名（中文），如 治疗药水"},
                    "description": {"type": "string", "description": "物品简述（1 句话）"},
                    "quantity": {"type": "integer", "description": "数量，默认 1"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remove_item",
            "description": "物品出背包。玩家消耗/使用/丢弃/交出物品（喝药水、交任务物品、送人）时必须调用，扣减数量。",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "物品名（中文），须与入包时一致"},
                    "quantity": {"type": "integer", "description": "数量，默认 1"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "use_feature",
            "description": "使用角色的主动能力（二次呼吸/狂暴/吐息武器/圣疗/吟游激励/狡诈行动）。玩家明确表示要使用某项能力时调用；引擎结算效果并扣减次数，叙事以结果为准。",
            "parameters": {
                "type": "object",
                "properties": {
                    "feature": {"type": "string", "description": "能力 key（second-wind/rage/bardic-inspiration-d6/lay-on-hands/breath-weapon/cunning-action）"},
                    "target": {"type": "string", "description": "目标（攻击性能力如吐息需要：敌人名，如 Goblin）"},
                },
                "required": ["feature"],
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
        if name == "post_quest":
            return post_quest(character, args["title"], args.get("description", ""),
                              args.get("reward", ""), args.get("status", "available"))
        if name == "add_item":
            return add_item(character, args["name"], args.get("description", ""), args.get("quantity", 1))
        if name == "remove_item":
            return remove_item(character, args["name"], args.get("quantity", 1))
        if name == "use_feature":
            return use_feature(character, args["feature"], args.get("target", ""))
        if name == "lookup":
            return lookup(args["kind"], args["name"])
        return {"error": f"未知工具: {name}"}
    except (ValueError, KeyError, TypeError) as e:  # LLM 畸形参数（类型错）同样转错误结果
        return {"error": str(e)}


def tool_result_message(call: dict, result: dict) -> dict:
    """工具结果 -> OpenAI tool 消息（供下一轮 LLM 请求）。"""
    return {
        "role": "tool",
        "tool_call_id": call["id"],
        "content": json.dumps(result, ensure_ascii=False),
    }
