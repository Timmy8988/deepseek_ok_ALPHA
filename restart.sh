#!/bin/bash

# 重启加密货币交易机器人服务

echo "=========================================="
echo "🔄 重启加密货币交易机器人服务"
echo "=========================================="

# 确保在正确的目录
cd /dsok

# 检查PM2是否安装
if ! command -v pm2 &> /dev/null; then
    echo "❌ 错误: PM2未安装"
    echo "请运行: npm install -g pm2"
    exit 1
fi

# 检查服务是否存在
DSOK_EXISTS=$(pm2 list | grep -c "dsok" || echo "0")

if [ "$DSOK_EXISTS" -eq 0 ]; then
    echo "⚠️  未检测到运行中的服务"
    echo "正在启动服务..."
    ./start.sh
    exit 0
fi

# 重启服务
echo "🔄 重启服务 (dsok)..."
pm2 restart dsok
echo "✅ 服务已重启"

# 保存PM2配置
pm2 save

# 等待服务启动
sleep 2

# 显示状态
echo ""
echo "=========================================="
echo "📊 当前服务状态:"
echo "=========================================="
pm2 status

echo ""
echo "=========================================="
echo "📝 最近日志 (最后10行):"
echo "=========================================="
pm2 logs dsok --lines 10 --nostream 2>/dev/null || echo "暂无日志"

echo ""
echo "=========================================="
echo "📖 常用命令:"
echo "=========================================="
echo "  查看状态:        ./status.sh"
echo "  启动服务:        ./start.sh"
echo "  停止服务:        ./stop.sh"
echo "  重启服务:        ./restart.sh"
echo "  查看实时日志:    pm2 logs"
echo "  查看服务日志:    pm2 logs dsok"
echo "=========================================="


