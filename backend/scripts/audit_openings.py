"""逐一排查全部开局：地图完整性 + 开局地点引用可达性分析。"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.tools import WORLD_MAP

# 前端 SCENE_PRESETS 的开局文本（手工维护副本；若改 App.jsx 的 SCENE_PRESETS 需同步此处）
SCENE_PRESETS = [
    {"key": "tavern", "name": "醉龙酒馆", "loc": "tavern",
     "text": "你在艾瑟兰村的醉龙酒馆醒来：炉火噼啪、酒客喧哗，冒险的故事从一张吧台开始。"},
    {"key": "forest", "name": "幽影森林边缘", "loc": "forest_edge",
     "text": "你在幽影森林边缘的猎营醒来：晨雾缭绕、鸟鸣幽远，猎弓就放在手边。"},
    {"key": "mine", "name": "矿洞镇", "loc": "mine_town",
     "text": "你在矿洞镇的铁匠铺前醒来：矿锤叮当、尘土飞扬，镇上正缺敢下深矿的雇工。"},
    {"key": "capital", "name": "王都艾瑟兰", "loc": "capital",
     "text": "你在王都艾瑟兰的旅店房间醒来：窗外马车辘辘、骑士巡街，楼下狮鹫酒馆的喧嚣若隐若现。"},
    {"key": "custom", "name": "自拟开局", "loc": "tavern", "text": ""},
]

# 地点关键词 → 对应地图区域（语义映射，用于判断 opening 引用地点是否可达）
PLACE_KEYWORDS = {
    "醉龙酒馆": "tavern", "酒馆": None,  # 酒馆泛指 → 检查起始区域邻接是否有酒馆类区域
    "村庄集市": "village_market", "集市": "village_market",
    "农场": "farmland", "郊野农场": "farmland",
    "幽影森林": "forest_edge", "森林": "forest_edge", "猎营": "forest_edge",
    "矿洞镇": "mine_town", "铁匠铺": "mine_town", "矿洞": "mine_town",
    "法师塔": "mage_tower", "灰塔": "mage_tower",
    "王都艾瑟兰": "capital", "王都": "capital",
    "海岸城": "coast_city", "港口": "coast_city",
    "龙眠山脉": "dragon_peaks", "山脉": "dragon_peaks",
    "狮鹫酒馆": "capital_tavern",
}
# 短名关键词只在未命中更长关键词时才检查（如「艾瑟兰」在「王都艾瑟兰」中属于国名而非村庄）
SHORT_WORDS_CHECK = {"艾瑟兰": "tavern", "酒馆": None}


def graph_checks():
    """地图完整性：引用存在、双向邻接、无孤立区域。"""
    problems = []
    for key, region in WORLD_MAP.items():
        for nb in region.get("neighbors", []):
            if nb not in WORLD_MAP:
                problems.append(f"死链：{key} 邻接 {nb} 不存在")
            elif key not in WORLD_MAP[nb].get("neighbors", []):
                problems.append(f"非双向：{key}→{nb} 但 {nb}→ 无 {key}")
    # 连通性（BFS from tavern）
    seen = {"tavern"}
    queue = ["tavern"]
    while queue:
        cur = queue.pop(0)
        for nb in WORLD_MAP[cur].get("neighbors", []):
            if nb not in seen:
                seen.add(nb)
                queue.append(nb)
    isolated = set(WORLD_MAP) - seen
    if isolated:
        problems.append(f"孤立区域（从 tavern 不可达）：{sorted(isolated)}")
    return problems


def opening_checks():
    """每个开局：起始区域存在 + opening 引用的地点是否与起始区域一致/可达。"""
    issues = []
    for preset in SCENE_PRESETS:
        loc = preset["loc"]
        if loc not in WORLD_MAP:
            issues.append(f"[{preset['name']}] 起始区域 {loc} 不在 WORLD_MAP")
            continue
        text = preset["text"]
        if not text:
            issues.append(f"[{preset['name']}] opening 为空（自拟开局由用户输入，跳过地点检查）")
            continue
        # 先匹配长关键词（避免「王都艾瑟兰」被「艾瑟兰」误命中村庄）
        matched = {kw: region for kw, region in PLACE_KEYWORDS.items() if kw in text}
        for short_kw, short_region in SHORT_WORDS_CHECK.items():
            if short_kw in text and not any(kw in text for kw in PLACE_KEYWORDS if kw != short_kw):
                matched.setdefault(short_kw, short_region)
        # 检查引用的具体地点
        for kw, region in matched.items():
            if region is None:  # 泛指酒馆：起始区域或邻接必须有酒馆类区域
                tavern_regions = [k for k, v in WORLD_MAP.items() if "酒馆" in v["name"]]
                reachable = {loc} | set(WORLD_MAP[loc]["neighbors"])
                if not any(t in reachable for t in tavern_regions):
                    issues.append(f"[{preset['name']}] opening 提到『{kw}』但起始区域 {loc} 邻接无酒馆")
            elif region == loc or region in WORLD_MAP[loc]["neighbors"]:
                pass  # 引用地点 = 起始区域或邻接 → 可达
            else:
                issues.append(f"[{preset['name']}] opening 提到『{kw}』（{region}）从 {loc} 不可直接到达")
    return issues


def main():
    print("=== 地图完整性 ===")
    graph_problems = graph_checks()
    print("无问题" if not graph_problems else "\n".join(f"- {p}" for p in graph_problems))
    print("\n=== 开局地点引用可达性 ===")
    opening_problems = opening_checks()
    if not opening_problems:
        print("全部开局 opening 引用的地点均与起始区域一致或邻接可达")
    else:
        print("\n".join(f"- {p}" for p in opening_problems))
    print("\n=== 区域清单 ===")
    for k, v in WORLD_MAP.items():
        print(f"- {k}（{v['name']}）shop={v['shop_level']} 邻接={v['neighbors']}")
    print("\n结论：", "全部通过" if not graph_problems and not opening_problems else "存在问题，见上")
    return 1 if (graph_problems or [p for p in opening_problems if "为空" not in p]) else 0


if __name__ == "__main__":
    sys.exit(main())
