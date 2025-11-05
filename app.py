from flask import Flask, render_template, jsonify, request, abort
from flask_socketio import SocketIO, emit
import os
import time
import threading
from datetime import datetime
import json
from dotenv import load_dotenv
# ccxt 已替换为 OKXClient，从 deepseek_ok_3.0 导入
import pandas as pd
from openai import OpenAI
import logging
import hashlib
import hmac
import secrets
from functools import wraps

# 获取项目根目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 加载环境变量
load_dotenv(os.path.join(BASE_DIR, '.env'))

# 确保日志目录存在
log_dir = os.path.join(BASE_DIR, 'logs')
os.makedirs(log_dir, exist_ok=True)

# 自定义日志过滤器，过滤无害的404错误和Socket.IO噪音日志
class IgnoreStaticCSSFilter(logging.Filter):
    def filter(self, record):
        # 过滤掉特定CSS文件的404请求日志
        ignored_paths = [
            '/static/js/css/modules/code.css',
            '/static/js/theme/default/layer.css',
            '/static/js/css/modules/laydate/default/laydate.css'
        ]
        
        message = record.getMessage()
        # 如果日志消息包含这些路径且返回404，则过滤掉
        if any(path in message and '404' in message for path in ignored_paths):
            return False
        return True

# Socket.IO 日志过滤器 - 过滤正常的连接/断开和轮询请求
class SocketIOFilter(logging.Filter):
    def filter(self, record):
        message = record.getMessage()
        # 过滤掉 Socket.IO 的正常轮询请求日志
        if 'transport=polling' in message and 'GET /socket.io/' in message:
            return False
        # 过滤掉 WebSocket 升级失败的警告（正常现象）
        if 'Failed websocket upgrade' in message or 'no PING packet' in message:
            return False
        # 过滤掉正常的 PING/PONG 包日志
        if 'Sending packet PING' in message or 'Sending packet PONG' in message:
            return False
        # 过滤掉正常的客户端断开日志（已在应用层记录）
        if 'Client is gone, closing socket' in message:
            return False
        return True

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_dir, 'app.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 为werkzeug日志添加过滤器
werkzeug_logger = logging.getLogger('werkzeug')
werkzeug_logger.addFilter(IgnoreStaticCSSFilter())

# 为 Socket.IO 和 EngineIO 日志添加过滤器
socketio_filter = SocketIOFilter()
engineio_logger = logging.getLogger('engineio.server')
engineio_logger.addFilter(socketio_filter)
socketio_logger = logging.getLogger('socketio.server')
socketio_logger.addFilter(socketio_filter)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', secrets.token_hex(32))
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# 安全配置
app.config['WTF_CSRF_ENABLED'] = True
app.config['WTF_CSRF_TIME_LIMIT'] = 3600

# Socket.IO 配置优化：减少日志输出，改善 WebSocket 升级
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    logger=False,  # 关闭 Socket.IO 默认日志（使用自定义日志）
    engineio_logger=False,  # 关闭 EngineIO 默认日志（使用自定义日志）
    async_mode='threading',
    ping_timeout=60,  # WebSocket ping 超时时间（秒）
    ping_interval=25,  # WebSocket ping 间隔（秒）
    max_http_buffer_size=1e6  # 最大 HTTP 缓冲区大小
)

# 安全配置
RATE_LIMIT = {}  # 简单的速率限制
MAX_REQUESTS_PER_MINUTE = 60

