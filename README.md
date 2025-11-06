# 加密货币交易机器人 (DSOK Trading Bot)

基于 DeepSeek AI 的比特币自动交易系统，支持 OKX 交易所永续合约交易。

## ✨ 核心特性

- 🤖 **AI 驱动**: 基于 DeepSeek API 的智能交易信号生成
- 📊 **实时监控**: Web 界面实时显示交易状态、持仓、盈亏
- 🔐 **风险管理**: 自动止损止盈、分档移动止盈、仓位管理、流动性检查
- 📈 **数据统计**: 信号准确率统计、资金曲线分析、AI决策历史、交易记录
- 🎯 **分档移动止盈**: 整合buou_trail三档渐进式移动止盈系统，极大提高胜率
- 💾 **历史数据管理**: 自动保存余额历史到SQLite数据库，支持导出Excel
- 📊 **可视化分析**: 信号分布图表、信心等级统计图表，直观展示交易决策
- 🌐 **完整Web API**: 提供RESTful API接口，支持多模型、多交易对管理
- 🛡️ **测试模式**: 支持模拟交易，无需真实资金即可测试

**📖 详细文档**: 所有说明文档已整合到本 README.md

## 📑 目录

- [快速开始](#-快速开始)
- [Windows 本地开发调试](#-windows-本地开发调试指南)
- [阿里云 Ubuntu 服务器部署](#-阿里云-ubuntu-服务器部署指南)
- [项目结构](#-项目结构)
- [Web 界面功能](#-web-界面功能)
- [交易机器人功能](#-交易机器人功能)
- [交易策略详细说明](#-交易策略详细说明)
  - [AI决策引擎](#aidecision-engine)
  - [分档移动止盈功能](#分档移动止盈功能来自buou_trail)
  - [智能仓位管理系统](#智能仓位管理系统)
  - [杠杆设置机制](#杠杆设置机制)
- [历史数据管理](#-历史数据管理)
- [PM2 管理](#-pm2-管理)
- [工作流程](#-工作流程)
- [安全建议](#-安全建议)
- [常见问题](#-常见问题)
- [更新日志](#-更新日志)

---

## 🚀 快速开始

### 1. 环境要求

- Python 3.8+
- Node.js 14+ (用于 PM2)
- OKX API 密钥
- DeepSeek API 密钥

### 2. 服务器部署

**重要**: 本项目设计为部署在服务器根目录 `/dsok` 下。

```bash
# 克隆或上传项目到服务器
cd /
git clone <repository> dsok  # 或直接上传项目到 /dsok 目录

cd /dsok
#按照所需的包
sudo apt update
sudo apt install python3.12-venv

# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

#安装npm
sudo apt update
sudo apt install npm

# 安装 PM2 (进程管理)
npm install -g pm2

# 配置环境变量（见下方说明）
nano .env

# 启动服务
chmod +x start.sh
./start.sh
```

### 3. 配置环境变量

**在项目根目录创建 `.env` 文件**（与 `app.py` 同级）：

```bash
# OKX API 配置（必须）
OKX_API_KEY=your_api_key
OKX_SECRET=your_secret_key
OKX_PASSWORD=your_passphrase

# DeepSeek API 配置（必须）
DEEPSEEK_API_KEY=your_deepseek_api_key

# Flask 配置（可选）
SECRET_KEY=your_random_secret_key
```

**文件位置**：`/dsok/.env`

### 4. 启动服务

```bash
# 使用 PM2 启动（推荐）
pm2 start ecosystem.config.js

# 或使用脚本
./start.sh

# 查看状态
pm2 list
./status.sh

# 重启服务
./restart.sh              # 重启所有服务
./restart.sh web          # 仅重启Web服务
./restart.sh bot          # 仅重启Bot服务

# 停止服务
./stop.sh
```

### 5. 访问 Web 界面

打开浏览器访问: `http://localhost:5000`

---

## 💻 Windows 本地开发调试指南

### 环境准备

1. **安装 Python 3.8+**
   - 下载地址：https://www.python.org/downloads/
   - 安装时勾选 "Add Python to PATH"
   - 验证安装：打开 PowerShell，运行 `python --version`

2. **安装 Git（可选）**
   - 下载地址：https://git-scm.com/download/win
   - 用于版本控制和代码管理

### 快速开始

#### 步骤0: 进入项目目录（CMD 用户必看）

**如果使用 Windows CMD，默认打开在 `C:\Windows\System32>`，需要先切换到项目目录：**

```cmd
# 方法1: 使用 cd 命令切换目录（假设项目在 d:\project\dsok）
cd /d d:\project\dsok

# 方法2: 如果项目在其他位置，替换为实际路径
cd /d C:\Users\YourName\Documents\dsok

# 方法3: 先切换到 D 盘，再进入项目目录
d:
cd project\dsok

# 验证当前目录（应该显示项目文件）
dir
# 应该能看到 app.py, deepseek_ok_3.0.py, requirements.txt 等文件
```

**提示：**
- `cd /d` 可以跨盘符切换目录（如从 C: 切换到 D:）
- 如果项目在 C 盘，可以直接使用 `cd C:\path\to\dsok`
- 可以使用 `cd` 命令查看当前目录
- 可以使用 `dir` 命令查看当前目录的文件列表

#### 步骤1: 克隆或下载项目

**如果项目还未下载，先克隆或下载：**

```cmd
# 使用 Git 克隆（推荐）
git clone <repository-url> dsok
cd /d dsok

# 或直接下载 ZIP 文件并解压，然后进入解压后的目录
cd /d d:\project\dsok
```

**如果项目已存在，直接进入项目目录：**

```cmd
cd /d d:\project\dsok
```

#### 步骤2: 创建虚拟环境

**确保已在项目目录中（使用 `cd` 命令查看当前目录）**

```cmd
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境（CMD）
venv\Scripts\activate.bat

# 激活后，命令行前应显示 (venv)，表示虚拟环境已激活
# 例如：D:\project\dsok> 会变成 (venv) D:\project\dsok>
```

**如果使用 PowerShell：**

```powershell
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
.\venv\Scripts\Activate.ps1

# 如果遇到执行策略限制，先运行：
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

#### 步骤3: 安装依赖

**确保虚拟环境已激活（命令行前应显示 `(venv)`）**

```cmd
# 升级 pip
python -m pip install --upgrade pip

# 安装依赖（如果遇到权限问题，使用 --no-cache-dir）
pip install --no-cache-dir -r requirements.txt

# 如果遇到 pandas 安装问题，先单独安装 numpy
pip install --no-cache-dir numpy
pip install --no-cache-dir -r requirements.txt
```

#### 步骤4: 配置环境变量

在项目根目录创建 `.env` 文件（与 `app.py` 同级）：

```cmd
# 使用记事本创建 .env 文件（CMD）
notepad .env

# 或使用 VS Code（如果已安装）
code .env
```

在 `.env` 文件中输入：

```bash
# OKX API 配置（必须）
OKX_API_KEY=your_api_key
OKX_SECRET=your_secret_key
OKX_PASSWORD=your_passphrase

# DeepSeek API 配置（必须）
DEEPSEEK_API_KEY=your_deepseek_api_key

# Flask 配置（可选）
SECRET_KEY=your_random_secret_key
```

#### 步骤5: 测试 API 连接

```cmd
# 测试 OKX API 连接
python scripts\test_okx_api.py

# 测试本地 OKXClient 类
python test_local.py
```

#### 步骤6: 运行程序

**方式1: 直接运行（推荐用于调试）**

**重要：确保已在项目目录中，且虚拟环境已激活**

```cmd
# 运行 Web 服务（在一个 CMD 窗口）
# 1. 打开第一个 CMD 窗口
cd /d d:\project\dsok
venv\Scripts\activate.bat
python app.py

# 运行交易机器人（在另一个 CMD 窗口）
# 2. 打开第二个 CMD 窗口（新开一个 CMD）
cd /d d:\project\dsok
venv\Scripts\activate.bat
python deepseek_ok_3.0.py
```

**提示：**
- 需要同时运行两个程序时，需要打开两个 CMD 窗口
- 每个窗口都需要先进入项目目录并激活虚拟环境
- 可以使用 `Ctrl + C` 停止程序

**方式2: 使用 Python 调试器**

在 VS Code 中：
1. 打开项目文件夹
2. 按 `F5` 或点击"运行和调试"
3. 选择 "Python: Current File" 或创建 `launch.json` 配置

示例 `launch.json` 配置：

```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Python: Web App",
            "type": "python",
            "request": "launch",
            "program": "${workspaceFolder}/app.py",
            "console": "integratedTerminal",
            "envFile": "${workspaceFolder}/.env"
        },
        {
            "name": "Python: Trading Bot",
            "type": "python",
            "request": "launch",
            "program": "${workspaceFolder}/deepseek_ok_3.0.py",
            "console": "integratedTerminal",
            "envFile": "${workspaceFolder}/.env"
        }
    ]
}
```

### 调试技巧

#### 1. 查看日志输出

程序运行时会输出详细日志，包括：
- API 调用状态
- 交易信号生成
- 错误信息

#### 2. 使用测试模式

在 `bot_config.json` 中设置 `"test_mode": true`，避免真实交易：

```json
{
  "test_mode": true,
  "leverage": 10,
  "timeframe": "5m"
}
```

#### 3. 断点调试

在 VS Code 中：
- 点击行号左侧设置断点（红色圆点）
- 按 `F5` 开始调试
- 使用调试工具栏：继续(F5)、单步跳过(F10)、单步进入(F11)

#### 4. 查看变量值

调试时：
- 鼠标悬停在变量上查看值
- 在"调试控制台"中输入变量名查看
- 使用 `print()` 输出调试信息

#### 5. 常见问题排查

**问题1: 模块导入错误**
```cmd
# 检查虚拟环境是否激活
# 命令行前应显示 (venv)

# 检查模块是否安装
pip list | findstr requests
pip list | findstr pandas

# 如果未安装，重新安装
pip install --no-cache-dir requests pandas
```

**问题2: 环境变量未加载**
```cmd
# 检查 .env 文件是否存在
dir .env

# 检查当前目录（确保在项目根目录）
cd

# 手动测试环境变量
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('OKX_API_KEY')[:10] if os.getenv('OKX_API_KEY') else 'Not Found')"
```

**问题3: 端口被占用**
```cmd
# 查看 5000 端口占用
netstat -ano | findstr :5000

# 结束占用进程（替换 PID 为实际进程ID）
# 例如：如果 PID 是 12345
taskkill /PID 12345 /F
```

**问题4: 权限错误**
```cmd
# 以管理员身份运行 CMD
# 右键点击 CMD → "以管理员身份运行"

# 或使用 --user 安装到用户目录
pip install --user -r requirements.txt
```

**问题5: 找不到项目目录**
```cmd
# 查看当前目录
cd

# 列出当前目录的文件
dir

# 如果不在项目目录，切换到项目目录
cd /d d:\project\dsok

# 验证是否在正确目录（应该能看到 app.py 等文件）
dir *.py
```

**问题6: 网络连接超时（Connection Timeout）**

如果遇到 `ConnectTimeoutError` 或 `Connection to www.okx.com timed out` 错误：

**原因分析：**
- 网络防火墙阻止了连接
- 需要代理才能访问 OKX（特别是在中国大陆）
- DNS 解析问题
- 网络不稳定

**解决方案1: 检查网络连接**
```cmd
# 测试是否能访问 OKX 网站
ping www.okx.com

# 测试 HTTPS 连接
curl -I https://www.okx.com

# 如果 ping 不通，可能是网络问题或需要代理
```

**解决方案2: 配置代理（如果需要）**

如果您的网络需要代理才能访问 OKX，需要配置代理：

**方法A: 设置系统代理环境变量**
```cmd
# 设置 HTTP 代理（替换为您的代理地址和端口）
set HTTP_PROXY=http://proxy.example.com:8080
set HTTPS_PROXY=http://proxy.example.com:8080

# 如果代理需要认证
set HTTP_PROXY=http://username:password@proxy.example.com:8080
set HTTPS_PROXY=http://username:password@proxy.example.com:8080

# 然后重新运行测试
python scripts\test_okx_api.py
```

**方法B: 修改代码使用代理**

如果需要永久配置代理，可以修改 `deepseek_ok_3.0.py` 中的 `OKXClient` 类，在 `_request` 方法中添加代理参数：

```python
# 在 OKXClient._request 方法中，修改 requests 调用
response = requests.get(
    url, 
    params=params, 
    headers=headers, 
    timeout=10,
    proxies={
        'http': 'http://proxy.example.com:8080',
        'https': 'http://proxy.example.com:8080'
    }
)
```

**解决方案3: 使用 VPN 或科学上网工具**

如果在中国大陆，可能需要：
1. 使用 VPN 连接到可以访问 OKX 的网络
2. 或使用科学上网工具
3. 确保 VPN/代理已正确配置并运行

**解决方案4: 检查防火墙设置**

```cmd
# 检查 Windows 防火墙是否阻止了 Python
# 打开 Windows 防火墙设置，允许 Python 通过防火墙

# 临时关闭防火墙测试（不推荐，仅用于测试）
# 控制面板 → Windows Defender 防火墙 → 启用或关闭 Windows Defender 防火墙
```

**解决方案5: 增加超时时间**

如果网络较慢，可以增加超时时间。修改 `scripts/test_okx_api.py` 中的 `timeout` 参数：

```python
# 将 timeout=10 改为 timeout=30 或更大
response = requests.get(url, params=params, headers=headers, timeout=30)
```

**解决方案6: 使用 OKX 的备用域名**

如果 `www.okx.com` 无法访问，可以尝试：
- `okx.com`（不带 www）
- 检查 OKX 官方文档是否有其他 API 端点

**验证网络连接：**
```cmd
# 测试 DNS 解析
nslookup www.okx.com

# 测试端口连接
telnet www.okx.com 443

# 如果 telnet 不可用，使用 PowerShell
Test-NetConnection -ComputerName www.okx.com -Port 443
```

### 开发工具推荐

1. **VS Code**
   - 安装 Python 扩展
   - 安装 Python Debugger 扩展
   - 安装 Python Environment Manager 扩展

2. **PyCharm**
   - 专业版支持完整调试功能
   - 社区版也支持基本调试

3. **Postman / Thunder Client**
   - 用于测试 Web API 接口

### 访问 Web 界面

启动 Web 服务后，在浏览器中访问：
```
http://localhost:5000
```

### 停止程序

- 在运行程序的终端窗口按 `Ctrl + C`
- 或在 VS Code 调试工具栏点击"停止"按钮

---

## 🌐 阿里云 Ubuntu 服务器部署指南

### ⚡ 快速部署（推荐）

使用一键部署脚本，自动完成所有配置：

```bash
# 1. 上传项目文件到服务器 /dsok 目录

# 2. 运行部署脚本
cd /dsok
sudo bash deploy.sh

# 3. 按提示配置 .env 文件并启动服务
```

**一键部署脚本将自动完成：**
- ✅ 系统更新和工具安装
- ✅ Python 3.10 环境安装
- ✅ Node.js 和 PM2 安装
- ✅ Python 依赖安装（自动使用国内镜像）
- ✅ 虚拟环境创建
- ✅ 配置文件检查和创建
- ✅ 防火墙配置
- ✅ 文件权限设置

### 📋 准备工作

1. **购买阿里云服务器**
   - 推荐配置：2核4G内存以上
   - 系统：Ubuntu 20.04 LTS 或 22.04 LTS
   - 带宽：建议5M以上（用于访问DeepSeek API）

2. **开通安全组端口**
   - 登录阿里云控制台 → 云服务器ECS → 安全组
   - 添加入站规则：
     - 端口：`5000`（TCP）
     - 授权对象：`0.0.0.0/0`（允许所有IP访问）
   - 如果需要SSH，开放端口`22`

### 详细部署步骤

#### 步骤1: 连接到服务器

```bash
# 使用SSH连接到阿里云服务器
# 替换为您的服务器IP地址
ssh root@your-server-ip
```

#### 步骤2: 更新系统并安装必要工具

```bash
# 更新系统包
sudo apt update
sudo apt upgrade -y

# 安装必要工具
sudo apt install -y git curl wget nano
```

#### 步骤3: 安装 Python 3.10+

```bash
# 检查Python版本
python3 --version

# 如果版本低于3.10，安装Python 3.10+
sudo apt install -y software-properties-common
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update
sudo apt install -y python3.10 python3.10-venv python3-pip

# 确认Python版本
python3.10 --version
```

#### 步骤4: 安装 Node.js 和 PM2

```bash
# 安装Node.js 18.x LTS版本
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs

# 验证安装
node --version
npm --version

# 全局安装PM2进程管理器
sudo npm install -g pm2

# 设置PM2开机自启
pm2 startup systemd
# 执行上面命令后提示的命令（例如：sudo env PATH=...）
```

#### 步骤5: 上传项目文件到服务器

**方法1: 使用git克隆（推荐）**

```bash
# 克隆项目到 /dsok 目录
cd /
sudo git clone https://github.com/your-repo/dsok.git dsok
sudo chown -R $USER:$USER /dsok
cd /dsok
```

**方法2: 使用FTP工具上传**

```bash
# 在本地电脑使用FileZilla、WinSCP等工具上传项目文件夹
# 上传到服务器的 /dsok 目录

# 如果使用root用户上传，需要修改文件所有者
cd /
sudo chown -R $USER:$USER /dsok
cd /dsok
```

**方法3: 使用scp命令上传**

在本地电脑执行：

```bash
# 假设您已经在项目目录
scp -r . root@your-server-ip:/dsok
```

#### 步骤6: 创建Python虚拟环境

```bash
# 进入项目目录
cd /dsok

# 创建虚拟环境（使用Python 3.10）
python3.10 -m venv venv

# 激活虚拟环境
source venv/bin/activate

# 升级pip
pip install --upgrade pip
```

#### 步骤7: 安装Python依赖

```bash
# 确保虚拟环境已激活（命令行前应显示 (venv)）
pip install -r requirements.txt

# 如果遇到依赖安装问题，可以使用国内镜像加速
# pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

#### 步骤8: 配置环境变量

```bash
# 创建.env配置文件
cd /dsok
nano .env
```

在编辑器中输入以下内容：

```bash
# OKX API 配置（必须）
OKX_API_KEY=your_okx_api_key_here
OKX_SECRET=your_okx_secret_key_here
OKX_PASSWORD=your_okx_passphrase_here

# DeepSeek API 配置（必须）
DEEPSEEK_API_KEY=your_deepseek_api_key_here

# Flask 配置（可选）
SECRET_KEY=your_random_secret_key_here
```

保存并退出：
- 按 `Ctrl + O` 保存
- 按 `Enter` 确认
- 按 `Ctrl + X` 退出

#### 步骤9: 配置防火墙（Ufw）

```bash
# 检查防火墙状态
sudo ufw status

# 如果防火墙已启用，需要开放5000端口
sudo ufw allow 5000/tcp
sudo ufw reload

# 查看开放端口
sudo ufw status numbered
```

#### 步骤10: 修改配置文件的执行权限

```bash
cd /dsok

# 给shell脚本添加执行权限
chmod +x start.sh stop.sh restart.sh status.sh

# 验证文件权限
ls -l *.sh
```

#### 步骤11: 测试运行

```bash
cd /dsok

# 激活虚拟环境
source venv/bin/activate

# 测试启动（可以看到是否报错）
python3 app.py
# 看到 "Running on http://127.0.0.1:5000" 说明成功
# 按 Ctrl+C 停止

# 测试交易机器人脚本
python3 deepseek_ok_3.0.py
# 看到启动信息说明成功
# 按 Ctrl+C 停止
```

#### 步骤12: 使用PM2启动服务

```bash
cd /dsok

# 方式1: 使用配置文件启动（推荐）
pm2 start ecosystem.config.js

# 方式2: 使用脚本启动
./start.sh

# 查看服务状态
pm2 list

# 查看服务日志
pm2 logs

# 查看指定服务日志
pm2 logs dsok-web
pm2 logs dsok-bot

# 保存PM2配置（开机自启）
pm2 save
```

#### 步骤13: 访问Web界面

1. **在浏览器中访问**
   ```
   http://your-server-ip:5000
   ```

2. **如果无法访问，检查以下内容**
   ```bash
   # 检查PM2服务是否运行
   pm2 list
   
   # 检查5000端口是否监听
   sudo netstat -tlnp | grep 5000
   
   # 检查防火墙
   sudo ufw status
   
   # 检查阿里云安全组是否开放5000端口
   ```

### 常用管理命令

```bash
cd /dsok

# === PM2 进程管理 ===
pm2 list                              # 查看所有进程状态
pm2 status                            # 详细状态
pm2 logs                              # 查看所有日志
pm2 logs dsok-web                     # 查看Web服务日志
pm2 logs dsok-bot                     # 查看Bot服务日志
pm2 restart all                       # 重启所有服务
pm2 restart dsok-web                  # 重启Web服务
pm2 restart dsok-bot                  # 重启Bot服务
pm2 stop all                          # 停止所有服务
pm2 delete all                        # 删除所有服务（谨慎使用）

# === 使用项目脚本 ===
./start.sh                            # 启动所有服务
./stop.sh                             # 停止所有服务
./restart.sh                          # 重启所有服务
./restart.sh web                      # 只重启Web服务
./restart.sh bot                      # 只重启Bot服务
./status.sh                           # 查看服务状态

# === 查看实时日志 ===
pm2 logs --lines 100                  # 显示最近100行日志
pm2 logs --lines 100 --nostream       # 显示后退出

# === 监控性能 ===
pm2 monit                             # 实时监控（CPU、内存）

# === 更新代码后重启 ===
cd /dsok
git pull                              # 如果使用git
pm2 restart all                       # 重启服务
```

### 常见问题排查

#### 1. 无法访问Web界面

```bash
# 检查服务是否运行
pm2 list

# 检查端口是否监听
sudo netstat -tlnp | grep 5000

# 检查防火墙
sudo ufw status

# 检查阿里云安全组规则
# 登录阿里云控制台 → ECS → 安全组 → 配置规则

# 查看错误日志
pm2 logs dsok-web --lines 50
```

#### 2. 交易机器人无法运行

```bash
# 检查环境变量是否配置
cat /dsok/.env

# 检查虚拟环境是否正确
cd /dsok
source venv/bin/activate
python3 -c "import ccxt; print('OK')"

# 查看Bot错误日志
pm2 logs dsok-bot --lines 100

# 测试DeepSeek API连接
python3 -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('DEEPSEEK_API_KEY')[:10] if os.getenv('DEEPSEEK_API_KEY') else 'Not Found')"
```

#### 3. PM2启动失败

```bash
# 检查Python路径
which python3

# 检查虚拟环境路径
ls -la /dsok/venv/bin/python3

# 如果路径不对，修改ecosystem.config.js
cd /dsok
nano ecosystem.config.js
# 修改 interpreter: '/dsok/venv/bin/python3'

# 手动测试启动
cd /dsok
source venv/bin/activate
python3 app.py
```

#### 4. 依赖安装失败

```bash
# 使用国内镜像源
cd /dsok
source venv/bin/activate
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 或者使用阿里云镜像
pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
```

#### 5. 服务自动重启

```bash
# 查看重启原因
pm2 list
pm2 describe dsok-bot

# 查看错误日志
pm2 logs dsok-bot --lines 200

# 检查系统资源
free -h                              # 内存
df -h                                # 磁盘
top                                  # CPU
```

### 性能优化建议

```bash
# 1. 设置PM2自动重启
# 已在ecosystem.config.js中配置

# 2. 定期清理日志（避免磁盘满）
# 编辑crontab
sudo crontab -e
# 添加以下行（每天凌晨2点清理7天前的日志）
0 2 * * * find /dsok/logs -name "*.log" -mtime +7 -delete

# 3. 监控磁盘空间
df -h

# 4. 设置日志轮转
# PM2已配置日志轮转功能
pm2 install pm2-logrotate
```

### 备份重要数据

```bash
cd /dsok

# 创建备份目录
mkdir -p /root/backup

# 备份配置文件
cp .env /root/backup/.env.$(date +%Y%m%d)

# 备份数据文件
tar -czf /root/backup/dsok-data-$(date +%Y%m%d).tar.gz \
    trade_stats.json \
    latest_signal.json \
    trade_audit.json \
    equity_curve.json \
    take_profit_tracker.json \
    bot_config.json

# 设置定时备份（每天凌晨3点）
sudo crontab -e
# 添加以下行
0 3 * * * cd /dsok && tar -czf /root/backup/dsok-data-$(date +\%Y\%m\%d).tar.gz trade_stats.json latest_signal.json trade_audit.json equity_curve.json take_profit_tracker.json bot_config.json
```

### 安全建议

1. **修改SSH默认端口**（可选）
   ```bash
   sudo nano /etc/ssh/sshd_config
   # 修改 Port 22 为其他端口
   sudo systemctl restart sshd
   ```

2. **配置SSH密钥登录**（推荐）
   ```bash
   # 在本地电脑生成密钥对
   ssh-keygen
   
   # 上传公钥到服务器
   ssh-copy-id root@your-server-ip
   ```

3. **定期更新系统**
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```

4. **限制.env文件权限**
   ```bash
   chmod 600 /dsok/.env
   ```

### 技术支持

如果遇到问题，请检查：
1. PM2日志：`pm2 logs`
2. 系统日志：`journalctl -u pm2-*`
3. 项目README文档
4. GitHub Issues

---

## 📁 项目结构

```
dsok/
├── .env                            # 环境变量配置（需手动创建，不提交到Git）
├── .gitignore                      # Git 忽略文件配置
├── app.py                          # Flask Web 应用
├── deepseek_ok_3.0.py             # 交易机器人（主程序）
├── bot_config.json                # 机器人配置文件
├── ecosystem.config.js             # PM2 配置文件
├── requirements.txt                # Python 依赖
├── deploy.sh                       # 一键部署脚本（Ubuntu服务器）
├── README.md                       # 项目文档
├── test_local.py                   # 本地测试脚本（Windows调试用）
│
├── [运行时数据文件]（自动生成，已在.gitignore中）
│   ├── trade_stats.json            # 交易统计
│   ├── latest_signal.json          # 最新信号
│   ├── trade_audit.json            # 交易审计日志
│   ├── equity_curve.json           # 资金曲线数据
│   └── take_profit_tracker.json    # 移动止盈追踪数据
│
├── static/                         # 前端静态资源
│   ├── css/
│   │   └── style.css              # 前端样式
│   └── js/
│       └── app.js                 # 前端逻辑
│
├── templates/                      # HTML模板
│   └── index.html                 # Web 界面模板
│
├── scripts/                        # 工具脚本
│   ├── export_history.py          # 历史数据导出工具
│   └── test_okx_api.py            # OKX API 连接测试工具
│
├── data/                           # 数据目录（自动创建）
│   └── history.db                 # SQLite历史数据库
│
├── archives/                       # 归档目录（自动创建）
│   └── balances-*.xlsx            # 每日归档的Excel文件
│
├── logs/                           # 日志目录（自动创建）
│   └── app.log                    # Web 应用日志
│
└── [管理脚本]                      # 服务管理脚本
    ├── start.sh                   # 启动服务
    ├── stop.sh                    # 停止服务
    ├── restart.sh                 # 重启服务（支持单独重启）
    └── status.sh                  # 查看状态
```

**重要说明：**
- ⚠️ `.env` 文件包含敏感信息，不要提交到 Git
- 📁 `data/`、`archives/`、`logs/` 目录会在首次运行时自动创建
- 📊 运行时 JSON 数据文件会在首次运行时自动创建
- 🔧 `scripts/` 目录包含工具脚本，用于测试和导出数据

## 🎮 Web 界面功能

### 控制面板
- 一键启动/停止/重启交易机器人
- 实时状态指示器（运行中/已停止）
- 自动刷新数据（可配置刷新间隔）

### 运行状态
- 运行时长（基于 PM2 进程时间）
- BTC 实时价格
- 最新交易信号（BUY/SELL/HOLD）
- 当前持仓信息
- 累计交易次数和总盈亏

### 持仓详情
- 持仓方向、数量、开仓均价
- 持仓价值、杠杆倍数
- 占用保证金、维持保证金率
- 强平价格（风险预警）
- 未实现盈亏和盈亏比例
- 账户余额和可用余额

### AI决策历史
- 显示最近20条AI决策记录
- 展示信号类型（BUY/SELL/HOLD）、信心等级（HIGH/MEDIUM/LOW）
- 显示决策理由、价格和时间戳
- 彩色标签区分不同信号类型和信心等级
- 自动刷新，最新决策在顶部

### 交易记录
- 显示最近30条交易记录
- 展示交易方向（long/short）、价格、数量、杠杆
- 显示盈亏情况（如有）
- 显示交易时间戳
- 自动刷新，最新交易在顶部

### 信号分布与信心等级统计
- **信号分布图表**：使用环形图展示 BUY/SELL/HOLD 信号的分布比例
  - 鼠标悬停显示详细数值和百分比
  - 颜色编码：绿色（BUY）、红色（SELL）、黄色（HOLD）
- **信心等级统计图表**：使用柱状图展示 HIGH/MEDIUM/LOW 信心等级的数量分布
  - 清晰展示AI决策的信心分布情况
  - 颜色编码：绿色（HIGH）、蓝色（MEDIUM）、黄色（LOW）

### 信号准确率统计
- 总信号数、已执行数、已过滤数
- 盈利交易数和准确率
- 信号分布（BUY/SELL/HOLD）
- 信心度分布统计

### 资金曲线
- 初始资金和当前资金
- 总收益率和最大回撤
- 账户余额历史曲线图
- **支持多种时间范围**：日、7天、15天、月、年、全部
- **多模型支持**：可查看不同AI模型的资金曲线对比

### 实时日志
- 交易机器人实时日志
- 彩色标签区分日志级别
- 自动刷新，最新日志在顶部

### Web API 接口

项目提供以下 RESTful API 接口供前端调用：

- **GET `/api/status`** - 获取机器人运行状态
- **GET `/api/dashboard`** - 获取仪表板数据（所有交易对信息）
- **GET `/api/overview`** - 获取总览数据（多模型资金曲线）
- **GET `/api/models`** - 获取模型列表
- **GET `/api/ai_decisions`** - 获取AI决策历史
- **GET `/api/trades`** - 获取交易记录
- **GET `/api/signals`** - 获取信号统计（信号分布和信心等级）
- **GET `/api/kline`** - 获取K线数据
- **GET `/api/profit_curve`** - 获取收益曲线（支持时间范围筛选）
- **GET `/api/ai_model_info`** - 获取AI模型信息
- **GET `/api/signal_accuracy`** - 获取信号准确率统计
- **GET `/api/equity_curve`** - 获取资金曲线数据（兼容旧接口）
- **GET `/api/trading_logs`** - 获取交易日志

## 🤖 交易机器人功能

### 核心功能
1. **智能分析**: DeepSeek AI 分析市场趋势，生成交易信号
2. **技术指标**: MA/RSI/MACD/Bollinger Bands/ATR 等
3. **风险管理**: 
   - **分档移动止盈监控**（三档渐进式保护）
   - **自动止损**（-2.0%强制平仓）
   - ATR动态止损调整
   - 智能仓位计算
   - 流动性检查
   - 信号过滤防频繁交易
4. **执行策略**: 
    - 支持同方向加仓减仓
    - 支持反向平仓开仓
    - 支持观望（HOLD）信号

---

## 📊 交易策略详细说明

### AI决策引擎

本机器人使用 DeepSeek AI 作为决策核心，结合技术指标和市场情绪进行综合分析。

#### 决策权重配置

| 因素 | 权重 | 说明 |
|------|------|------|
| **技术指标** | 60% | 趋势、支撑阻力、K线形态是主要依据 |
| **市场情绪** | 30% | 情绪数据用于验证技术信号，不能单独作为交易理由 |
| **风险管理** | 10% | 考虑持仓、盈亏状况和止损位置 |

#### 技术指标体系

**趋势指标（最重要）**
- **SMA均线**：5周期、20周期、50周期
  - 用于判断短期、中期、长期趋势
  - 趋势强度：强势上涨/下跌、震荡整理
- **MACD**：12/26/9 经典配置
  - 判断动量方向
  - 金叉死叉信号

**动量指标**
- **RSI（14）**：超买超卖判断
  - RSI > 70：超买区域（减仓30%）
  - RSI < 30：超卖区域（减仓30%）
  - RSI 30-70：健康范围（不减仓）
- **成交量比**：判断市场活跃度

**波动指标**
- **布林带（20周期）**：价格波动区间
  - 上轨（阻力）：价格突破 → 超买信号
  - 下轨（支撑）：价格跌破 → 超卖信号
  - 中线：趋势方向
- **ATR（14周期）**：动态调整止损
  - 止损幅度 = 入场价 ± (2.0 × ATR)
  - 自动适应市场波动

**支撑阻力**
- **静态支撑/阻力**：20周期最高/最低价
- **动态支撑/阻力**：布林带上轨/下轨

#### 市场情绪数据

- **数据源**：CryptOracle 网络情绪指标
- **指标**：
  - 乐观情绪比例
  - 悲观情绪比例
  - 净值情绪（乐观 - 悲观）
- **缓存机制**：15分钟缓存，降低API请求
- **应用逻辑**：
  - 情绪与技术同向 → 增强信号信心
  - 情绪与技术背离 → 以技术为主，情绪仅参考
  - 数据延迟 → 降低权重

#### 交易决策规则

**信号生成规则**
- **强势上涨趋势** → BUY 信号
- **强势下跌趋势** → SELL 信号
- **震荡整理、无明确方向** → HOLD 信号
- **技术指标权重**：趋势 > RSI > MACD > 布林带

**防频繁交易原则**
1. **趋势持续性优先**：不因单根K线或短期波动改变整体判断
2. **持仓稳定性**：除非趋势明确反转，否则保持现有持仓方向
3. **反转确认**：需2-3个技术指标同时确认趋势反转才改变信号
4. **成本意识**：减少不必要的仓位调整
5. **信号过滤机制**：
   - 近3次出现≥3种信号 → 仅执行HIGH信心信号
   - 相同信号连续2次且间隔<1小时 → 跳过
   - 连续3次同信号 → 警告提示

**趋势跟随优先**
- 强势上涨 + 任何RSI值 → 积极BUY
- 强势下跌 + 任何RSI值 → 积极SELL
- 震荡整理 + 无明确方向 → HOLD
- 不要因轻微超买/超卖而过度HOLD

**突破交易信号**
- 价格突破关键阻力 + 成交量放大 → 高信心BUY
- 价格跌破关键支撑 + 成交量放大 → 高信心SELL

**持仓优化逻辑**
- 已有持仓且趋势延续 → 保持或BUY/SELL信号
- 趋势明确反转 → 及时反向信号
- 不因已有持仓而过度HOLD

**BTC特殊调整**
- 做多权重略大（因BTC长期呈上升趋势）

---

### 分档移动止盈功能（来自buou_trail）
分档移动止盈系统，极大提高胜率，管住双手，纪律性拉满：
- **低档保护止盈**: 盈利 ≥ 0.3% 时触发
  - 固定回撤到 0.2% 时止盈
  - 保护小额盈利不被吞噬
  
- **第一档移动止盈**: 最高盈利 ≥ 1.0% 时触发
  - 允许最高盈利回撤 20%
  - 例如：最高盈利 1.5%，回撤到 1.2% 止盈
  
- **第二档移动止盈**: 最高盈利 ≥ 3.0% 时触发
  - 允许最高盈利回撤 25%
  - 例如：最高盈利 4.0%，回撤到 3.0% 止盈

- **止损**: 亏损 ≥ 2.0% 时强制平仓

- **特点**:
  - 自动追踪最高盈利值
  - 持仓方向改变时自动重置追踪
  - 档位自动升级（只能升级，不能降级）
  - 纪律性强，严格执行止盈止损

---

### 配置参数详解

#### bot_config.json 配置

完整的 `bot_config.json` 配置示例：

```json
{
  "test_mode": true,                    // 测试模式：true=模拟交易（默认），false=实盘交易
  "leverage": 10,                       // 杠杆倍数：1-125x，建议≤10x
  "timeframe": "5m",                    // 时间周期：5m/15m/1h/4h/1d
  "base_usdt_amount": 100,              // 基础投入金额（USDT）
  
  // 分档移动止盈参数
  "stop_loss_pct": 2.0,                 // 止损百分比
  "low_trail_stop_loss_pct": 0.2,       // 低档保护止盈回撤百分比
  "trail_stop_loss_pct": 0.2,           // 第一档移动止盈回撤百分比（20%）
  "higher_trail_stop_loss_pct": 0.25,   // 第二档移动止盈回撤百分比（25%）
  "low_trail_profit_threshold": 0.3,    // 低档保护止盈触发阈值（0.3%）
  "first_trail_profit_threshold": 1.0,  // 第一档移动止盈触发阈值（1.0%）
  "second_trail_profit_threshold": 3.0  // 第二档移动止盈触发阈值（3.0%）
}
```

**配置说明**
- `test_mode`: 设置为`true`时仅模拟交易，不会真实下单
- `leverage`: 杠杆倍数，建议不超过10倍
- `timeframe`: K线周期，默认15分钟
- `base_usdt_amount`: 每次交易的基础投入USDT金额

#### .env 环境变量配置

**文件位置**：在项目根目录创建 `.env` 文件（与 `app.py` 同级）

完整配置示例：

```bash
# OKX API 配置（必须）
OKX_API_KEY=your_okx_api_key_here
OKX_SECRET=your_okx_secret_key_here
OKX_PASSWORD=your_okx_passphrase_here

# DeepSeek API 配置（必须）
DEEPSEEK_API_KEY=your_deepseek_api_key_here

# Flask 配置（可选，用于加密Session）
SECRET_KEY=your_random_secret_key_here
```

**配置获取方法**：
- **OKX API**：登录 OKX 官网 → API管理 → 创建API密钥（需开启"读取"和"交易"权限）
- **DeepSeek API**：访问 https://www.deepseek.com/ → 注册账号 → 获取API密钥

**重要提示**：修改配置后需要重启交易机器人才能生效。

---

### 智能仓位管理系统

#### 杠杆设置机制

**为什么需要初始设置杠杆？**

程序启动时会为所有交易对设置默认杠杆（如 10x），这是**必需的**，原因如下：

1. **OKX 交易所要求**
   - 在交易前必须先设置杠杆，否则可能无法下单
   - 确保每个交易对都有一个明确的杠杆值

2. **作为默认值保障**
   - 如果 AI 没有建议杠杆，或建议失败时使用默认值
   - 代码逻辑：`signal_data.get('leverage', config['leverage_default'])`

3. **作为动态调整的起点**
   - 程序启动时，所有交易对都有统一的基础杠杆
   - 后续由 AI 根据市场情况动态调整

**AI 自动调节机制**

虽然初始设置了默认杠杆，但**AI 会在每次交易周期自动调节**：

```
程序启动
  ↓
设置初始杠杆（默认值，如 10x）← 必需的初始设置
  ↓
每个交易周期（每5分钟）：
  ↓
AI 分析市场 → 建议杠杆（3-20x，如 15x 或 8x）
  ↓
执行交易前检查：
  - 如果 AI 建议 ≠ 当前杠杆 → 动态调整为 AI 建议值 ✅
  - 如果 AI 建议 = 当前杠杆 → 保持不变
  ↓
执行交易
```

**AI 杠杆建议逻辑**

AI 会根据以下因素动态建议杠杆：
- 市场趋势强度（强势趋势 → 更高杠杆）
- 技术指标信号（RSI、MACD 等）
- 历史准确率统计
- 市场波动性
- 信心等级（HIGH/MEDIUM/LOW）

**示例：**
- 强势上涨趋势 + 高信心 → AI 可能建议 15-20x
- 震荡整理 + 低信心 → AI 可能建议 3-5x
- 正常市场 + 中信心 → AI 可能建议 8-12x

**总结**
- ✅ **初始设置**：满足交易所要求 + 提供默认值保障
- ✅ **AI 调节**：根据市场情况动态优化（每次交易周期都会检查并调整）
- ✅ **两者配合**：初始设置是基础，AI 调节是优化

#### 仓位计算逻辑

**计算公式**
```
基础仓位 = base_usdt_amount (默认100 USDT)

信心度调整倍数：
  - HIGH信心   → 1.5x
  - MEDIUM信心 → 1.0x
  - LOW信心    → 0.5x

趋势调整倍数：
  - 强势上涨/下跌 → 1.2x
  - 震荡整理      → 1.0x

RSI调整倍数：
  - RSI > 75 或 RSI < 25 → 0.7x (超买超卖减仓30%)
  - RSI 30-70            → 1.0x (健康范围)

最终仓位 = 基础仓位 × 信心倍数 × 趋势倍数 × RSI倍数
```

**风险限制**
- **单次最大风险**：账户余额的 2%
- **最大仓位**：账户余额的 10%
- **自动风险验证**：潜在损失超过上限时自动调仓

**名义价值 vs 保证金**
- 使用名义价值管理（非保证金计算）
- 100 USDT 基础投入 = 100 USDT 名义价值
- 10x杠杆下，实际使用保证金约 10 USDT
- 公式：合约张数 = 名义价值 ÷ (当前价格 × 合约乘数)

#### 仓位调整策略

**加仓条件**
- 同向信号
- 建议仓位 > 当前仓位
- 差额 ≥ 0.01 张

**减仓条件**
- 同向信号
- 建议仓位 < 当前仓位
- 差额 ≥ 0.01 张

**反向交易**
- 收到反向信号时先平仓
- 清空移动止盈追踪器
- 随后按新信号开仓

---

### 流动性检查机制

为确保交易执行质量，每次交易前进行市场流动性检查：

**检查项目**
- **价差**：买卖价差 ≤ 0.1%
- **深度**：前5档订单簿深度 ≥ 1 BTC

**处理逻辑**
- 价差过大 → 延迟交易
- 深度不足 → 延迟交易
- 检查通过 → 正常执行

---

## 💾 历史数据管理

系统自动保存所有余额历史到SQLite数据库，支持按时间范围查询和导出Excel。

### 数据库存储

系统使用SQLite数据库 `data/history.db` 存储历史数据：

- **表结构**:
  - `balance_history`: 余额历史记录
    - `model`: 模型标识（如 'deepseek'）
    - `timestamp`: 时间戳
    - `total_equity`: 总权益
    - `available_balance`: 可用余额
    - `unrealized_pnl`: 未实现盈亏
    - `currency`: 货币类型（默认USDT）
  - `meta`: 元数据表（存储最后归档日期等）

### 自动数据管理

- **自动保存**: 每个交易周期自动保存余额快照到 SQLite 数据库
- **自动归档**: 每日零点后自动将前一天数据导出为Excel文件到 `archives/` 目录
  - 文件命名格式：`balances-YYYYMMDD.xlsx`（例如：`balances-20251105.xlsx`）
  - 每个文件包含该日所有模型的余额历史记录
  - 归档后的数据仍保留在数据库中，方便后续查询
- **数据压缩**: 归档后的数据保留在数据库中，可以随时导出

### archives/ 文件夹说明

**用途**：`archives/` 文件夹用于存储历史余额数据的 Excel 归档文件。

**工作原理**：
1. **自动归档**：
   - 系统在每个交易周期检查是否需要归档
   - 每日零点后，自动将前一天的数据从 SQLite 数据库导出为 Excel 文件
   - 文件保存在 `archives/` 目录下，文件名格式：`balances-YYYYMMDD.xlsx`

2. **手动导出**：
   - 使用 `scripts/export_history.py` 脚本可以导出指定时间范围的数据
   - 导出的文件也会保存到 `archives/` 目录（或自定义路径）

3. **文件内容**：
   - 每个 Excel 文件包含该时间段内所有模型的余额历史记录
   - 列包括：model（模型）、timestamp（时间戳）、total_equity（总权益）、available_balance（可用余额）、unrealized_pnl（未实现盈亏）、currency（货币类型）

4. **用途**：
   - 📊 **数据分析**：可以下载 Excel 文件进行离线分析
   - 📈 **报表生成**：可以用于生成交易报告、资金曲线分析等
   - 💾 **数据备份**：作为历史数据的备份，方便长期保存
   - 📋 **审计记录**：可以用于交易审计和合规检查

**注意事项**：
- `archives/` 目录会在首次归档时自动创建
- 归档文件会占用磁盘空间，建议定期清理旧文件
- 归档后的数据仍保留在数据库中，删除归档文件不会影响数据库查询

### 导出历史数据

使用 `scripts/export_history.py` 工具导出指定时间范围的余额历史：

```bash
# 导出指定时间范围的余额历史
python scripts/export_history.py --range 2025-01-01:2025-01-31

# 导出指定模型的数据
python scripts/export_history.py --range 2025-01-01:2025-01-31 --models deepseek

# 指定输出文件路径
python scripts/export_history.py --range 2025-01-01:2025-01-31 --output archives/custom.xlsx

# 导出指定模型的数据
python scripts/export_history.py --range 2025-01-01:2025-01-31 --models deepseek
```

**参数说明**:
- `--range`: 日期范围，格式 `YYYY-MM-DD:YYYY-MM-DD`（必填）
- `--models`: 导出的模型列表，逗号分隔（可选，默认导出全部）
- `--output`: 输出文件路径（可选，默认生成在 `archives/` 目录）

**输出文件格式**:
- Excel文件（.xlsx）
- 包含列：model, timestamp, total_equity, available_balance, unrealized_pnl, currency
- 按时间升序排列

### 数据目录结构

```
项目根目录/
├── data/
│   └── history.db          # SQLite数据库
├── archives/
│   ├── balances-20250101.xlsx        # 单日归档文件
│   ├── balances-20250101-20250131.xlsx  # 自定义导出文件
│   └── ...
└── scripts/
    └── export_history.py   # 导出工具
```

---

## ⚙️ PM2 管理

### 进程说明
- **dsok-web**: Web 应用（端口 5000）
- **dsok-bot**: 交易机器人（使用 `deepseek_ok_3.0.py`）

### 使用脚本（推荐）

```bash
# 启动所有服务
./start.sh

# 查看运行状态
./status.sh

# 重启所有服务
./restart.sh

# 单独重启Web服务
./restart.sh web

# 单独重启Bot服务
./restart.sh bot

# 停止所有服务
./stop.sh
```

### PM2 直接命令

```bash
# 启动所有服务
pm2 start ecosystem.config.js

# 查看进程状态
pm2 list

# 查看日志
pm2 logs dsok-web --lines 50
pm2 logs dsok-bot --lines 50

# 重启服务
pm2 restart dsok-web
pm2 restart dsok-bot

# 停止服务
pm2 stop dsok-web
pm2 stop dsok-bot

# 保存进程列表（开机自启）
pm2 save
pm2 startup
```

---

## ⏱️ 工作流程

### 执行周期

机器人每5分钟执行一次完整分析和交易流程：

```
┌─────────────────────────────────────────┐
│  每个5分钟整点执行一次完整循环          │
└─────────────────────────────────────────┘
              ↓
    ┌────────────────────┐
    │  步骤1: 止损止盈检查 │
    └────────────────────┘
              ↓
    ┌─────────────────────┐
    │  步骤2: 获取市场数据  │
    └─────────────────────┘
              ↓
    ┌─────────────────────┐
    │  步骤3: AI分析决策    │
    └─────────────────────┘
              ↓
    ┌─────────────────────┐
    │  步骤4: 执行交易决策  │
    └─────────────────────┘
              ↓
         等待下一周期
```

### 详细流程说明

**步骤1: 止损止盈检查**
1. 读取当前持仓
2. 计算当前盈利百分比
3. 加载并更新最高盈利追踪器
4. 判断当前档位（无/低档/一档/二档）
5. 检查触发条件：
   - 低档：盈利回撤到 0.2%
   - 一档：盈利回撤20%
   - 二档：盈利回撤25%
   - 止损：亏损达到-2%
6. 触发平仓则清空追踪器并记录审计日志

**步骤2: 获取市场数据**
1. 拉取96根5分钟K线（8小时数据）
2. 计算技术指标：MA、RSI、MACD、布林带、ATR
3. 分析趋势：短期、中期、整体趋势
4. 计算支撑阻力位
5. 获取市场情绪数据（带缓存）

**步骤3: AI分析决策**
1. 构建DeepSeek Prompt：
   - K线数据（最近5根）
   - 技术分析文本
   - 历史信号
   - 市场情绪
   - 当前持仓
2. 调用DeepSeek API（温度0.1，确保稳定）
3. 解析JSON信号
4. ATR动态调整止损位
5. 保存信号到历史和文件

**步骤4: 执行交易决策**
1. 信号过滤检查：
   - 频繁切换检查
   - 连续相同检查
   - 时间间隔验证
2. 计算智能仓位
3. 风险管理检查
4. 流动性检查
5. 执行交易：
   - 无持仓 → 开仓
   - 同向 → 加减仓
   - 反向 → 平仓后开仓
   - HOLD → 不操作
6. 更新交易统计和审计日志

---

## 🔒 安全建议

1. **API 密钥**: 使用环境变量存储，不要提交到 Git
2. **测试模式**: 新手建议长期使用测试模式
3. **风险控制**: 
   - 不要使用全部资金
   - 设置合理止损
   - 避免过高杠杆（建议 ≤ 10x）
4. **监控**: 定期检查持仓状态、强平价格、账户余额

## 🚨 常见问题

### 机器人无法启动
```bash
# 检查进程和日志
pm2 list
pm2 logs dsok-bot --err --lines 50

# 检查配置文件
cat bot_config.json
cat .env
```

### Web 界面无法访问
```bash
# 检查 Web 服务
pm2 list | grep dsok-web
pm2 logs dsok-web --lines 30

# 检查端口
netstat -tuln | grep 5000
```

### 数据不显示
```bash
# 检查数据文件
ls -lh *.json

# 检查文件权限
chmod 666 *.json

# 重启服务
pm2 restart all
```

## 📝 更新日志

### v3.4 (2025-11-05) - API优化与文档完善版
- ✅ **修复 OKX API 签名问题**：修复 POST 请求签名错误（50113 Invalid Sign），确保签名与发送的 body 完全一致
- ✅ **移除 ccxt 依赖**：完全使用直接 OKX API 调用，避免市场数据解析问题
- ✅ **Windows 本地调试支持**：添加完整的 Windows CMD 调试指南
- ✅ **杠杆设置说明**：详细说明初始杠杆设置与 AI 自动调节的关系
- ✅ **网络连接问题排查**：添加网络超时、代理配置等问题的解决方案
- ✅ **项目清理**：删除临时文件、备份文件和诊断脚本

### v3.3 (2025-11-04) - Web功能增强版
- ✅ **新增AI决策历史展示**：Web界面显示最近20条AI决策记录，包含信号类型、信心等级、决策理由等
- ✅ **新增交易记录展示**：Web界面显示最近30条交易记录，包含交易方向、价格、数量、盈亏等
- ✅ **新增信号分布图表**：使用Chart.js环形图展示BUY/SELL/HOLD信号分布比例
- ✅ **新增信心等级统计图表**：使用Chart.js柱状图展示HIGH/MEDIUM/LOW信心等级分布
- ✅ **新增Web API接口**：
  - `/api/dashboard` - 仪表板数据接口
  - `/api/kline` - K线数据接口
  - `/api/profit_curve` - 收益曲线接口（支持时间范围筛选）
  - `/api/ai_model_info` - AI模型信息接口
- ✅ **资金曲线功能增强**：支持多种时间范围（日、7天、15天、月、年、全部）和多模型对比
- ✅ **项目清理**：删除所有备份文件、临时文件和alpha参考文件夹
- ✅ **README更新**：整合所有新功能说明到README.md

### v3.2 (2025-11-04) - 分档移动止盈版
- ✅ **新增分档移动止盈功能**: 整合buou_trail分档移动止盈系统，极大提高胜率
  - 低档保护止盈：盈利 ≥ 0.3% 触发，回撤到 0.2% 止盈
  - 第一档移动止盈：盈利 ≥ 1.0% 触发，回撤 20% 止盈
  - 第二档移动止盈：盈利 ≥ 3.0% 触发，回撤 25% 止盈
  - 自动追踪最高盈利，持仓方向改变时自动重置
- ✅ **策略详细说明**：补充AI决策引擎、技术指标、仓位管理、工作流程等详细文档
- ✅ **历史数据管理**：自动保存余额历史到SQLite数据库，支持导出Excel
- ✅ **执行周期优化**：从15分钟改为5分钟执行周期，提高响应速度
- ✅ **自动杠杆设置**：AI建议杠杆倍数，动态调整杠杆
- ✅ **项目结构优化**：所有文件整合到根目录，删除冗余文件夹
- ✅ **优化配置参数**：支持灵活配置止盈阈值
- ✅ **修复 PM2 配置**：修复 PM2 配置文件路径问题（使用绝对路径 `/dsok`）
- ✅ **优化 shell 脚本**：使用绝对路径
- ✅ **添加 `.gitignore`**：规范版本控制
- ✅ **移除未使用的依赖**：移除 `schedule` 依赖
- ✅ **优化代码导入结构**
- ✅ **新增阿里云 Ubuntu 服务器详细部署指南**
- ✅ **新增一键部署脚本 `deploy.sh`**

### v3.1 (2025-10-31)
- ✅ 修复信号准确率统计和资金曲线数据问题
- ✅ 优化审计日志记录逻辑
- ✅ 修复初始资金和当前资金计算
- ✅ 增强数据一致性验证
- ✅ 支持所有信号类型（BUY/SELL/HOLD）的审计记录

### v3.0
- ✅ 信号准确率统计功能
- ✅ 资金曲线图表功能
- ✅ 交易审计日志系统
- ✅ 优化版交易机器人

### v2.1
- ✅ 重构控制面板
- ✅ 新增重启机器人功能
- ✅ 修复运行时长显示
- ✅ 增强持仓详情显示

## ⚠️ 免责声明

本项目仅供学习和研究使用。

- 加密货币交易具有高风险，可能导致资金损失
- 作者不对使用本软件造成的任何损失负责
- 请在充分了解风险的情况下使用
- 建议先在测试模式下运行，验证策略有效性
- 真实交易前请谨慎评估自身风险承受能力

---

**项目版本**: v3.4 API优化与文档完善版  
**最后更新**: 2025-11-05  
**开发状态**: 活跃开发中  
**特别感谢**: 整合了 buou_trail 的分档移动止盈系统
