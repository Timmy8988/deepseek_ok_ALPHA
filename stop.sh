#!/bin/bash

# 停止加密货币交易机器人

echo "=========================================="
echo "停止加密货币交易机器人..."
echo "=========================================="

# 停止所有进程
pm2 stop all

# 显示状态
pm2 status

echo ""
echo "=========================================="
echo "所有服务已停止"
echo "重新启动: ./start.sh"
echo "单独启动Web: pm2 start dsok-web"
echo "单独启动Bot: pm2 start dsok-bot"
echo "启动所有服务：./start.sh"
echo "查看运行状态：./status.sh"
echo "重启服务：./restart.sh"
echo "停止服务：./stop.sh"
echo "=========================================="


