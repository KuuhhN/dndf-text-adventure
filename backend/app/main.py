import json

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from . import db, game
from .chat import game_chat
from .character import create_character

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
            req.abilities, req.background, req.feat, req.skilled_skills,
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
    return s


@app.get("/api/sessions")
def sessions():
    return {"sessions": game.list_sessions()}


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