# 安全装饰器
def rate_limit(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        client_ip = request.remote_addr
        current_time = time.time()
        
        if client_ip in RATE_LIMIT:
            if current_time - RATE_LIMIT[client_ip]['last_request'] < 60:
                if RATE_LIMIT[client_ip]['count'] >= MAX_REQUESTS_PER_MINUTE:
                    logger.warning(f"Rate limit exceeded for IP: {client_ip}")
                    return jsonify({'error': 'Rate limit exceeded'}), 429
                RATE_LIMIT[client_ip]['count'] += 1
            else:
                RATE_LIMIT[client_ip] = {'count': 1, 'last_request': current_time}
        else:
            RATE_LIMIT[client_ip] = {'count': 1, 'last_request': current_time}
        
        return f(*args, **kwargs)
    return decorated_function

def validate_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 简单的API密钥验证（生产环境应使用更安全的方法）
        api_key = request.headers.get('X-API-Key')
        if not api_key or api_key != os.getenv('API_KEY', 'default-key'):
            logger.warning(f"Invalid API key from IP: {request.remote_addr}")
            return jsonify({'error': 'Invalid API key'}), 401
        return f(*args, **kwargs)
    return decorated_function

# 错误处理
@app.errorhandler(400)
def bad_request(error):
    logger.error(f"Bad request: {error}")
    return jsonify({'error': 'Bad request'}), 400

@app.errorhandler(401)
def unauthorized(error):
    logger.error(f"Unauthorized: {error}")
    return jsonify({'error': 'Unauthorized'}), 401

@app.errorhandler(403)
def forbidden(error):
    logger.error(f"Forbidden: {error}")
    return jsonify({'error': 'Forbidden'}), 403

@app.errorhandler(404)
def not_found(error):
    # 过滤掉已知的无害404错误（第三方库尝试加载的CSS文件）
    ignored_paths = [
        '/static/js/css/modules/code.css',
        '/static/js/theme/default/layer.css',
        '/static/js/css/modules/laydate/default/laydate.css'
    ]
    
    request_path = request.path
    # 如果是被忽略的路径，不记录错误日志
    if not any(ignored in request_path for ignored in ignored_paths):
        logger.error(f"Not found: {error}")
    
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(429)
def rate_limit_exceeded(error):
    logger.error(f"Rate limit exceeded: {error}")
    return jsonify({'error': 'Rate limit exceeded'}), 429

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal error: {error}")
    return jsonify({'error': 'Internal server error'}), 500

# 配置文件路径
BOT_CONFIG_FILE = os.path.join(BASE_DIR, 'bot_config.json')
SIGNAL_FILE = os.path.join(BASE_DIR, 'latest_signal.json')
TRADE_STATS_FILE = os.path.join(BASE_DIR, 'trade_stats.json')
TRADE_AUDIT_FILE = os.path.join(BASE_DIR, 'trade_audit.json')
EQUITY_CURVE_FILE = os.path.join(BASE_DIR, 'equity_curve.json')

# 读取交易统计信息
def load_trade_stats():
    """从文件加载交易统计信息"""
    try:
        if os.path.exists(TRADE_STATS_FILE):
            with open(TRADE_STATS_FILE, 'r', encoding='utf-8') as f:
                stats = json.load(f)
                logger.info(f"✅ 成功加载交易统计: {stats.get('total_trades', 0)} 次交易")
                return stats
        else:
            # 文件不存在，创建默认统计信息并保存
            logger.warning(f"⚠️ 交易统计文件不存在，创建新文件: {TRADE_STATS_FILE}")
            default_stats = {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'last_updated': None
            }
            # 立即保存默认统计，确保文件存在
            save_trade_stats(default_stats)
            return default_stats
    except Exception as e:
        logger.error(f"❌ 读取交易统计文件失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        # 返回默认值，但不创建文件（避免覆盖可能存在的数据）
        return {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'last_updated': None
        }

def save_trade_stats(stats):
    """保存交易统计信息到文件"""
    try:
        stats['last_updated'] = datetime.now().isoformat()
        
        # 确保目录存在
        stats_dir = os.path.dirname(TRADE_STATS_FILE)
        if not os.path.exists(stats_dir):
            os.makedirs(stats_dir, exist_ok=True)
            logger.info(f"创建交易统计目录: {stats_dir}")
        
        with open(TRADE_STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✅ 交易统计已保存: {stats['total_trades']} 次交易 -> {TRADE_STATS_FILE}")
        return True
    except Exception as e:
        logger.error(f"❌ 保存交易统计文件失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

# 读取最新交易信号
_last_signal_file_check = None
def load_latest_signal():
    """从文件加载最新交易信号"""
    global _last_signal_file_check
    try:
        if os.path.exists(SIGNAL_FILE):
            with open(SIGNAL_FILE, 'r', encoding='utf-8') as f:
                signal = json.load(f)
                logger.debug(f"成功读取信号: {signal.get('signal', 'UNKNOWN')}, 时间: {signal.get('timestamp', 'N/A')}")
                _last_signal_file_check = None  # 文件存在后，重置检查标记
                return signal
        else:
            # 只在首次检查时记录一次警告，避免重复日志
            if _last_signal_file_check is None:
                logger.debug(f"信号文件不存在（首次检查）: {SIGNAL_FILE}，等待交易机器人生成信号...")
                _last_signal_file_check = True
            return None
    except Exception as e:
        logger.error(f"读取信号文件失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None

# 读取机器人配置文件
def load_bot_config():
    """从配置文件加载机器人配置"""
    try:
        if os.path.exists(BOT_CONFIG_FILE):
            with open(BOT_CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            # 默认配置
            default_config = {
                'test_mode': True,
                'leverage': 10,
                'timeframe': '15m',
                'base_usdt_amount': 100,
                'last_updated': datetime.now().isoformat()
            }
            save_bot_config(default_config)
            return default_config
    except Exception as e:
        logger.error(f"读取机器人配置失败: {e}")
        return {'test_mode': True, 'leverage': 10, 'timeframe': '15m', 'base_usdt_amount': 100}

# 保存机器人配置文件
def save_bot_config(config):
    """保存配置到文件"""
    try:
        config['last_updated'] = datetime.now().isoformat()
        with open(BOT_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        logger.info(f"配置已保存到: {BOT_CONFIG_FILE}")
        return True
    except Exception as e:
        logger.error(f"保存机器人配置失败: {e}")
        return False

# 全局变量
bot_running = False
bot_thread = None
price_history = []
signal_history = []
position = None

# 从配置文件加载配置
bot_config = load_bot_config()

# 安全获取配置值，确保类型正确
def safe_get_config(key, default):
    """安全获取配置值，处理None值"""
    value = bot_config.get(key, default)
    if value is None:
        return default
    return value

trading_config = {
    'symbol': 'BTC/USDT:USDT',  # OKX永续合约格式
    'amount': 0.01,
    'leverage': int(safe_get_config('leverage', 10)),
    'timeframe': safe_get_config('timeframe', '15m'),
    'test_mode': safe_get_config('test_mode', True),
    'base_usdt_amount': float(safe_get_config('base_usdt_amount', 100)),
    'auto_refresh': True,
    'refresh_interval': 2
}

# 检查DeepSeek API密钥配置
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')
if not DEEPSEEK_API_KEY:
    logger.warning("DeepSeek API密钥未配置，AI分析功能将不可用")
    deepseek_client = None
else:
    # 初始化DeepSeek客户端
    deepseek_client = OpenAI(
        api_key=DEEPSEEK_API_KEY,
        base_url="https://api.deepseek.com"
    )
    api_key_display = DEEPSEEK_API_KEY[:8] if DEEPSEEK_API_KEY and len(DEEPSEEK_API_KEY) >= 8 else 'N/A'
    logger.info(f"DeepSeek客户端已初始化 (API Key: {api_key_display}...)")

# 检查OKX API密钥配置（本项目强制要求配置）
OKX_API_KEY = os.getenv('OKX_API_KEY')
OKX_SECRET = os.getenv('OKX_SECRET')
OKX_PASSWORD = os.getenv('OKX_PASSWORD')

if not OKX_API_KEY or not OKX_SECRET or not OKX_PASSWORD:
    error_msg = """
    ❌ 错误：OKX API密钥未配置！
    
    本项目仅支持OKX交易所，必须配置OKX API密钥才能运行。
    
    请按以下步骤配置：
    
    1. 编辑配置文件：
       nano .env
    
    2. 填入您的OKX API密钥：
       OKX_API_KEY=your-okx-api-key
       OKX_SECRET=your-okx-secret-key
       OKX_PASSWORD=your-okx-api-password
    
    3. 重启服务：
       pm2 restart dsok
    
    获取OKX API密钥：https://www.okx.com/account/my-api
    """
    logger.error(error_msg)
    print(error_msg)
    raise SystemExit("OKX API密钥未配置，服务无法启动")

# 初始化OKX交易所（本项目仅支持OKX）
# 使用 OKXClient 替代 ccxt
try:
    # 动态导入 OKXClient（因为 deepseek_ok_3.0.py 文件名包含点号）
    # 尝试直接导入（如果已经在同一进程中）
    try:
        import deepseek_ok_3_0 as deepseek_module
    except ImportError:
        # 如果导入失败，使用动态导入
        import importlib.util
        module_path = os.path.join(BASE_DIR, 'deepseek_ok_3.0.py')
        spec = importlib.util.spec_from_file_location("deepseek_ok_3_0", module_path)
        deepseek_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(deepseek_module)
    OKXClient = deepseek_module.OKXClient
    
    exchange = OKXClient(
        api_key=OKX_API_KEY,
        secret=OKX_SECRET,
        password=OKX_PASSWORD,
        sub_account=None,
        sandbox=False,
        enable_rate_limit=True
    )
    api_key_display = OKX_API_KEY[:8] if OKX_API_KEY and len(OKX_API_KEY) >= 8 else 'N/A'
    logger.info(f"OKX交易所已初始化 (API Key: {api_key_display}...)")
except Exception as e:
    logger.error(f"OKX交易所初始化失败: {e}")
    logger.error("请检查API密钥格式是否正确")
    exchange = None  # 设置为None，后续检查


def setup_exchange():
    """设置OKX交易所参数（本项目仅支持OKX交易所）"""
    try:
        # 检查exchange是否已初始化
        if exchange is None:
            logger.error("OKX交易所未初始化，无法设置")
            return False
        
        # 确保杠杆配置有效
        leverage = trading_config.get('leverage', 10)
        if leverage is None:
            leverage = 10
            trading_config['leverage'] = leverage
            logger.warning("杠杆配置为None，使用默认值10x")
        
        # 确保leverage是数字类型
        try:
            leverage = int(leverage)
        except (ValueError, TypeError):
            logger.warning(f"杠杆配置无效: {leverage}，使用默认值10")
            leverage = 10
            trading_config['leverage'] = leverage
        
        # OKX设置杠杆（直接API调用）
        inst_id = 'BTC-USDT-SWAP'
        params = {
            'lever': str(leverage),
            'instId': inst_id,
            'mgnMode': 'cross'
        }
        exchange.private_post_account_set_leverage(params)
        logger.info(f"OKX杠杆已设置: {leverage}x")
        
        # 获取OKX账户余额（直接API调用，使用account/balance端点）
        balance_response = exchange.private_get_account_balance({'ccy': 'USDT'})
        if not balance_response or 'data' not in balance_response or not balance_response['data']:
            raise Exception(f"获取账户余额失败: API返回数据为空")
        
        account_data = balance_response['data'][0]
        details = account_data.get('details', [])
        
        usdt_balance = 0
        for detail in details:
            if detail.get('ccy') == 'USDT':
                avail_bal = detail.get('availBal') or detail.get('availEq') or detail.get('eq')
                if avail_bal is not None:
                    usdt_balance = float(avail_bal)
                else:
                    usdt_balance = float(detail.get('availBal', 0))
                break
        
        # 如果details中没有找到，使用总可用权益
        if usdt_balance == 0:
            avail_eq = account_data.get('availEq')
            if avail_eq:
                usdt_balance = float(avail_eq)
        
        logger.info(f"OKX账户USDT余额: {usdt_balance:.2f} USDT")
        
        # 验证API连接
        logger.info("OKX API连接验证成功")
        return True
    except Exception as e:
        logger.error(f"OKX交易所设置失败: {e}")
        logger.error(f"错误类型: {type(e).__name__}")
        import traceback
        logger.error(f"详细错误信息: {traceback.format_exc()}")
        logger.error("请检查OKX API密钥是否正确，以及是否设置了IP白名单")
        return False

def get_btc_ohlcv():
    """从OKX获取BTC/USDT永续合约K线数据"""
    try:
        if exchange is None:
            logger.error("OKX交易所未初始化，无法获取K线数据")
            return None
        
        # 获取K线数据（直接API调用）
        inst_id = 'BTC-USDT-SWAP'
        bar_map = {
            '15m': '15m',
            '1h': '1H',
            '4h': '4H',
            '1d': '1D'
        }
        bar = bar_map.get(trading_config['timeframe'], '15m')
        
        params = {
            'instId': inst_id,
            'bar': bar,
            'limit': '10'
        }
        response = exchange.public_get_market_candles(params)
        
        if not response or 'data' not in response or not response['data']:
            raise Exception(f"获取K线数据失败: API返回数据为空")
        
        # 转换OKX格式到标准OHLCV格式
        ohlcv_data = []
        for candle in reversed(response['data']):  # OKX返回的是倒序
            ohlcv_data.append([
                int(candle[0]),  # timestamp (ms)
                float(candle[1]),  # open
                float(candle[2]),  # high
                float(candle[3]),  # low
                float(candle[4]),  # close
                float(candle[5])   # volume
            ])
        ohlcv = ohlcv_data
        
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        current_data = df.iloc[-1]
        previous_data = df.iloc[-2] if len(df) > 1 else current_data
        
        return {
            'price': float(current_data['close']),
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'high': float(current_data['high']),
            'low': float(current_data['low']),
            'volume': float(current_data['volume']),
            'timeframe': trading_config['timeframe'],
            'price_change': ((current_data['close'] - previous_data['close']) / previous_data['close']) * 100,
            'kline_data': df[['timestamp', 'open', 'high', 'low', 'close', 'volume']].tail(5).to_dict('records')
        }
    except Exception as e:
        logger.error(f"获取OKX K线数据失败: {e}")
        return None

def get_current_position():
    """从OKX获取当前持仓情况（增强版）"""
    try:
        if exchange is None:
            logger.error("OKX交易所未初始化，无法获取持仓信息")
            return None
        
        symbol = 'BTC/USDT:USDT'  # OKX永续合约格式
        inst_id = 'BTC-USDT-SWAP'
        
        # 获取持仓（直接API调用）
        response = exchange.private_get_account_positions({'instId': inst_id})
        if not response or 'data' not in response:
            raise Exception(f"获取持仓失败: API返回数据为空")
        
        positions_data = response['data']
        logger.info(f"获取到 {len(positions_data)} 个持仓数据")
        
        # 获取账户余额（直接API调用，使用account/balance端点）
        balance_response = exchange.private_get_account_balance({'ccy': 'USDT'})
        if not balance_response or 'data' not in balance_response or not balance_response['data']:
            raise Exception(f"获取账户余额失败: API返回数据为空")
        
        account_data = balance_response['data'][0]
        details = account_data.get('details', [])
        
        free_balance = 0
        total_balance = 0
        for detail in details:
            if detail.get('ccy') == 'USDT':
                avail_bal = detail.get('availBal') or detail.get('availEq') or detail.get('eq')
                total_bal = detail.get('bal') or detail.get('eq') or detail.get('frozenBal')
                if avail_bal is not None:
                    free_balance = float(avail_bal)
                else:
                    free_balance = float(detail.get('availBal', 0))
                if total_bal is not None:
                    total_balance = float(total_bal)
                else:
                    total_balance = float(detail.get('bal', 0))
                break
        
        # 如果details中没有找到，使用总权益
        if free_balance == 0:
            avail_eq = account_data.get('availEq')
            if avail_eq:
                free_balance = float(avail_eq)
        if total_balance == 0:
            eq_usd = account_data.get('eqUsd')
            if eq_usd:
                total_balance = float(eq_usd)
        
        for i, pos_data in enumerate(positions_data):
            # 处理OKX格式的持仓数据
            if pos_data.get('instId') == inst_id:
                # 获取持仓数量（OKX格式）
                pos = float(pos_data.get('pos', 0))  # 持仓数量（正数=多头，负数=空头）
                
                if abs(pos) > 0:
                    # 确定持仓方向
                    side = 'long' if pos > 0 else 'short'
                    contracts = abs(pos)
                    
                    logger.info(f"✅ 检测到持仓: {side}, 数量={contracts}")
                    
                    # 获取持仓信息
                    entry_price = float(pos_data.get('avgPx', 0))  # 平均开仓价
                    unrealized_pnl = float(pos_data.get('upl', 0))  # 未实现盈亏
                    leverage = float(pos_data.get('lever', trading_config['leverage']))
                    mark_price = float(pos_data.get('markPx', entry_price))  # 标记价格
                    
                    # 获取保证金信息
                    initial_margin = float(pos_data.get('imr', 0))  # 初始保证金要求
                    maint_margin = float(pos_data.get('mmr', 0))  # 维持保证金要求
                    liquidation_price = float(pos_data.get('liqPx', 0))  # 强平价格
                    
                    # 维持保证金率
                    maint_margin_ratio = float(pos_data.get('mgnRatio', 0))  # OKX直接返回百分比
                    if maint_margin_ratio > 0:
                        maint_margin_ratio = maint_margin_ratio * 100  # 转换为百分比
                    
                    logger.info(f"持仓详情: 开仓价={entry_price}, 未实现盈亏={unrealized_pnl}, 保证金={initial_margin}, 强平价={liquidation_price}")
                    
                    return {
                        'side': side,  # 'long' 或 'short'
                        'size': contracts,  # 持仓数量
                        'entry_price': entry_price,
                        'mark_price': mark_price,
                        'unrealized_pnl': unrealized_pnl,
                        'position_amt': pos,  # 保留原始值（可能有正负）
                        'symbol': symbol,
                        'leverage': leverage,
                        'initial_margin': initial_margin,
                        'maint_margin': maint_margin,
                        'maint_margin_ratio': maint_margin_ratio,  # 维持保证金率
                        'liquidation_price': liquidation_price,
                        'total_balance': total_balance,
                        'free_balance': free_balance
                    }
        
        # 无持仓时返回账户信息（DEBUG级别，避免无持仓时的噪音日志）
        logger.debug(f"未检测到持仓 (遍历了{len(positions_data)}个持仓数据)")
        return {
            'total_balance': total_balance,
            'free_balance': free_balance
        }
    except Exception as e:
        logger.error(f"获取OKX持仓失败: {e}")
        return None

def analyze_with_deepseek(price_data):
    """使用DeepSeek分析市场并生成交易信号"""
    global price_history, signal_history
    
    # 检查DeepSeek客户端是否已初始化
    if not deepseek_client:
        logger.error("DeepSeek API未配置，无法进行AI分析")
        return None
    
    price_history.append(price_data)
    if len(price_history) > 20:
        price_history.pop(0)
    
    # 构建K线数据文本
    kline_text = f"【最近5根{trading_config['timeframe']}K线数据】\n"
    for i, kline in enumerate(price_data['kline_data']):
        trend = "阳线" if kline['close'] > kline['open'] else "阴线"
        change = ((kline['close'] - kline['open']) / kline['open']) * 100
        kline_text += f"K线{i + 1}: {trend} 开盘:{kline['open']:.2f} 收盘:{kline['close']:.2f} 涨跌:{change:+.2f}%\n"
    
    # 构建技术指标文本
    if len(price_history) >= 5:
        closes = [data['price'] for data in price_history[-5:]]
        sma_5 = sum(closes) / len(closes)
        price_vs_sma = ((price_data['price'] - sma_5) / sma_5) * 100
        indicator_text = f"【技术指标】\n5周期均价: {sma_5:.2f}\n当前价格相对于均线: {price_vs_sma:+.2f}%"
    else:
        indicator_text = "【技术指标】\n数据不足计算技术指标"
    
    # 添加上次交易信号
    signal_text = ""
    if signal_history:
        last_signal = signal_history[-1]
        signal_text = f"\n【上次交易信号】\n信号: {last_signal.get('signal', 'N/A')}\n信心: {last_signal.get('confidence', 'N/A')}"
    
    # 添加当前持仓信息
    current_pos = get_current_position()
    position_text = "无持仓" if not current_pos else f"{current_pos['side']}仓, 数量: {current_pos['size']}, 盈亏: {current_pos['unrealized_pnl']:.2f}USDT"
    
    prompt = f"""
    你是一个专业的加密货币交易分析师。请基于以下BTC/USDT {trading_config['timeframe']}周期数据进行分析：
    
    {kline_text}
    
    {indicator_text}
    
    {signal_text}
    
    【当前行情】
    - 当前价格: ${price_data['price']:,.2f}
    - 时间: {price_data['timestamp']}
    - 本K线最高: ${price_data['high']:,.2f}
    - 本K线最低: ${price_data['low']:,.2f}
    - 本K线成交量: {price_data['volume']:.2f} BTC
    - 价格变化: {price_data['price_change']:+.2f}%
    - 当前持仓: {position_text}
    
    【分析要求】
    1. 基于{trading_config['timeframe']}K线趋势和技术指标给出交易信号: BUY(买入) / SELL(卖出) / HOLD(观望)
    2. 简要分析理由（考虑趋势连续性、支撑阻力、成交量等因素）
    3. 基于技术分析建议合理的止损价位
    4. 基于技术分析建议合理的止盈价位
    5. 评估信号信心程度
    
    请用以下JSON格式回复：
    {{
        "signal": "BUY|SELL|HOLD",
        "reason": "分析理由",
        "stop_loss": 具体价格,
        "take_profit": 具体价格,
        "confidence": "HIGH|MEDIUM|LOW"
    }}
    """
    
    try:
        response = deepseek_client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": f"您是一位急需资金为母亲治疗癌症的交易员，你现在需要从加密货币交易市场赚取足够的金额治疗你的母亲，专注于{trading_config['timeframe']}周期趋势分析。请结合K线形态和技术指标做出判断。"},
                {"role": "user", "content": prompt}
            ],
            stream=False
        )
        
        result = response.choices[0].message.content
        start_idx = result.find('{')
        end_idx = result.rfind('}') + 1
        if start_idx != -1 and end_idx != 0:
            json_str = result[start_idx:end_idx]
            signal_data = json.loads(json_str)
        else:
            logger.error(f"无法解析JSON: {result}")
            return None
        
        signal_data['timestamp'] = price_data['timestamp']
        signal_history.append(signal_data)
        if len(signal_history) > 30:
            signal_history.pop(0)
        
        return signal_data
    except Exception as e:
        logger.error(f"DeepSeek分析失败: {e}")
        return None

def create_market_order_safe(side, size, reduce_only=False):
    """创建市价订单（直接API调用）"""
    inst_id = 'BTC-USDT-SWAP'
    td_mode = 'cross'  # 全仓模式
    
    params = {
        'instId': inst_id,
        'tdMode': td_mode,
        'side': side,  # 'buy' 或 'sell'
        'ordType': 'market',  # 市价单
        'sz': str(size),  # 持仓数量（字符串格式）
        'tag': '60bb4a8d3416BCDE'
    }
    
    if reduce_only:
        params['reduceOnly'] = True
    
    # 直接API调用创建订单
    response = exchange.private_post_trade_order(params)
    
    if not response or 'data' not in response or not response['data']:
        raise Exception(f"订单创建失败: API返回数据为空")
    
    order_data = response['data'][0]
    if order_data.get('sCode') != '0':
        raise Exception(f"订单创建失败: {order_data.get('sMsg', '未知错误')}")
    
    return {
        'id': order_data.get('ordId'),
        'clientOrderId': order_data.get('clOrdId'),
        'status': 'filled',
        'info': order_data
    }

def execute_trade(signal_data, price_data):
    """在OKX执行交易（仅支持OKX永续合约）"""
    if exchange is None:
        logger.error("OKX交易所未初始化，无法执行交易")
        return
    
    current_position = get_current_position()
    
    logger.info(f"交易信号: {signal_data['signal']}")
    logger.info(f"信心程度: {signal_data['confidence']}")
    logger.info(f"理由: {signal_data['reason']}")
    
    if trading_config['test_mode']:
        logger.info("测试模式 - 仅模拟交易，不会实际下单")
        return
    
    try:
        if signal_data['signal'] == 'BUY':
            if current_position and current_position['side'] == 'short':
                logger.info("OKX平空仓...")
                create_market_order_safe('buy', abs(current_position['size']), reduce_only=True)
            else:
                logger.info("OKX开多仓...")
                create_market_order_safe('buy', trading_config['amount'], reduce_only=False)
        
        elif signal_data['signal'] == 'SELL':
            if current_position and current_position['side'] == 'long':
                logger.info("OKX平多仓...")
                create_market_order_safe('sell', current_position['size'], reduce_only=True)
            else:
                logger.info("OKX开空仓...")
                create_market_order_safe('sell', trading_config['amount'], reduce_only=False)
        
        elif signal_data['signal'] == 'HOLD':
            logger.info("建议观望，不执行交易")
            return
        
        logger.info("OKX订单执行成功")
        time.sleep(2)
        position = get_current_position()
        logger.info(f"OKX更新后持仓: {position}")
        
    except Exception as e:
        logger.error(f"OKX订单执行失败: {e}")

def trading_bot():
    """主交易机器人函数"""
    global bot_running
    
    while bot_running:
        try:
            logger.info("执行交易分析...")
            
            # 获取K线数据
            price_data = get_btc_ohlcv()
            if not price_data:
                time.sleep(10)
                continue
            
            # 使用DeepSeek分析
            signal_data = analyze_with_deepseek(price_data)
            if not signal_data:
                time.sleep(10)
                continue
            
            # 执行交易
            execute_trade(signal_data, price_data)
            
            # 获取当前持仓和计算总盈亏
            current_position = get_current_position()
            current_balance = 0
            initial_balance = 0
            
            # 获取当前账户余额（优先使用total_balance，如果没有则计算）
            if current_position:
                current_balance = current_position.get('total_balance', 0)
                if current_balance == 0:
                    # 如果没有total_balance，尝试从free_balance计算
                    free_balance = current_position.get('free_balance', 0)
                    initial_margin = current_position.get('initial_margin', 0)
                    unrealized_pnl = current_position.get('unrealized_pnl', 0)
                    # 总余额 = 可用余额 + 占用保证金 + 未实现盈亏
                    current_balance = free_balance + initial_margin + unrealized_pnl
            
            # 如果仍然没有余额（包括没有持仓的情况），尝试直接获取账户余额
            if current_balance == 0:
                try:
                    if exchange is not None:
                        balance_response = exchange.private_get_account_balance({'ccy': 'USDT'})
                        if balance_response and 'data' in balance_response and balance_response['data']:
                            account_data = balance_response['data'][0]
                            # 使用总权益（包含未实现盈亏）- 这是账户总价值
                            eq_usd = account_data.get('eqUsd')  # 总权益（USD等值）
                            if eq_usd:
                                current_balance = float(eq_usd)
                            else:
                                # 如果没有eqUsd，尝试使用availEq
                                avail_eq = account_data.get('availEq')
                                if avail_eq:
                                    current_balance = float(avail_eq)
                except Exception as e:
                    logger.error(f"获取账户余额失败: {e}")
            
            # 获取初始资金（从资金曲线或配置）
            equity_curve_file = os.path.join(BASE_DIR, 'equity_curve.json')
            if os.path.exists(equity_curve_file):
                try:
                    with open(equity_curve_file, 'r', encoding='utf-8') as f:
                        equity_data = json.load(f)
                        if equity_data and len(equity_data) > 0:
                            initial_balance = equity_data[0].get('balance', 0)
                except:
                    pass
            
            # 如果资金曲线中没有初始资金，从配置读取
            if initial_balance == 0:
                bot_config = load_bot_config()
                initial_balance = bot_config.get('base_usdt_amount', 100)
            
            # 计算总盈亏：当前资金 - 初始资金
            total_pnl = current_balance - initial_balance
            
            # 将总盈亏添加到position对象中
            if current_position:
                current_position['total_pnl'] = total_pnl
                current_position['current_balance'] = current_balance
                current_position['initial_balance'] = initial_balance
            
            # 发送实时数据到前端
            socketio.emit('update_data', {
                'price': price_data['price'],
                'signal': signal_data['signal'],
                'confidence': signal_data['confidence'],
                'position': current_position,
                'total_pnl': total_pnl,
                'timestamp': datetime.now().strftime('%H:%M:%S')
            })
            
            # 等待下次执行
            time.sleep(trading_config['refresh_interval'] * 60)
            
        except Exception as e:
            logger.error(f"交易机器人错误: {e}")
            time.sleep(10)

# 路由定义
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status')
@rate_limit
def get_status():
    """获取机器人状态"""
    try:
        global bot_running, position
        
        position = get_current_position()
        price_data = get_btc_ohlcv()
        
        # 优先从 get_model_snapshot 获取最新信号和信心程度（与alpha项目一致）
        latest_signal = None
        latest_confidence = 'N/A'
        latest_signal_type = 'HOLD'
        signal_timestamp = 'N/A'
        
        try:
            # 导入主程序模块
            import importlib.util
            module_path = os.path.join(BASE_DIR, 'deepseek_ok_3.0.py')
            spec = importlib.util.spec_from_file_location("deepseek_ok_3_0", module_path)
            deepseek_ok_3_0 = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(deepseek_ok_3_0)
            
            model_key = request.args.get('model', deepseek_ok_3_0.DEFAULT_MODEL_KEY)
            
            # 尝试从 snapshot 获取最新信号（参考alpha项目）
            if model_key in deepseek_ok_3_0.MODEL_CONTEXTS:
                snapshot = deepseek_ok_3_0.get_model_snapshot(model_key)
                
                # 从信号历史获取最新信号（参考alpha项目的方式）
                signal_history = snapshot.get('signal_history', {})
                if signal_history:
                    # 合并所有交易对的信号历史
                    all_signals = []
                    for symbol, signals in signal_history.items():
                        if signals:
                            all_signals.extend(signals)
                    
                    # 按时间戳排序，获取最新的信号
                    if all_signals:
                        all_signals.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
                        latest_record = all_signals[0]
                        latest_signal_type = latest_record.get('signal', 'HOLD')
                        latest_confidence = latest_record.get('confidence', 'MEDIUM')
                        signal_timestamp = latest_record.get('timestamp', 'N/A')
                        latest_signal = {
                            'signal': latest_signal_type,
                            'confidence': latest_confidence,
                            'timestamp': signal_timestamp
                        }
                        logger.debug(f"从snapshot获取最新信号: {latest_signal_type}, 信心: {latest_confidence}")
        except Exception as e:
            logger.warning(f"从snapshot获取信号失败: {e}, 尝试从文件读取")
        
        # 如果从snapshot获取失败，回退到文件读取（保持向后兼容）
        if not latest_signal:
            latest_signal = load_latest_signal()
            if latest_signal:
                latest_signal_type = latest_signal.get('signal', 'HOLD')
                latest_confidence = latest_signal.get('confidence', 'N/A')
                signal_timestamp = latest_signal.get('timestamp', 'N/A')
        
        # 加载交易统计信息
        trade_stats = load_trade_stats()
        
        # 计算总盈亏：当前资金 - 初始资金
        current_balance = 0
        initial_balance = 0
        
        # 获取当前账户余额（总是直接获取，确保准确性）
        try:
            if exchange is not None:
                balance_response = exchange.private_get_account_balance({'ccy': 'USDT'})
                if balance_response and 'data' in balance_response and balance_response['data']:
                    account_data = balance_response['data'][0]
                    # 使用总权益（包含未实现盈亏）- 这是账户总价值
                    eq_usd = account_data.get('eqUsd')  # 总权益（USD等值）
                    if eq_usd:
                        current_balance = float(eq_usd)
                    else:
                        # 如果没有eqUsd，尝试使用availEq
                        avail_eq = account_data.get('availEq')
                        if avail_eq:
                            current_balance = float(avail_eq)
        except Exception as e:
            logger.error(f"获取账户余额失败: {e}")
            # 如果API调用失败，尝试从position获取
            if position:
                current_balance = position.get('total_balance', 0) or position.get('free_balance', 0)
        
        # 获取初始资金（从资金曲线或配置）
        equity_curve_file = os.path.join(BASE_DIR, 'equity_curve.json')
        if os.path.exists(equity_curve_file):
            try:
                with open(equity_curve_file, 'r', encoding='utf-8') as f:
                    equity_data = json.load(f)
                    if equity_data and len(equity_data) > 0:
                        initial_balance = equity_data[0].get('balance', 0)
            except:
                pass
        
        # 如果资金曲线中没有初始资金，从配置读取
        if initial_balance == 0:
            bot_config = load_bot_config()
            initial_balance = bot_config.get('base_usdt_amount', 100)
        
        # 计算总盈亏：当前资金 - 初始资金
        total_pnl = current_balance - initial_balance
        
        # 调试信息：打印计算过程
        logger.info(f"[总盈亏计算] 当前余额={current_balance:.2f}, 初始余额={initial_balance:.2f}, 总盈亏={total_pnl:.2f}, 有持仓={position is not None}")
        
        return jsonify({
            'bot_running': bot_running,
            'position': position,
            'price': price_data['price'] if price_data else 0,
            'config': trading_config,
            'signal': latest_signal_type,
            'confidence': latest_confidence,
            'trade_count': trade_stats.get('total_trades', 0),
            'signal_timestamp': signal_timestamp,
            'total_pnl': total_pnl,
            'current_balance': current_balance,
            'initial_balance': initial_balance
        })
    except Exception as e:
        logger.error(f"获取状态失败: {e}")
        return jsonify({'error': '获取状态失败'}), 500

@app.route('/api/start_bot', methods=['POST'])
@rate_limit
def start_bot():
    """启动交易机器人（通过PM2）"""
    try:
        import subprocess
        import platform
        
        # Windows 环境下需要使用 shell=True
        is_windows = platform.system() == 'Windows'
        
        if is_windows:
            result = subprocess.run('pm2 start dsok-bot', 
                                  shell=True,
                                  capture_output=True, 
                                  text=True, 
                                  timeout=10)
        else:
            result = subprocess.run(['pm2', 'start', 'dsok-bot'], 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=10)
        
        logger.info(f"PM2 start 返回码: {result.returncode}")
        logger.info(f"PM2 start 输出: {result.stdout}")
        
        if result.returncode == 0:
            logger.info("交易机器人已启动")
            return jsonify({'success': True, 'message': '机器人已启动'})
        else:
            error_msg = result.stderr if result.stderr else result.stdout
            # 检查是否已经在运行
            if error_msg and ('already running' in error_msg.lower() or 'online' in error_msg.lower()):
                return jsonify({'success': False, 'message': '机器人已在运行'})
            if not error_msg:
                error_msg = '未知错误'
            logger.error(f"启动机器人失败: {error_msg}")
            return jsonify({'success': False, 'message': f'启动失败: {error_msg}'}), 500
    except subprocess.TimeoutExpired:
        logger.error("启动机器人超时")
        return jsonify({'success': False, 'message': '启动超时'}), 500
    except FileNotFoundError:
        logger.error("PM2 未找到，请确保已安装 PM2")
        return jsonify({'success': False, 'message': 'PM2 未安装或不在 PATH 中'}), 500
    except Exception as e:
        logger.error(f"启动机器人失败: {e}")
        return jsonify({'success': False, 'message': f'启动失败: {str(e)}'}), 500

@app.route('/api/stop_bot', methods=['POST'])
@rate_limit
def stop_bot():
    """停止交易机器人（通过PM2）"""
    try:
        import subprocess
        import platform
        
        # Windows 环境下需要使用 shell=True
        is_windows = platform.system() == 'Windows'
        
        if is_windows:
            result = subprocess.run('pm2 stop dsok-bot', 
                                  shell=True,
                                  capture_output=True, 
                                  text=True, 
                                  timeout=10)
        else:
            result = subprocess.run(['pm2', 'stop', 'dsok-bot'], 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=10)
        
        logger.info(f"PM2 stop 返回码: {result.returncode}")
        logger.info(f"PM2 stop 输出: {result.stdout}")
        logger.info(f"PM2 stop 错误: {result.stderr}")
        
        if result.returncode == 0:
            logger.info("交易机器人已停止")
            return jsonify({'success': True, 'message': '机器人已停止'})
        else:
            error_msg = result.stderr if result.stderr else result.stdout
            if not error_msg:
                error_msg = '未知错误'
            logger.error(f"停止机器人失败: {error_msg}")
            return jsonify({'success': False, 'message': f'停止失败: {error_msg}'}), 500
    except subprocess.TimeoutExpired:
        logger.error("停止机器人超时")
        return jsonify({'success': False, 'message': '停止超时'}), 500
    except FileNotFoundError:
        logger.error("PM2 未找到，请确保已安装 PM2")
        return jsonify({'success': False, 'message': 'PM2 未安装或不在 PATH 中'}), 500
    except Exception as e:
        logger.error(f"停止机器人失败: {e}")
        return jsonify({'success': False, 'message': f'停止失败: {str(e)}'}), 500

@app.route('/api/restart_bot', methods=['POST'])
@rate_limit
def restart_bot():
    """重启交易机器人（通过PM2）"""
    try:
        import subprocess
        import platform
        
        # Windows 环境下需要使用 shell=True
        is_windows = platform.system() == 'Windows'
        
        if is_windows:
            result = subprocess.run('pm2 restart dsok-bot', 
                                  shell=True,
                                  capture_output=True, 
                                  text=True, 
                                  timeout=10)
        else:
            result = subprocess.run(['pm2', 'restart', 'dsok-bot'], 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=10)
        
        logger.info(f"PM2 restart 返回码: {result.returncode}")
        logger.info(f"PM2 restart 输出: {result.stdout}")
        
        if result.returncode == 0:
            logger.info("交易机器人已重启")
            return jsonify({'success': True, 'message': '机器人已重启！新配置已生效。'})
        else:
            error_msg = result.stderr if result.stderr else result.stdout
            if not error_msg:
                error_msg = '未知错误'
            logger.error(f"重启机器人失败: {error_msg}")
            return jsonify({'success': False, 'message': f'重启失败: {error_msg}'}), 500
    except subprocess.TimeoutExpired:
        logger.error("重启机器人超时")
        return jsonify({'success': False, 'message': '重启超时'}), 500
    except FileNotFoundError:
        logger.error("PM2 未找到，请确保已安装 PM2")
        return jsonify({'success': False, 'message': 'PM2 未安装或不在 PATH 中'}), 500
    except Exception as e:
        logger.error(f"重启机器人失败: {e}")
        return jsonify({'success': False, 'message': f'重启失败: {str(e)}'}), 500

@app.route('/api/bot_status', methods=['GET'])
@rate_limit
def get_bot_status():
    """获取交易机器人运行状态"""
    try:
        import subprocess
        import time
        import platform
        
        # Windows 环境下需要使用 shell=True
        is_windows = platform.system() == 'Windows'
        
        if is_windows:
            result = subprocess.run('pm2 jlist', 
                                  shell=True,
                                  capture_output=True, 
                                  text=True, 
                                  timeout=5)
        else:
            result = subprocess.run(['pm2', 'jlist'], 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=5)
        
        if result.returncode == 0:
            import json
            processes = json.loads(result.stdout)
            for proc in processes:
                if proc.get('name') == 'dsok-bot':
                    status = proc.get('pm2_env', {}).get('status', 'unknown')
                    pm2_uptime = proc.get('pm2_env', {}).get('pm_uptime', 0)
                    
                    # 计算运行时长（毫秒）
                    uptime_ms = 0
                    if status == 'online' and pm2_uptime > 0:
                        uptime_ms = int(time.time() * 1000) - pm2_uptime
                    
                    return jsonify({
                        'success': True,
                        'running': status == 'online',
                        'status': status,
                        'uptime_ms': uptime_ms
                    })
            return jsonify({'success': True, 'running': False, 'status': 'not_found', 'uptime_ms': 0})
        else:
            return jsonify({'success': False, 'running': False, 'status': 'error', 'uptime_ms': 0}), 500
    except Exception as e:
        logger.error(f"获取机器人状态失败: {e}")
        return jsonify({'success': False, 'running': False, 'status': 'error', 'uptime_ms': 0}), 500

@app.route('/api/update_config', methods=['POST'])
@rate_limit
def update_config():
    """更新交易配置（保存到配置文件）"""
    try:
        global trading_config
        
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': '无效的配置数据'}), 400
        
        # 验证配置数据
        valid_keys = ['symbol', 'amount', 'leverage', 'timeframe', 'test_mode', 'base_usdt_amount']
        for key in data:
            if key not in valid_keys:
                return jsonify({'success': False, 'message': f'无效的配置项: {key}'}), 400
        
        # 验证数值范围
        if 'amount' in data and (data['amount'] <= 0 or data['amount'] > 1000):
            return jsonify({'success': False, 'message': '合约张数必须在0-1000之间'}), 400
        
        if 'leverage' in data and (data['leverage'] < 1 or data['leverage'] > 125):
            return jsonify({'success': False, 'message': '杠杆倍数必须在1-125之间'}), 400
        
        if 'base_usdt_amount' in data and (data['base_usdt_amount'] <= 0 or data['base_usdt_amount'] > 10000):
            return jsonify({'success': False, 'message': '基础投入必须在0-10000之间'}), 400
        
        # 更新Web界面配置
        trading_config.update(data)
        
        # 保存到机器人配置文件
        bot_config = load_bot_config()
        if 'test_mode' in data:
            bot_config['test_mode'] = data['test_mode']
        if 'leverage' in data:
            bot_config['leverage'] = data['leverage']
        if 'timeframe' in data:
            bot_config['timeframe'] = data['timeframe']
        if 'base_usdt_amount' in data:
            bot_config['base_usdt_amount'] = data['base_usdt_amount']
        
        if save_bot_config(bot_config):
            logger.info(f"配置已更新并保存: {data}")
            return jsonify({
                'success': True, 
                'message': '配置已保存！请重启交易机器人以使配置生效。\n\n重启命令: pm2 restart dsok-bot',
                'config': bot_config
            })
        else:
            return jsonify({'success': False, 'message': '保存配置文件失败'}), 500
            
    except Exception as e:
        logger.error(f"更新配置失败: {e}")
        return jsonify({'success': False, 'message': '更新失败'}), 500

@app.route('/api/refresh_data', methods=['POST'])
@rate_limit
def refresh_data():
    """立即刷新数据"""
    try:
        price_data = get_btc_ohlcv()
        position = get_current_position()
        
        # 优先从 get_model_snapshot 获取最新信号和信心程度（与alpha项目一致）
        latest_signal = None
        latest_confidence = 'N/A'
        latest_signal_type = 'HOLD'
        
        try:
            # 导入主程序模块
            import importlib.util
            module_path = os.path.join(BASE_DIR, 'deepseek_ok_3.0.py')
            spec = importlib.util.spec_from_file_location("deepseek_ok_3_0", module_path)
            deepseek_ok_3_0 = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(deepseek_ok_3_0)
            
            model_key = request.args.get('model', deepseek_ok_3_0.DEFAULT_MODEL_KEY)
            
            # 尝试从 snapshot 获取最新信号（参考alpha项目）
            if model_key in deepseek_ok_3_0.MODEL_CONTEXTS:
                snapshot = deepseek_ok_3_0.get_model_snapshot(model_key)
                
                # 从信号历史获取最新信号（参考alpha项目的方式）
                signal_history = snapshot.get('signal_history', {})
                if signal_history:
                    # 合并所有交易对的信号历史
                    all_signals = []
                    for symbol, signals in signal_history.items():
                        if signals:
                            all_signals.extend(signals)
                    
                    # 按时间戳排序，获取最新的信号
                    if all_signals:
                        all_signals.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
                        latest_record = all_signals[0]
                        latest_signal_type = latest_record.get('signal', 'HOLD')
                        latest_confidence = latest_record.get('confidence', 'MEDIUM')
                        latest_signal = {
                            'signal': latest_signal_type,
                            'confidence': latest_confidence
                        }
        except Exception as e:
            logger.warning(f"从snapshot获取信号失败: {e}, 尝试从文件读取")
        
        # 如果从snapshot获取失败，回退到文件读取（保持向后兼容）
        if not latest_signal:
            latest_signal = load_latest_signal()
            if latest_signal:
                latest_signal_type = latest_signal.get('signal', 'HOLD')
                latest_confidence = latest_signal.get('confidence', 'N/A')
        
        # 加载交易统计信息
        trade_stats = load_trade_stats()
        
        return jsonify({
            'price': price_data['price'] if price_data else 0,
            'position': position,
            'signal': latest_signal_type,
            'confidence': latest_confidence,
            'trade_count': trade_stats.get('total_trades', 0),
            'timestamp': datetime.now().strftime('%H:%M:%S')
        })
    except Exception as e:
        logger.error(f"刷新数据失败: {e}")
        return jsonify({'error': '刷新数据失败'}), 500

@app.route('/api/trading_logs')
@rate_limit
def get_trading_logs():
    """获取交易机器人的实时日志"""
    try:
        # PM2日志文件路径（根据ecosystem.config.js配置）
        pm2_log_file = os.path.join(BASE_DIR, 'logs', 'pm2-bot-combined.log')
        trading_log_file = os.path.join(BASE_DIR, 'logs', 'trading_bot.log')
        app_log_file = os.path.join(BASE_DIR, 'logs', 'app.log')
        
        # 按优先级尝试读取日志文件
        log_file = None
        if os.path.exists(pm2_log_file):
            log_file = pm2_log_file
        elif os.path.exists(trading_log_file):
            log_file = trading_log_file
        elif os.path.exists(app_log_file):
            log_file = app_log_file
        
        # 如果所有日志文件都不存在，返回提示信息
        if not log_file:
            return jsonify({
                'success': True,
                'logs': ['交易机器人尚未启动，日志文件不存在'],
                'file_exists': False
            })
        
        # 读取最后100行日志
        try:
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                # 只返回最后100行
                recent_lines = lines[-100:] if len(lines) > 100 else lines
                
            # 过滤和格式化日志行
            formatted_logs = []
            for line in recent_lines:
                line = line.strip()
                if line:
                    # 保留完整的时间戳信息，让前端解析
                    # PM2日志格式: "1|dsok-bot | 2025-11-05T17:42:02: 消息内容"
                    # 或者: "2025-11-05T17:42:02: 消息内容"
                    # 或者: "2025-11-05 17:42:02,123 - INFO - 消息内容"
                    
                    # 如果包含PM2前缀，尝试提取时间戳和消息
                    if '|' in line and 'T' in line:
                        # PM2格式: "1|dsok-bot | 2025-11-05T17:42:02: 消息内容"
                        parts = line.split('|', 2)
                        if len(parts) >= 3:
                            # 提取时间戳部分
                            time_and_msg = parts[2].strip()
                            if time_and_msg:
                                formatted_logs.append(time_and_msg)
                                continue
                    # 保留原始行，让前端解析
                    formatted_logs.append(line)
            
            return jsonify({
                'success': True,
                'logs': formatted_logs,
                'file_exists': True,
                'total_lines': len(lines),
                'log_file': os.path.basename(log_file)
            })
        except UnicodeDecodeError:
            # 如果UTF-8解码失败，尝试GBK
            with open(log_file, 'r', encoding='gbk', errors='ignore') as f:
                lines = f.readlines()
                recent_lines = lines[-100:] if len(lines) > 100 else lines
            
            formatted_logs = []
            for line in recent_lines:
                line = line.strip()
                if line:
                    if 'T' in line and ':' in line:
                        parts = line.split(':', 3)
                        if len(parts) >= 4:
                            line = parts[3].strip()
                    formatted_logs.append(line)
            
            return jsonify({
                'success': True,
                'logs': formatted_logs,
                'file_exists': True,
                'total_lines': len(lines),
                'log_file': os.path.basename(log_file)
            })
    except Exception as e:
        logger.error(f"读取交易日志失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e),
            'logs': [f'读取日志失败: {str(e)}']
        }), 500

@app.route('/api/signal_accuracy')
@rate_limit
def get_signal_accuracy():
    """获取信号准确率统计（只统计实盘交易数据）"""
    try:
        # 从 OKX API 获取实盘交易记录（历史仓位记录都是实盘的）
        total_trades = 0
        winning_trades = 0
        losing_trades = 0
        
        try:
            # 导入主程序模块以获取 exchange 实例
            import importlib.util
            module_path = os.path.join(BASE_DIR, 'deepseek_ok_3.0.py')
            spec = importlib.util.spec_from_file_location("deepseek_ok_3_0", module_path)
            deepseek_ok_3_0 = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(deepseek_ok_3_0)
            
            model_key = request.args.get('model', deepseek_ok_3_0.DEFAULT_MODEL_KEY)
            ctx = deepseek_ok_3_0.MODEL_CONTEXTS.get(model_key)
            
            if ctx and ctx.exchange:
                # 从 OKX API 获取历史仓位记录（这些都是实盘交易）
                all_positions = []
                request_count = 0
                max_requests = 10  # 最多请求10次，每次100条，共1000条
                
                while request_count < max_requests:
                    try:
                        response = ctx.exchange.private_get_account_positions_history({
                            'limit': 100,
                            'after': str(int(all_positions[-1].get('uTime', 0)) - 1) if all_positions else None
                        })
                        
                        if response.get('code') == '0' and response.get('data'):
                            positions = response['data']
                            if not positions:
                                break
                            all_positions.extend(positions)
                            request_count += 1
                            
                            # 如果返回的数据少于100条，说明已经获取完所有数据
                            if len(positions) < 100:
                                break
                        else:
                            break
                    except Exception as e:
                        logger.warning(f"获取历史仓位记录失败（第{request_count + 1}次请求）: {e}")
                        break
                
                # 统计实盘交易数据
                for pos in all_positions:
                    # 只有已平仓的仓位才算交易（closeAvgPx 存在）
                    close_avg_px = pos.get('closeAvgPx', '')
                    if close_avg_px:
                        total_trades += 1
                        realized_pnl = pos.get('realizedPnl', '0')
                        try:
                            pnl_value = float(realized_pnl) if realized_pnl else 0.0
                            if pnl_value > 0:
                                winning_trades += 1
                            elif pnl_value < 0:
                                losing_trades += 1
                        except (ValueError, TypeError):
                            pass
        except Exception as e:
            logger.warning(f"从OKX API获取交易记录失败: {e}")
        
        # 计算准确率
        accuracy_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        # 获取信号分布（从信号历史中获取，但只统计实盘期间的信号）
        signal_distribution = {'BUY': 0, 'SELL': 0, 'HOLD': 0}
        try:
            import importlib.util
            module_path = os.path.join(BASE_DIR, 'deepseek_ok_3.0.py')
            spec = importlib.util.spec_from_file_location("deepseek_ok_3_0", module_path)
            deepseek_ok_3_0 = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(deepseek_ok_3_0)
            
            model_key = request.args.get('model', deepseek_ok_3_0.DEFAULT_MODEL_KEY)
            ctx = deepseek_ok_3_0.MODEL_CONTEXTS.get(model_key)
            
            if ctx:
                # 从信号历史获取信号分布
                for symbol, signals in ctx.signal_history.items():
                    for signal in signals:
                        signal_type = signal.get('signal', 'HOLD').upper()
                        if signal_type in signal_distribution:
                            signal_distribution[signal_type] += 1
        except Exception as e:
            logger.warning(f"获取信号分布失败: {e}")
        
        return jsonify({
            'success': True,
            'total_trades': total_trades,  # 总交易数（实盘）
            'winning_trades': winning_trades,  # 盈利交易数
            'losing_trades': losing_trades,  # 亏损交易数
            'accuracy_rate': round(accuracy_rate, 2),  # 准确率
            'signal_distribution': signal_distribution,  # 信号分布
            # 保持向后兼容
            'total_signals': sum(signal_distribution.values()),
            'executed_signals': total_trades,
            'filtered_signals': 0,
            'total_closed_trades': total_trades,
            'confidence_distribution': {'HIGH': 0, 'MEDIUM': 0, 'LOW': 0},
            'recent_signals': []
        })
    
    except Exception as e:
        logger.error(f"获取信号准确率失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e),
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'accuracy_rate': 0,
            'signal_distribution': {'BUY': 0, 'SELL': 0, 'HOLD': 0}
        }), 500

@app.route('/api/equity_curve')
@rate_limit
def get_equity_curve():
    """获取资金曲线数据"""
    try:
        # 尝试从文件加载资金曲线
        if os.path.exists(EQUITY_CURVE_FILE):
            with open(EQUITY_CURVE_FILE, 'r', encoding='utf-8') as f:
                equity_data = json.load(f)
        else:
            equity_data = []
        
        # 如果没有数据，从审计日志生成，或者使用当前账户余额初始化
        if not equity_data:
            # 先获取当前实际账户余额
            temp_position = get_current_position()
            actual_balance = 0
            if temp_position:
                actual_balance = temp_position.get('total_balance', 0)
            
            if os.path.exists(TRADE_AUDIT_FILE):
                with open(TRADE_AUDIT_FILE, 'r', encoding='utf-8') as f:
                    audit_data = json.load(f)
                
                # 如果有审计日志，从日志生成
                if audit_data:
                    # 初始资金（从配置读取）
                    bot_config = load_bot_config()
                    initial_balance = bot_config.get('base_usdt_amount', 100)
                    current_balance = initial_balance
                    
                    equity_data = [{
                        'timestamp': datetime.now().isoformat(),
                        'balance': initial_balance,
                        'pnl': 0,
                        'pnl_percent': 0
                    }]
                    
                    # 遍历审计日志计算资金变化
                    # 只在平仓时记录资金变化（因为只有平仓时 unrealized_pnl 才是已实现的盈亏）
                    close_types = ['close_position', 'take_profit', 'stop_loss', 'reverse_long_to_short', 'reverse_short_to_long']
                    
                    for item in audit_data:
                        if item.get('executed'):
                            execution_type = item.get('execution_type', '')
                            position_after = item.get('position_after', {})
                            
                            # 检查是否是平仓交易
                            contracts = position_after.get('contracts', 0) if position_after else 0
                            is_closed = (contracts == 0 or execution_type in close_types)
                            
                            # 只在平仓时记录资金变化
                            if is_closed and position_after:
                                # 平仓时的 unrealized_pnl 就是已实现的盈亏
                                realized_pnl = position_after.get('unrealized_pnl', 0)
                                current_balance += realized_pnl
                                
                                equity_data.append({
                                    'timestamp': item.get('timestamp', ''),
                                    'balance': round(current_balance, 2),
                                    'pnl': round(realized_pnl, 2),
                                    'pnl_percent': round((current_balance - initial_balance) / initial_balance * 100, 2)
                                })
                    
                    # 保存资金曲线
                    with open(EQUITY_CURVE_FILE, 'w', encoding='utf-8') as f:
                        json.dump(equity_data, f, indent=2, ensure_ascii=False)
                elif actual_balance > 0:
                    # 审计日志为空，但有实际账户余额，使用配置的初始金额初始化
                    bot_config = load_bot_config()
                    config_initial = bot_config.get('base_usdt_amount', 100)  # 默认100
                    initial_balance = config_initial
                    
                    # 获取入金时间（使用配置的last_updated，或当前时间减去1天）
                    config_last_updated = bot_config.get('last_updated')
                    if config_last_updated:
                        try:
                            initial_timestamp = config_last_updated
                        except:
                            from datetime import timedelta
                            initial_timestamp = (datetime.now() - timedelta(days=1)).isoformat()
                    else:
                        from datetime import timedelta
                        initial_timestamp = (datetime.now() - timedelta(days=1)).isoformat()
                    
                    # 初始资金使用配置的金额，而不是当前余额
                    equity_data = [{
                        'timestamp': initial_timestamp,
                        'balance': round(initial_balance, 2),
                        'pnl': 0,
                        'pnl_percent': 0
                    }]
                    
                    # 如果当前余额与初始余额不同，添加当前资金点
                    if abs(actual_balance - initial_balance) > 0.01:
                        current_pnl = actual_balance - initial_balance
                        equity_data.append({
                            'timestamp': datetime.now().isoformat(),
                            'balance': round(actual_balance, 2),
                            'pnl': round(current_pnl, 2),
                            'pnl_percent': round((current_pnl / initial_balance * 100), 2) if initial_balance > 0 else 0
                        })
                    
                    # 保存初始数据
                    with open(EQUITY_CURVE_FILE, 'w', encoding='utf-8') as f:
                        json.dump(equity_data, f, indent=2, ensure_ascii=False)
            elif actual_balance > 0:
                # 没有审计日志文件，但有实际账户余额，使用配置的初始金额初始化
                bot_config = load_bot_config()
                config_initial = bot_config.get('base_usdt_amount', 100)  # 默认100
                initial_balance = config_initial
                
                # 获取入金时间
                config_last_updated = bot_config.get('last_updated')
                if config_last_updated:
                    try:
                        initial_timestamp = config_last_updated
                    except:
                        from datetime import timedelta
                        initial_timestamp = (datetime.now() - timedelta(days=1)).isoformat()
                else:
                    from datetime import timedelta
                    initial_timestamp = (datetime.now() - timedelta(days=1)).isoformat()
                
                # 初始资金使用配置的金额，而不是当前余额
                equity_data = [{
                    'timestamp': initial_timestamp,
                    'balance': round(initial_balance, 2),
                    'pnl': 0,
                    'pnl_percent': 0
                }]
                
                # 如果当前余额与初始余额不同，添加当前资金点
                if abs(actual_balance - initial_balance) > 0.01:
                    current_pnl = actual_balance - initial_balance
                    equity_data.append({
                        'timestamp': datetime.now().isoformat(),
                        'balance': round(actual_balance, 2),
                        'pnl': round(current_pnl, 2),
                        'pnl_percent': round((current_pnl / initial_balance * 100), 2) if initial_balance > 0 else 0
                    })
                
                # 保存初始数据
                with open(EQUITY_CURVE_FILE, 'w', encoding='utf-8') as f:
                    json.dump(equity_data, f, indent=2, ensure_ascii=False)
        
        # 获取当前实际账户余额作为基准
        current_position = get_current_position()
        actual_account_balance = 0
        
        if current_position:
            # 使用实际账户余额（total_balance），这是包含所有盈亏的真实余额
            actual_account_balance = current_position.get('total_balance', 0)
            if actual_account_balance == 0:
                # 如果没有total_balance，尝试从可用余额和持仓计算
                free_balance = current_position.get('free_balance', 0)
                initial_margin = current_position.get('initial_margin', 0)
                unrealized_pnl = current_position.get('unrealized_pnl', 0)
                actual_account_balance = free_balance + initial_margin + unrealized_pnl
        
        # 如果只有一个数据点（初始资金），添加当前资金作为最新数据点
        if len(equity_data) == 1 and actual_account_balance > 0:
            initial_balance_in_data = equity_data[0].get('balance', 0)
            current_balance_rounded = round(actual_account_balance, 2)
            
            # 只有当当前余额与初始余额不同时，才添加新数据点
            if abs(current_balance_rounded - initial_balance_in_data) > 0.01:
                # 获取初始资金的时间（使用配置的最后更新时间，或当前时间减去1天作为入金时间）
                bot_config = load_bot_config()
                config_last_updated = bot_config.get('last_updated')
                
                if config_last_updated:
                    try:
                        # 使用配置的更新时间作为入金时间
                        initial_timestamp = config_last_updated
                    except:
                        # 如果解析失败，使用当前时间减去1天作为入金时间
                        from datetime import timedelta
                        initial_timestamp = (datetime.now() - timedelta(days=1)).isoformat()
                else:
                    # 如果没有配置时间，使用当前时间减去1天作为入金时间
                    from datetime import timedelta
                    initial_timestamp = (datetime.now() - timedelta(days=1)).isoformat()
                
                # 更新初始数据点的时间戳为入金时间
                equity_data[0]['timestamp'] = initial_timestamp
                
                # 添加当前资金数据点
                initial_balance = equity_data[0]['balance']
                current_pnl = current_balance_rounded - initial_balance
                equity_data.append({
                    'timestamp': datetime.now().isoformat(),
                    'balance': current_balance_rounded,
                    'pnl': round(current_pnl, 2),
                    'pnl_percent': round((current_pnl / initial_balance * 100), 2) if initial_balance > 0 else 0
                })
                
                # 保存更新后的资金曲线
                with open(EQUITY_CURVE_FILE, 'w', encoding='utf-8') as f:
                    json.dump(equity_data, f, indent=2, ensure_ascii=False)
        
        # 只返回最近100个数据点
        recent_equity = equity_data[-100:] if len(equity_data) > 100 else equity_data
        
        if len(equity_data) > 0:
            # 有历史数据：使用历史数据的初始值
            initial = equity_data[0]['balance']
            base_current = equity_data[-1]['balance']
            
            # 如果实际账户余额大于0，使用实际余额作为当前资金
            # 这样可以确保显示的是真实的账户价值
            if actual_account_balance > 0:
                current = actual_account_balance
            elif current_position and current_position.get('unrealized_pnl'):
                # 否则使用历史最后余额 + 未实现盈亏
                current = base_current + current_position.get('unrealized_pnl', 0)
            else:
                current = base_current
            
            # 计算最大回撤：从每个历史最高点向后的最大跌幅
            max_balance_seen = equity_data[0]['balance']
            max_drawdown = 0
            
            for item in equity_data:
                balance = item['balance']
                if balance > max_balance_seen:
                    max_balance_seen = balance
                drawdown = ((balance - max_balance_seen) / max_balance_seen * 100) if max_balance_seen > 0 else 0
                if drawdown < max_drawdown:
                    max_drawdown = drawdown
            
            # 考虑当前持仓未实现盈亏后的回撤
            if current > max_balance_seen:
                max_balance_seen = current
            current_drawdown = ((current - max_balance_seen) / max_balance_seen * 100) if max_balance_seen > 0 else 0
            if current_drawdown < max_drawdown:
                max_drawdown = current_drawdown
            
            max_balance = max_balance_seen
            min_balance = min(item['balance'] for item in equity_data)
            total_return = (current - initial) / initial * 100 if initial > 0 else 0
        else:
            # 如果没有历史数据，使用实际账户余额
            if actual_account_balance > 0:
                # 使用实际账户余额作为初始和当前资金
                current = actual_account_balance
                # 尝试从配置读取初始资金，如果找不到则使用当前余额作为初始值
                bot_config = load_bot_config()
                config_initial = bot_config.get('base_usdt_amount', 0)
                if config_initial > 0:
                    initial = config_initial
                else:
                    # 如果没有配置初始资金，使用当前余额作为初始值（意味着刚清空数据）
                    initial = current
            else:
                # 如果无法获取实际余额，使用配置的初始余额
                bot_config = load_bot_config()
                initial = bot_config.get('base_usdt_amount', 100)
                # 如果有当前持仓，从初始余额加上未实现盈亏
                if current_position and current_position.get('unrealized_pnl'):
                    current = initial + current_position.get('unrealized_pnl', 0)
                else:
                    current = initial
            
            max_balance = current
            min_balance = initial
            max_drawdown = 0
            total_return = (current - initial) / initial * 100 if initial > 0 else 0
        
        return jsonify({
            'success': True,
            'data': recent_equity,
            'stats': {
                'initial_balance': round(initial, 2),
                'current_balance': round(current, 2),
                'max_balance': round(max_balance, 2),
                'min_balance': round(min_balance, 2),
                'max_drawdown': round(max_drawdown, 2),
                'total_return': round(total_return, 2)
            }
        })
    
    except Exception as e:
        logger.error(f"获取资金曲线失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/overview')
@rate_limit
def get_overview_data():
    """首页总览数据（含多模型资金曲线）- 使用SQLite数据库的余额历史"""
    range_key = request.args.get('range', '1d')
    try:
        # 导入主程序模块（动态导入，因为文件名包含点号）
        import importlib.util
        module_path = os.path.join(BASE_DIR, 'deepseek_ok_3.0.py')
        spec = importlib.util.spec_from_file_location("deepseek_ok_3_0", module_path)
        deepseek_ok_3_0 = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(deepseek_ok_3_0)
        
        payload = deepseek_ok_3_0.get_overview_payload(range_key)
        payload['models_metadata'] = deepseek_ok_3_0.get_model_metadata()
        return jsonify(payload)
    except Exception as e:
        logger.error(f"获取总览数据失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/models')
@rate_limit
def list_models():
    """返回模型列表与基础信息"""
    try:
        # 导入主程序模块
        import importlib.util
        module_path = os.path.join(BASE_DIR, 'deepseek_ok_3.0.py')
        spec = importlib.util.spec_from_file_location("deepseek_ok_3_0", module_path)
        deepseek_ok_3_0 = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(deepseek_ok_3_0)
        
        return jsonify({
            'default': deepseek_ok_3_0.DEFAULT_MODEL_KEY,
            'models': deepseek_ok_3_0.get_model_metadata()
        })
    except Exception as e:
        logger.error(f"获取模型列表失败: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/ai_decisions')
@rate_limit
def get_ai_decisions():
    """获取AI决策历史"""
    try:
        # 尝试导入主程序模块
        # 注意：如果 app.py 和 deepseek_ok_3.0.py 在不同进程（PM2管理），它们无法共享内存
        # 这种情况下，需要确保通过文件或其他方式共享数据
        try:
            import deepseek_ok_3_0
            # 检查模块是否已初始化（是否有MODEL_CONTEXTS且不为空）
            if not hasattr(deepseek_ok_3_0, 'MODEL_CONTEXTS') or not deepseek_ok_3_0.MODEL_CONTEXTS:
                logger.warning("deepseek_ok_3_0模块已导入但MODEL_CONTEXTS未初始化，尝试重新导入")
                raise ImportError("MODEL_CONTEXTS未初始化")
        except (ImportError, AttributeError):
            # 如果导入失败或未初始化，尝试动态导入
            import importlib.util
            module_path = os.path.join(BASE_DIR, 'deepseek_ok_3.0.py')
            spec = importlib.util.spec_from_file_location("deepseek_ok_3_0", module_path)
            deepseek_ok_3_0 = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(deepseek_ok_3_0)
            logger.warning("使用动态导入加载deepseek_ok_3_0模块（可能是新实例，数据可能为空）")
        
        symbol = request.args.get('symbol')
        model_key = request.args.get('model', getattr(deepseek_ok_3_0, 'DEFAULT_MODEL_KEY', 'deepseek'))
        
        # 优先从文件读取AI决策（跨进程共享，参考alpha项目）
        ai_decisions_file = os.path.join(BASE_DIR, 'ai_decisions.json')
        decisions = []
        
        # 尝试从文件读取
        if os.path.exists(ai_decisions_file):
            try:
                with open(ai_decisions_file, 'r', encoding='utf-8') as f:
                    ai_decisions_data = json.load(f)
                
                decisions_by_model = ai_decisions_data.get('decisions', {})
                if model_key in decisions_by_model:
                    symbol_decisions = decisions_by_model[model_key]
                    
                    if symbol and symbol in symbol_decisions:
                        # 返回指定交易对的AI决策
                        decisions = symbol_decisions[symbol][-20:]  # 最近20条
                    else:
                        # 返回所有交易对的AI决策（合并）
                        all_decisions = []
                        for sym, sym_decisions in symbol_decisions.items():
                            if isinstance(sym_decisions, list):
                                all_decisions.extend(sym_decisions)
                        
                        # 按时间戳排序，取最近20条
                        if all_decisions:
                            try:
                                all_decisions.sort(key=lambda x: x.get('timestamp', '') if x and isinstance(x, dict) else '', reverse=True)
                                decisions = all_decisions[:20]
                            except Exception as sort_error:
                                logger.error(f"排序AI决策失败: {sort_error}")
                                decisions = all_decisions[:20]
                    
                    logger.info(f"从文件读取AI决策: {len(decisions)} 条（模型: {model_key}）")
                    if decisions:
                        logger.info(f"第一条决策: signal={decisions[0].get('signal')}, timestamp={decisions[0].get('timestamp')}")
                    return jsonify(decisions)
            except Exception as e:
                logger.warning(f"从文件读取AI决策失败: {e}，尝试从内存读取")
        
        # 如果文件不存在或读取失败，尝试从内存读取（同一进程）
        if hasattr(deepseek_ok_3_0, 'get_model_snapshot'):
            try:
                snapshot = deepseek_ok_3_0.get_model_snapshot(model_key)
                if snapshot and 'symbols' in snapshot:
                    symbols_data = snapshot['symbols']
                    all_decisions = []
                    for sym, symbol_data in symbols_data.items():
                        ai_decisions = symbol_data.get('ai_decisions', [])
                        if ai_decisions and isinstance(ai_decisions, list):
                            all_decisions.extend(ai_decisions)
                    
                    if all_decisions:
                        try:
                            all_decisions.sort(key=lambda x: x.get('timestamp', '') if x and isinstance(x, dict) else '', reverse=True)
                            decisions = all_decisions[:20]
                        except Exception:
                            decisions = all_decisions[:20]
                    
                    logger.info(f"从内存读取AI决策: {len(decisions)} 条")
                    return jsonify(decisions)
            except Exception as e:
                logger.warning(f"从内存读取AI决策失败: {e}")
        
        logger.info(f"未找到AI决策数据，返回空数组")
        return jsonify([])
    except Exception as e:
        logger.error(f"获取AI决策历史失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify([])

@app.route('/api/trades')
@rate_limit
def get_trades():
    """获取交易记录（从OKX API直接读取）"""
    try:
        # 导入主程序模块
        import importlib.util
        module_path = os.path.join(BASE_DIR, 'deepseek_ok_3.0.py')
        spec = importlib.util.spec_from_file_location("deepseek_ok_3_0", module_path)
        deepseek_ok_3_0 = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(deepseek_ok_3_0)
        
        symbol = request.args.get('symbol')
        model_key = request.args.get('model', deepseek_ok_3_0.DEFAULT_MODEL_KEY)
        
        # 获取模型上下文
        if model_key not in deepseek_ok_3_0.MODEL_CONTEXTS:
            return jsonify([])
        
        ctx = deepseek_ok_3_0.MODEL_CONTEXTS[model_key]
        
        # 从 OKX API 直接获取历史仓位记录
        if not ctx.exchange:
            logger.error("交易所未初始化")
            return jsonify([])
        
        # 准备参数：获取历史持仓记录（最近3个月）
        # OKX API 最大支持 limit=100，但为了获取更多数据，我们可能需要多次请求
        # 先尝试获取100条，如果不够可以后续优化
        params = {
            'instType': 'SWAP',  # 永续合约
            'limit': '100'  # 获取最多100条（API最大限制）
        }
        
        # 如果指定了交易对，转换为 instId
        if symbol:
            parts = symbol.replace('/USDT:USDT', '').split('/')
            if len(parts) >= 1:
                base = parts[0]
                inst_id = f"{base}-USDT-SWAP"
                params['instId'] = inst_id
        
        # 调用OKX API获取历史持仓记录
        try:
            response = ctx.exchange.private_get_account_positions_history(params)
            
            if not response or 'data' not in response or not response['data']:
                logger.debug("OKX API返回数据为空")
                return jsonify([])
            
            positions_data = response['data']
            all_positions = list(positions_data)
            
            # 如果返回了100条数据，可能还有更多，继续分页获取
            # 使用最后一个记录的 uTime 作为 before 参数继续获取
            max_requests = 10  # 最多请求10次，避免无限循环
            request_count = 0
            while len(positions_data) == 100 and request_count < max_requests:
                last_time = positions_data[-1].get('uTime', '')
                if last_time:
                    pagination_params = params.copy()
                    pagination_params['before'] = last_time
                    pagination_response = ctx.exchange.private_get_account_positions_history(pagination_params)
                    if not pagination_response or 'data' not in pagination_response or not pagination_response['data']:
                        break
                    positions_data = pagination_response['data']
                    if not positions_data:
                        break
                    all_positions.extend(positions_data)
                    request_count += 1
                    # 如果返回的数据少于100条，说明已经获取完所有数据
                    if len(positions_data) < 100:
                        break
                else:
                    break
            
            logger.info(f"总共获取到 {len(all_positions)} 条历史仓位记录（分页请求 {request_count + 1} 次）")
            
            # 转换OKX格式到前端需要的格式
            trades = []
            for pos in all_positions:
                # OKX positions-history 字段说明：
                # instId: 交易对
                # posSide: long/short (持仓方向)
                # openAvgPx: 开仓均价
                # closeAvgPx: 平仓均价
                # closeTotalPos: 平仓数量
                # realizedPnl: 已实现盈亏
                # pnl: 总盈亏
                # pnlRatio: 盈亏比例
                # lever: 杠杆倍数
                # cTime: 创建时间（毫秒时间戳）
                # uTime: 更新时间（毫秒时间戳）
                # fee: 手续费
                # fundingFee: 资金费用
                
                pos_side = pos.get('posSide', '').lower()
                side_display = pos_side if pos_side in ['long', 'short'] else 'long'
                
                # 使用更新时间作为时间戳
                u_time = pos.get('uTime', '') or pos.get('cTime', '')
                if u_time:
                    try:
                        timestamp_ms = int(u_time)
                        timestamp_dt = datetime.fromtimestamp(timestamp_ms / 1000)
                        timestamp_str = timestamp_dt.strftime('%Y-%m-%d %H:%M:%S')
                    except (ValueError, TypeError):
                        timestamp_str = str(u_time)
                else:
                    timestamp_str = '--'
                
                # 获取盈亏
                realized_pnl = pos.get('realizedPnl', '0')
                pnl = pos.get('pnl', '0')
                try:
                    # 优先使用已实现盈亏，如果没有则使用总盈亏
                    pnl_value = float(realized_pnl) if realized_pnl else float(pnl) if pnl else 0.0
                except (ValueError, TypeError):
                    pnl_value = 0.0
                
                # 获取杠杆
                leverage = pos.get('lever', '1')
                try:
                    leverage_value = int(float(leverage)) if leverage else 1
                except (ValueError, TypeError):
                    leverage_value = 1
                
                # 使用平仓均价作为价格，如果没有则使用开仓均价
                close_price = pos.get('closeAvgPx', '0')
                open_price = pos.get('openAvgPx', '0')
                try:
                    price_value = float(close_price) if close_price and float(close_price) > 0 else float(open_price) if open_price else 0.0
                except (ValueError, TypeError):
                    price_value = 0.0
                
                # 获取持仓数量
                amount = pos.get('closeTotalPos', '0') or pos.get('openMaxPos', '0')
                try:
                    amount_value = float(amount) if amount else 0.0
                except (ValueError, TypeError):
                    amount_value = 0.0
                
                # 计算手续费
                fee = pos.get('fee', '0')
                funding_fee = pos.get('fundingFee', '0')
                try:
                    fee_value = float(fee) if fee else 0.0
                    funding_fee_value = float(funding_fee) if funding_fee else 0.0
                    total_fee = fee_value + funding_fee_value
                except (ValueError, TypeError):
                    total_fee = 0.0
                
                trade = {
                    'symbol': pos.get('instId', '--'),
                    'side': side_display,
                    'price': price_value,
                    'amount': amount_value,
                    'fee': total_fee,
                    'feeCcy': 'USDT',
                    'pnl': pnl_value,
                    'leverage': leverage_value,
                    'timestamp': timestamp_str,
                    'type': 'close',  # 历史仓位记录都是已平仓的
                    'openAvgPx': float(open_price) if open_price else 0.0,
                    'closeAvgPx': float(close_price) if close_price else 0.0,
                    'pnlRatio': float(pos.get('pnlRatio', 0)) if pos.get('pnlRatio') else 0.0,
                    'posId': pos.get('posId', '')
                }
                trades.append(trade)
            
            # 按时间戳排序（最新的在前）
            trades.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            
            logger.info(f"从OKX API获取到 {len(trades)} 条历史仓位记录")
            if trades:
                logger.info(f"第一条交易记录示例: {trades[0] if trades else 'N/A'}")
            return jsonify(trades)
            
        except Exception as api_error:
            logger.error(f"调用OKX API获取历史仓位记录失败: {api_error}")
            import traceback
            logger.error(traceback.format_exc())
            # 返回空数组而不是错误，避免前端显示错误
            return jsonify([])
    except Exception as e:
        logger.error(f"获取交易记录失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify([])

@app.route('/api/dashboard')
@rate_limit
def get_dashboard_data():
    """获取所有交易对的仪表板数据"""
    try:
        # 导入主程序模块
        import importlib.util
        module_path = os.path.join(BASE_DIR, 'deepseek_ok_3.0.py')
        spec = importlib.util.spec_from_file_location("deepseek_ok_3_0", module_path)
        deepseek_ok_3_0 = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(deepseek_ok_3_0)
        
        model_key = request.args.get('model', deepseek_ok_3_0.DEFAULT_MODEL_KEY)
        
        # 获取模型快照
        snapshot = deepseek_ok_3_0.get_model_snapshot(model_key)
        
        # 构建仪表板数据
        symbols_data = []
        for symbol, config in deepseek_ok_3_0.TRADE_CONFIGS.items():
            symbol_data = snapshot['symbols'].get(symbol, {})
            symbols_data.append({
                'symbol': symbol,
                'display': config['display'],
                'current_price': symbol_data.get('current_price', 0),
                'current_position': symbol_data.get('current_position'),
                'performance': symbol_data.get('performance', {}),
                'analysis_records': symbol_data.get('analysis_records', []),
                'last_update': symbol_data.get('last_update'),
                'config': {
                    'timeframe': config['timeframe'],
                    'test_mode': config.get('test_mode', True),
                    'leverage_range': f"{config['leverage_min']}-{config['leverage_max']}"
                }
            })
        
        data = {
            'model': model_key,
            'display': snapshot['display'],
            'symbols': symbols_data,
            'ai_model_info': snapshot['ai_model_info'],
            'account_summary': snapshot['account_summary'],
            'balance_history': snapshot.get('balance_history', [])
        }
        return jsonify(data)
    except Exception as e:
        logger.error(f"获取仪表板数据失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/kline')
@rate_limit
def get_kline_data():
    """获取K线数据 - 支持symbol参数"""
    try:
        # 导入主程序模块
        import importlib.util
        module_path = os.path.join(BASE_DIR, 'deepseek_ok_3.0.py')
        spec = importlib.util.spec_from_file_location("deepseek_ok_3_0", module_path)
        deepseek_ok_3_0 = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(deepseek_ok_3_0)
        
        model_key = request.args.get('model', deepseek_ok_3_0.DEFAULT_MODEL_KEY)
        symbol = request.args.get('symbol', 'BTC/USDT:USDT')
        
        # 获取模型快照
        snapshot = deepseek_ok_3_0.get_model_snapshot(model_key)
        
        if symbol in snapshot['symbols']:
            return jsonify(snapshot['symbols'][symbol].get('kline_data', []))
        return jsonify([])
    except Exception as e:
        logger.error(f"获取K线数据失败: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/profit_curve')
@rate_limit
def get_profit_curve():
    """获取模型的总金额曲线，支持按范围筛选"""
    try:
        # 导入主程序模块
        import importlib.util
        module_path = os.path.join(BASE_DIR, 'deepseek_ok_3.0.py')
        spec = importlib.util.spec_from_file_location("deepseek_ok_3_0", module_path)
        deepseek_ok_3_0 = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(deepseek_ok_3_0)
        
        model_key = request.args.get('model', deepseek_ok_3_0.DEFAULT_MODEL_KEY)
        range_key = request.args.get('range', '7d')
        
        start_ts, end_ts = deepseek_ok_3_0.resolve_time_range(range_key)
        data = deepseek_ok_3_0.history_store.fetch_balance_range(model_key, start_ts, end_ts)
        
        if not data:
            snapshot = deepseek_ok_3_0.get_model_snapshot(model_key)
            data = snapshot.get('balance_history', [])
        
        return jsonify({
            'model': model_key,
            'range': range_key,
            'series': data
        })
    except Exception as e:
        logger.error(f"获取收益曲线失败: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/ai_model_info')
@rate_limit
def get_ai_model_info():
    """获取AI模型信息"""
    try:
        # 导入主程序模块
        import importlib.util
        module_path = os.path.join(BASE_DIR, 'deepseek_ok_3.0.py')
        spec = importlib.util.spec_from_file_location("deepseek_ok_3_0", module_path)
        deepseek_ok_3_0 = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(deepseek_ok_3_0)
        
        # 获取所有模型的状态
        models_status = deepseek_ok_3_0.get_models_status()
        
        return jsonify(models_status)
    except Exception as e:
        logger.error(f"获取AI模型信息失败: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/signals')
@rate_limit
def get_signals():
    """获取信号历史统计（信号分布和信心等级）"""
    try:
        # 导入主程序模块
        import importlib.util
        module_path = os.path.join(BASE_DIR, 'deepseek_ok_3.0.py')
        spec = importlib.util.spec_from_file_location("deepseek_ok_3_0", module_path)
        deepseek_ok_3_0 = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(deepseek_ok_3_0)
        
        symbol = request.args.get('symbol')
        model_key = request.args.get('model', deepseek_ok_3_0.DEFAULT_MODEL_KEY)
        
        # 获取模型上下文
        if model_key not in deepseek_ok_3_0.MODEL_CONTEXTS:
            return jsonify({
                'signal_stats': {'BUY': 0, 'SELL': 0, 'HOLD': 0},
                'confidence_stats': {'HIGH': 0, 'MEDIUM': 0, 'LOW': 0},
                'total_signals': 0,
                'recent_signals': []
            })
        
        ctx = deepseek_ok_3_0.MODEL_CONTEXTS[model_key]
        
        # 统计信号分布和信心等级
        signal_stats = {'BUY': 0, 'SELL': 0, 'HOLD': 0}
        confidence_stats = {'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}
        all_signals = []
        
        # 从信号历史获取（合并所有交易对的信号，或指定交易对）
        signal_map = ctx.signal_history
        
        if symbol and symbol in signal_map:
            # 返回指定交易对的信号
            signals = signal_map[symbol]
            all_signals = signals
        else:
            # 合并所有交易对的信号
            for sym_signals in signal_map.values():
                all_signals.extend(sym_signals)
        
        # 统计信号分布和信心等级
        for signal in all_signals:
            signal_type = signal.get('signal', 'HOLD').upper()
            confidence = signal.get('confidence', 'MEDIUM').upper()
            
            signal_stats[signal_type] = signal_stats.get(signal_type, 0) + 1
            confidence_stats[confidence] = confidence_stats.get(confidence, 0) + 1
        
        # 按时间戳排序，取最近10条
        all_signals.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        recent_signals = all_signals[:10] if all_signals else []
        
        return jsonify({
            'signal_stats': signal_stats,
            'confidence_stats': confidence_stats,
            'total_signals': len(all_signals),
            'recent_signals': recent_signals
        })
    except Exception as e:
        logger.error(f"获取信号统计失败: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'signal_stats': {'BUY': 0, 'SELL': 0, 'HOLD': 0},
            'confidence_stats': {'HIGH': 0, 'MEDIUM': 0, 'LOW': 0},
            'total_signals': 0,
            'recent_signals': []
        })

# WebSocket事件
@socketio.on('connect')
def handle_connect():
    # 连接日志：减少日志噪音，仅在关键信息时记录
    try:
        client_ip = request.environ.get('REMOTE_ADDR', 'unknown') if request else 'unknown'
        # 只在必要时记录（例如：连接数统计、异常连接等）
        # 正常连接不记录，避免日志过多
        pass
    except:
        pass
    emit('status', {'message': '连接成功'})

@socketio.on('disconnect')
def handle_disconnect():
    # 断开日志：减少日志噪音，正常断开不记录
    # 只在异常断开或需要调试时记录
    pass

if __name__ == '__main__':
    # 启动前检查
    logger.info("=" * 50)
    logger.info("加密货币交易机器人启动中...")
    logger.info("支持交易所: OKX (仅支持)")
    logger.info("交易对: BTC/USDT:USDT (永续合约)")
    logger.info("=" * 50)
    
    # 设置OKX交易所（本项目仅支持OKX）
    if not setup_exchange():
        logger.error("OKX交易所初始化失败，请检查API配置")
        logger.error("服务将继续运行，但交易功能可能不可用")
    
    # 启动Flask应用
    logger.info("=" * 50)
    logger.info("Web服务启动中...")
    logger.info("访问地址: http://0.0.0.0:5000")
    logger.info("=" * 50)
    
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, allow_unsafe_werkzeug=True)
