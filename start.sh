#!/bin/bash
echo "========================================"
echo "智慧零售损耗预警系统 - 启动脚本"
echo "========================================"
echo ""

echo "[1/3] 检查并初始化数据库..."
python3 -m app.init_data
if [ $? -ne 0 ]; then
    echo "数据库初始化失败！"
    exit 1
fi

echo ""
echo "[2/3] 启动服务..."
echo "服务将在 http://localhost:8000 启动"
echo "API文档: http://localhost:8000/docs"
echo ""
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
