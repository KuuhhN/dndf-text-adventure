@echo off
chcp 65001 >nul
title DNDF 文字冒险 - 一键启动
echo ============================================
echo   DNDF 文字冒险 - 一键启动
echo ============================================
echo.

cd /d %~dp0

REM --- 1. 检查数据（首次自动导入） ---
if not exist backend\data\dndf.db (
    echo [1/3] 首次运行，导入 5e 规则数据...
    cd backend
    python scripts\import_5e.py || (echo 数据导入失败 & pause & exit /b 1)
    cd ..
) else (
    echo [1/3] 规则数据已就绪
)

REM --- 2. 启动后端 ---
echo [2/3] 启动后端 http://localhost:8000 ...
start "DNDF 后端" cmd /k "cd /d %~dp0backend && python -m uvicorn app.main:app --port 8000"

REM --- 3. 启动前端 ---
echo [3/3] 启动前端 http://localhost:5173 ...
if not exist frontend\node_modules (
    echo      首次运行，安装前端依赖...
    cd frontend && call npm install && cd ..
)
start "DNDF 前端" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo 浏览器打开 http://localhost:5173 开始冒险！
echo 关闭本窗口不会停止游戏；结束游戏请关闭两个服务窗口。
echo.
pause
