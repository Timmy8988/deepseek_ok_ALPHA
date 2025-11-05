#!/bin/bash

# ============================================
# DSOK 阿里云 Ubuntu 自动部署脚本
# ============================================
# 用途：一键部署 DSOK 交易机器人到阿里云服务器
# 使用方法：bash deploy.sh
# ============================================

set -e  # 遇到错误立即退出

echo "=========================================="
echo "🚀 DSOK 交易机器人部署脚本"
echo "=========================================="
echo ""

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查是否为root用户
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}❌ 请使用root用户运行此脚本${NC}"
    echo "使用方法: sudo bash deploy.sh"
    exit 1
fi

# 步骤1: 更新系统
echo -e "${GREEN}[1/12]${NC} 更新系统软件包..."
apt update -qq
apt upgrade -y -qq

# 步骤2: 安装必要工具
echo -e "${GREEN}[2/12]${NC} 安装必要工具..."
apt install -y git curl wget nano software-properties-common > /dev/null 2>&1

# 步骤3: 检查并安装Python
echo -e "${GREEN}[3/12]${NC} 检查Python版本..."
if ! command -v python3.10 &> /dev/null; then
    echo "安装Python 3.10..."
    add-apt-repository ppa:deadsnakes/ppa -y > /dev/null 2>&1
    apt update -qq
    apt install -y python3.10 python3.10-venv python3-pip > /dev/null 2>&1
else
    echo "Python 3.10 已安装"
fi

# 步骤4: 安装Node.js
echo -e "${GREEN}[4/12]${NC} 安装Node.js..."
if ! command -v node &> /dev/null; then
    echo "安装Node.js 18.x..."
    curl -fsSL https://deb.nodesource.com/setup_18.x | bash - > /dev/null 2>&1
    apt install -y nodejs > /dev/null 2>&1
else
    echo "Node.js 已安装"
fi

# 步骤5: 安装PM2
echo -e "${GREEN}[5/12]${NC} 安装PM2..."
if ! command -v pm2 &> /dev/null; then
    npm install -g pm2 > /dev/null 2>&1
else
    echo "PM2 已安装"
fi

# 步骤6: 克隆项目
echo -e "${GREEN}[6/12]${NC} 检查项目目录..."
if [ ! -d "/dsok" ]; then
    echo -e "${YELLOW}⚠️  项目目录 /dsok 不存在${NC}"
    echo "请先上传项目文件到 /dsok 目录"
    echo "或使用 git 克隆项目："
    echo "  cd /"
    echo "  git clone <your-repo> dsok"
    echo ""
    read -p "项目文件是否已上传到 /dsok？(y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${RED}❌ 部署已取消${NC}"
        exit 1
    fi
fi

# 步骤7: 创建虚拟环境
echo -e "${GREEN}[7/12]${NC} 创建Python虚拟环境..."
cd /dsok

if [ ! -d "venv" ]; then
    python3.10 -m venv venv
    echo "虚拟环境已创建"
else
    echo "虚拟环境已存在"
fi

# 步骤8: 安装Python依赖
echo -e "${GREEN}[8/12]${NC} 安装Python依赖..."
source venv/bin/activate
pip install --upgrade pip > /dev/null 2>&1

# 尝试使用国内镜像加速
echo "正在安装依赖（可能耗时2-3分钟）..."
if pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple > /dev/null 2>&1; then
    echo "依赖安装成功"
else
    echo -e "${YELLOW}⚠️  使用国内镜像失败，尝试官方源...${NC}"
    pip install -r requirements.txt > /dev/null 2>&1
    echo "依赖安装成功"
fi

# 步骤9: 配置环境变量
echo -e "${GREEN}[9/12]${NC} 检查环境变量配置..."
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠️  .env 文件不存在${NC}"
    echo "创建 .env 模板文件..."
    cat > .env << 'EOF'
# OKX API 配置（必须）
OKX_API_KEY=your_okx_api_key_here
OKX_SECRET=your_okx_secret_key_here
OKX_PASSWORD=your_okx_passphrase_here

# DeepSeek API 配置（必须）
DEEPSEEK_API_KEY=your_deepseek_api_key_here

# Flask 配置（可选）
SECRET_KEY=change_this_to_a_random_secret_key
EOF
    echo -e "${RED}❌ 请编辑 /dsok/.env 文件，填入您的API密钥${NC}"
    echo "使用方法: nano /dsok/.env"
    read -p "是否现在编辑 .env 文件？(y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        nano .env
    else
        echo -e "${RED}⚠️  请稍后手动编辑 .env 文件，否则程序无法正常运行${NC}"
    fi
else
    echo ".env 文件已存在"
fi

# 步骤10: 配置防火墙
echo -e "${GREEN}[10/12]${NC} 配置防火墙..."
if command -v ufw &> /dev/null; then
    if ufw status | grep -q "Status: active"; then
        ufw allow 5000/tcp > /dev/null 2>&1
        echo "已开放5000端口"
    else
        echo "防火墙未启用"
    fi
else
    echo "UFW未安装，跳过防火墙配置"
fi

# 步骤11: 设置文件权限
echo -e "${GREEN}[11/12]${NC} 设置文件权限..."
chmod +x start.sh stop.sh restart.sh status.sh
chmod 600 .env 2>/dev/null || true
chown -R $SUDO_USER:$SUDO_USER /dsok 2>/dev/null || true

# 步骤12: 验证安装
echo -e "${GREEN}[12/12]${NC} 验证安装..."
if [ -f ".env" ]; then
    # 检查.env是否包含有效配置
    if grep -q "your_okx_api_key_here" .env; then
        echo -e "${YELLOW}⚠️  警告：.env 文件仍包含模板值，请务必修改${NC}"
    else
        echo "✅ .env 文件配置正常"
    fi
fi

echo ""
echo "=========================================="
echo "✅ 部署完成！"
echo "=========================================="
echo ""
echo "📝 下一步操作："
echo ""
echo "1. 确保 .env 文件配置正确："
echo "   cd /dsok"
echo "   nano .env"
echo ""
echo "2. 测试启动服务："
echo "   cd /dsok"
echo "   ./start.sh"
echo ""
echo "3. 查看服务状态："
echo "   pm2 list"
echo "   pm2 logs"
echo ""
echo "4. 访问Web界面："
echo "   http://your-server-ip:5000"
echo ""
echo "⚠️  重要提示："
echo "- 确保阿里云安全组已开放5000端口"
echo "- 如果无法访问，检查防火墙和安全组配置"
echo "- 查看日志：pm2 logs"
echo ""
echo "=========================================="
echo ""

# 询问是否立即启动
read -p "是否现在启动服务？(y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "启动服务..."
    cd /dsok
    ./start.sh
fi

echo ""
echo -e "${GREEN}🎉 部署脚本执行完毕！${NC}"


