import json

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from . import db, game
from .chat import game_chat
from .character import create_character
from .tools import SHOP_ITEMS, WORLD_MAP, accept_quest, buy_item, equip_item, unequip_item

app = FastAPI(title="DNDF Text Adventure API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    session_id: str
    message: str


class QuestAcceptRequest(BaseModel):
    session_id: str
    title: str


class ShopBuyRequest(BaseModel):
    session_id: str
    item: str
    quantity: int = 1


class EquipRequest(BaseModel):
    session_id: str
    item: str
    slot: str


class UnequipRequest(BaseModel):
    session_id: str
    slot: str


class CreateCharacterRequest(BaseModel):
    name: str
    race: str
    class_name: str
    method: str = "standard"
    chosen_skills: list[str] = []
    abilities: dict | None = None
    background: str = ""
    feat: str = ""
    skilled_skills: list[str] = []
    expertise_skills: list[str] = []
    opening: str = ""
    start_location: str = "tavern"


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/races")
def races():
    return {"races": db.list_races()}


@app.get("/api/classes")
def classes():
    return {"classes": db.list_classes()}


@app.get("/api/races/{name}")
def race_detail(name: str):
    d = db.get_race_detail(name)
    if not d:
        return JSONResponse({"error": "未知种族"}, status_code=404)
    return d


@app.get("/api/classes/{name}")
def class_detail(name: str):
    d = db.get_class_detail(name)
    if not d:
        return JSONResponse({"error": "未知职业"}, status_code=404)
    return d


@app.get("/api/feats")
def feats():
    return {"feats": db.get_feats()}


@app.get("/api/backgrounds")
def backgrounds():
    return {"backgrounds": db.get_backgrounds()}


@app.get("/api/roll-abilities")
def roll_abilities_preview():
    """4d6 取 3 高 ×6（预览用，创建时后端会正式掷）。"""
    from .character import ABILITY_ORDER, roll_abilities

    return {"abilities": dict(zip(ABILITY_ORDER, roll_abilities()))}


@app.get("/api/class/{class_name}/skill-choices")
def skill_choices(class_name: str):
    from .character import class_skill_choices

    return class_skill_choices(class_name) or {}


@app.post("/api/character")
def create_character_api(req: CreateCharacterRequest):
    """创建角色并新建会话，返回角色卡 + session_id。"""
    try:
        character = create_character(
            req.name, req.race, req.class_name, req.method, req.chosen_skills,
            req.abilities, req.background, req.feat, req.skilled_skills, req.expertise_skills,
            req.opening, req.start_location,
        )
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    sid = game.create_session(req.name, character)
    return {"session_id": sid, "character": character}


@app.get("/api/session/{sid}")
def get_session(sid: str):
    s = game.get_session(sid)
    if not s:
        return JSONResponse({"error": "会话不存在"}, status_code=404)
    s["in_combat"] = bool(s["character"].get("combat", {}).get("enemies"))
    # 当前区域详情（前端商店按钮/地图弹窗用）
    loc_key = s["character"].get("location", "tavern")
    loc = WORLD_MAP.get(loc_key, {})
    s["location"] = {"key": loc_key, "name": loc.get("name", ""),
                     "desc": loc.get("desc", ""), "shop_level": loc.get("shop_level", 0),
                     "neighbors": loc.get("neighbors", [])}
    return s


@app.get("/api/sessions")
def sessions():
    return {"sessions": game.list_sessions()}


@app.get("/api/shop")
def shop():
    """商店商品清单（引擎定价，含等级）。"""
    return {"items": SHOP_ITEMS}


@app.get("/api/world")
def world():
    """世界地图：全部区域（名称/简介/商店等级/邻接）。"""
    return {"map": WORLD_MAP, "start": "tavern"}


def _load_session_or_404(sid: str):
    s = game.get_session(sid)
    if not s:
        return None, JSONResponse({"error": "会话不存在"}, status_code=404)
    return s, None


@app.post("/api/quests/accept")
def accept_quest_api(req: QuestAcceptRequest):
    """弹窗接受任务：available -> accepted（待办）。"""
    s, err = _load_session_or_404(req.session_id)
    if err:
        return err
    try:
        result = accept_quest(s["character"], req.title)
        game.update_character(req.session_id, s["character"])
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    return {"result": result, "character": s["character"]}


@app.post("/api/shop/buy")
def shop_buy_api(req: ShopBuyRequest):
    """弹窗购买：按引擎定价扣金币入背包。"""
    s, err = _load_session_or_404(req.session_id)
    if err:
        return err
    try:
        result = buy_item(s["character"], req.item, req.quantity)
        game.update_character(req.session_id, s["character"])
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    return {"result": result, "character": s["character"]}


@app.post("/api/equipment/equip")
def equip_api(req: EquipRequest):
    """弹窗装备：背包物品 -> 槽位（同槽替换回包）。"""
    s, err = _load_session_or_404(req.session_id)
    if err:
        return err
    try:
        result = equip_item(s["character"], req.item, req.slot)
        game.update_character(req.session_id, s["character"])
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except KeyError:
        return JSONResponse({"error": "装备数据异常（旧存档兼容），请重新打开背包"}, status_code=400)
    return {"result": result, "character": s["character"]}


@app.post("/api/equipment/unequip")
def unequip_api(req: UnequipRequest):
    """弹窗卸下装备：槽位 -> 背包。"""
    s, err = _load_session_or_404(req.session_id)
    if err:
        return err
    try:
        result = unequip_item(s["character"], req.slot)
        game.update_character(req.session_id, s["character"])
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except KeyError:
        return JSONResponse({"error": "装备数据异常（旧存档兼容），请重新打开背包"}, status_code=400)
    return {"result": result, "character": s["character"]}


@app.post("/api/chat")
async def chat(req: ChatRequest):
    """SSE 流式游戏对话：两阶段协议（工具调用 -> 叙事）。"""

    async def gen():
        try:
            async for event in game_chat(req.session_id, req.message):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:  # 流中报错也以事件形式送达前端（脱敏：详情只进日志）
            import logging
            logging.getLogger("dndf").exception("chat 流异常")
            yield f"data: {json.dumps({'type': 'error', 'text': '游戏引擎出错，请重试（详见服务端日志）'}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")
