#!/bin/bash

# 启动加密货币交易机器人 (使用PM2)

echo "=========================================="
echo "启动加密货币交易机器人..."
echo "=========================================="

# 确保在正确的目录
cd /dsok

# 检查PM2是否安装
if ! command -v pm2 &> /dev/null; then
    echo "错误: PM2未安装"
    echo "请运行: npm install -g pm2"
    exit 1
fi

# 检查虚拟环境是否存在
if [ ! -d "venv" ]; then
    echo "错误: 虚拟环境不存在"
    echo "请先运行: python3 -m venv venv"
    exit 1
fi

# 检查app.py是否存在
if [ ! -f "app.py" ]; then
    echo "错误: app.py文件不存在"
    exit 1
fi

# 停止已存在的进程
echo "停止现有进程..."
pm2 delete dsok 2>/dev/null || true
pm2 delete dsok-web 2>/dev/null || true
pm2 delete dsok-bot 2>/dev/null || true

# 使用PM2配置文件启动
echo "启动应用（Web + Bot 合并进程）..."
pm2 start ecosystem.config.js

# 保存PM2配置
echo "保存PM2配置..."
pm2 save

# 显示状态
echo ""
echo "=========================================="
echo "服务状态:"
echo "=========================================="
pm2 status

echo ""
echo "=========================================="
echo "📖 常用命令:"
echo "=========================================="
echo "  查看所有日志:    pm2 logs"
echo "  查看服务日志:    pm2 logs dsok"
echo "  查看运行状态:    ./status.sh"
echo "  重启服务:        ./restart.sh"
echo "  停止服务:        ./stop.sh"
echo "=========================================="
