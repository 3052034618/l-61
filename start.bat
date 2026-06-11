@echo off
echo ========================================
echo 智慧零售损耗预警系统 - 启动脚本
echo ========================================
echo.

echo [1/3] 检查并初始化数据库...
python -m app.init_data
if errorlevel 1 (
    echo 数据库初始化失败！
    pause
    exit /b 1
)

echo.
echo [2/3] 启动服务...
echo 服务将在 http://localhost:8000 启动
echo API文档: http://localhost:8000/docs
echo.
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
