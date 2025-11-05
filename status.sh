#!/bin/bash

# 查看加密货币交易机器人状态

echo "=========================================="
echo "服务状态"
echo "=========================================="
pm2 status

echo ""
echo "=========================================="
echo "Web服务详细信息"
echo "=========================================="
pm2 info dsok-web

echo ""
echo "=========================================="
echo "Bot服务详细信息"
echo "=========================================="
pm2 info dsok-bot

echo ""
echo "=========================================="
echo "Web最近日志 (最后10行)"
echo "=========================================="
pm2 logs dsok-web --lines 10 --nostream

echo ""
echo "=========================================="
echo "Bot最近日志 (最后10行)"
echo "=========================================="
pm2 logs dsok-bot --lines 10 --nostream

echo ""
echo "=========================================="
echo "实时日志: pm2 logs --follow"
echo "查看Web日志: pm2 logs dsok-web --follow"
echo "查看Bot日志: pm2 logs dsok-bot --follow"
echo "启动所有服务：./start.sh"
echo "查看运行状态：./status.sh"
echo "重启服务：./restart.sh"
echo "停止服务：./stop.sh"
echo "=========================================="


