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
WEB_EXISTS=$(pm2 list | grep -c "dsok-web" || echo "0")
BOT_EXISTS=$(pm2 list | grep -c "dsok-bot" || echo "0")

if [ "$WEB_EXISTS" -eq 0 ] && [ "$BOT_EXISTS" -eq 0 ]; then
    echo "⚠️  未检测到运行中的服务"
    echo "正在启动服务..."
    ./start.sh
    exit 0
fi

# 如果传入了参数，可以单独重启
if [ "$1" = "web" ]; then
    echo "🔄 重启Web服务..."
    if [ "$WEB_EXISTS" -gt 0 ]; then
        pm2 restart dsok-web
        echo "✅ Web服务已重启"
    else
        echo "⚠️  Web服务未运行，正在启动..."
        pm2 start ecosystem.config.js --only dsok-web
    fi
elif [ "$1" = "bot" ]; then
    echo "🔄 重启Bot服务..."
    if [ "$BOT_EXISTS" -gt 0 ]; then
        pm2 restart dsok-bot
        echo "✅ Bot服务已重启"
    else
        echo "⚠️  Bot服务未运行，正在启动..."
        pm2 start ecosystem.config.js --only dsok-bot
    fi
else
    # 重启所有服务
    echo "🔄 重启所有服务..."
    
    if [ "$WEB_EXISTS" -gt 0 ]; then
        echo "   - 重启Web服务 (dsok-web)..."
        pm2 restart dsok-web
    else
        echo "   - 启动Web服务 (dsok-web)..."
        pm2 start ecosystem.config.js --only dsok-web 2>/dev/null || true
    fi
    
    if [ "$BOT_EXISTS" -gt 0 ]; then
        echo "   - 重启Bot服务 (dsok-bot)..."
        pm2 restart dsok-bot
    else
        echo "   - 启动Bot服务 (dsok-bot)..."
        pm2 start ecosystem.config.js --only dsok-bot 2>/dev/null || true
    fi
    
    echo "✅ 所有服务已重启"
fi

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
echo "📝 最近日志 (最后5行):"
echo "=========================================="
if [ "$WEB_EXISTS" -gt 0 ] || [ "$1" != "bot" ]; then
    echo "--- Web服务日志 ---"
    pm2 logs dsok-web --lines 5 --nostream 2>/dev/null || echo "暂无Web日志"
fi
echo ""
if [ "$BOT_EXISTS" -gt 0 ] || [ "$1" != "web" ]; then
    echo "--- Bot服务日志 ---"
    pm2 logs dsok-bot --lines 5 --nostream 2>/dev/null || echo "暂无Bot日志"
fi

echo ""
echo "=========================================="
echo "📖 常用命令:"
echo "=========================================="
echo "  查看状态:        ./status.sh"
echo "  启动所有服务:    ./start.sh"
echo "  停止所有服务:    ./stop.sh"
echo "  重启所有服务:    ./restart.sh"
echo "  重启Web服务:     ./restart.sh web"
echo "  重启Bot服务:     ./restart.sh bot"
echo "  查看实时日志:    pm2 logs"
echo "  查看Web日志:     pm2 logs dsok-web"
echo "  查看Bot日志:     pm2 logs dsok-bot"
echo "=========================================="


