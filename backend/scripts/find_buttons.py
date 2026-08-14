# -*- coding: utf-8 -*-
"""分析 computer-use 截图，定位浅色卡片按钮的物理像素位置（颜色分割）。"""
import sys
from pathlib import Path

from PIL import Image

img_path = sys.argv[1] if len(sys.argv) > 1 else None
if not img_path:
    print("用法: python find_buttons.py <截图路径>")
    sys.exit(1)

img = Image.open(img_path).convert("RGB")
w, h = img.size
px = img.load()
print(f"截图尺寸: {w}x{h}")

# 羊皮纸卡片色：#f5ecd7 ~ #f8ecc8（浅暖色）。扫描行找连续浅色横条。
def is_card_color(r, g, b):
    return r > 225 and g > 210 and b > 160 and b < 235 and r > g > b

# 只扫向导区域（页面中部），找卡片矩形
rows = []
for y in range(400, 1200):
    xs = []
    x = 600
    while x < w - 200:
        r, g, b = px[x, y]
        if is_card_color(r, g, b):
            start = x
            while x < w - 200 and is_card_color(*px[x, y][:3]):
                x += 1
            if x - start > 60:  # 宽度足够才算卡片
                xs.append((start, x))
        x += 1
    if xs:
        rows.append((y, xs))

# 简化：逐行输出长色段（x 跨度 > 100 的卡片区域行）
prev = None
for y in range(400, 1200):
    x = 600
    segs = []
    while x < 2000:
        r, g, b = px[x, y]
        if is_card_color(r, g, b):
            start = x
            while x < 2000 and is_card_color(*px[x, y][:3]):
                x += 1
            if x - start > 100:
                segs.append((start, x))
        x += 1
    for (x0, x1) in segs:
        print(f"y={y} x[{x0}-{x1}] 中心=({(x0+x1)//2},{y})")
