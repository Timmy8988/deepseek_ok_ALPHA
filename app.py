from flask import Flask, render_template, jsonify, request, abort  # type: ignore
from flask_socketio import SocketIO, emit  # type: ignore
import os
import sys
import time
import threading
from datetime import datetime
import json
from dotenv import load_dotenv  # type: ignore
# ccxt 已替换为 OKXClient，从 deepseek_ok_3.0 导入
import pandas as pd  # type: ignore
import logging
import secrets
from functools import wraps
import importlib.util

# 获取项目根目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 先配置基础日志（用于早期日志记录）
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
_temp_logger = logging.getLogger(__name__)

# ==================== 优化：直接导入 deepseek_ok_3_0 模块 ====================
# 由于文件名包含点号，使用 importlib 导入
# 现在单进程运行，可以直接导入，避免重复的动态导入
deepseek_ok_3_0 = None
try:
    module_path = os.path.join(BASE_DIR, 'deepseek_ok_3.0.py')
    spec = importlib.util.spec_from_file_location("deepseek_ok_3_0", module_path)
    deepseek_ok_3_0 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(deepseek_ok_3_0)
    _temp_logger.info("✅ deepseek_ok_3_0 模块已导入（单进程模式，直接使用内存数据）")
except Exception as e:
    _temp_logger.error(f"❌ 导入 deepseek_ok_3_0 模块失败: {e}")
    deepseek_ok_3_0 = None

def get_bot_module():
    """获取bot模块引用（单进程模式下直接返回已导入的模块）"""
    global deepseek_ok_3_0
    if deepseek_ok_3_0 is not None:
        return deepseek_ok_3_0
    # 如果导入失败，尝试重新导入（用于动态导入场景）
    try:
        module_path = os.path.join(BASE_DIR, 'deepseek_ok_3.0.py')
        spec = importlib.util.spec_from_file_location("deepseek_ok_3_0", module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        deepseek_ok_3_0 = module  # 缓存模块引用
        return module
    except Exception as e:
        # 使用临时logger，因为此时logger可能还未完全初始化
        _temp_logger.error(f"❌ 无法获取bot模块: {e}")
        return None

def get_model_context(model_key=None):
    """获取模型上下文（单进程模式优化：直接从内存获取）"""
    bot_module = get_bot_module()
    if bot_module is None:
        return None
    if model_key is None:
        model_key = getattr(bot_module, 'DEFAULT_MODEL_KEY', 'deepseek')
    if hasattr(bot_module, 'MODEL_CONTEXTS') and model_key in bot_module.MODEL_CONTEXTS:
        return bot_module.MODEL_CONTEXTS[model_key]
    return None

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

# 配置完整日志（添加文件处理器）
# 注意：basicConfig 已经在上面调用过，这里只添加文件处理器
logger = logging.getLogger(__name__)
# 清除可能存在的处理器，避免重复
logger.handlers.clear()
# 添加文件和控制台处理器
logger.addHandler(logging.FileHandler(os.path.join(log_dir, 'app.log')))
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.INFO)

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
# 单进程模式优化：不再需要文件共享，直接使用内存数据
# SIGNAL_FILE 已移除，load_latest_signal() 现在直接从内存获取
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
        
        with open(TRADE_STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)
        
        return True
    except Exception as e:
        logger.error(f"❌ 保存交易统计文件失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

# 读取最新交易信号
_last_signal_file_check = None
def load_latest_signal():
    """从内存获取最新交易信号（单进程模式优化：不再使用文件）"""
    try:
        bot_module = get_bot_module()
        if bot_module is None:
            return None
        
        model_key = getattr(bot_module, 'DEFAULT_MODEL_KEY', 'deepseek')
        
        # 直接从内存中的 MODEL_CONTEXTS 获取最新信号
        if hasattr(bot_module, 'MODEL_CONTEXTS') and model_key in bot_module.MODEL_CONTEXTS:
            ctx = bot_module.MODEL_CONTEXTS[model_key]
            signal_history = ctx.signal_history
            
            # 合并所有交易对的信号历史，获取最新的
            all_signals = []
            for symbol, signals in signal_history.items():
                if signals:
                    all_signals.extend(signals)
            
            if all_signals:
                # 按时间戳排序，获取最新的信号
                all_signals.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
                latest_record = all_signals[0]
                return {
                    'signal': latest_record.get('signal', 'HOLD'),
                    'confidence': latest_record.get('confidence', 'MEDIUM'),
                    'timestamp': latest_record.get('timestamp', ''),
                    'entry_price': latest_record.get('entry_price'),
                    'reason': latest_record.get('reason'),
                    'stop_loss': latest_record.get('stop_loss'),
                    'take_profit': latest_record.get('take_profit')
                }
        
            return None
    except Exception as e:
        logger.debug(f"从内存获取最新信号失败: {e}")
        return None

# 读取机器人配置文件
def load_bot_config():
    """从配置文件加载机器人配置"""
    try:
        if os.path.exists(BOT_CONFIG_FILE):
            with open(BOT_CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                # 确保 test_mode 有值（如果不存在或为 None，才设置默认值）
                # 注意：如果用户明确设置为 False，这里不应该覆盖
                if 'test_mode' not in config:
                    config['test_mode'] = True
                    # 只在配置项完全不存在时才保存默认值
                    save_bot_config(config)
                elif config.get('test_mode') is None:
                    # 如果存在但值为 None，也设置为默认值
                    config['test_mode'] = True
                    save_bot_config(config)
                return config
        else:
            # 默认配置
            default_config = {
                'test_mode': True,  # 默认测试模式
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
            f.flush()
            os.fsync(f.fileno())
        logger.info(f"配置已保存到: {BOT_CONFIG_FILE}, test_mode={config.get('test_mode')}")
        return True
    except Exception as e:
        logger.error(f"保存机器人配置失败: {e}")
        return False

# 全局变量（单进程模式优化：bot逻辑在deepseek_ok_3.0.py中）
bot_thread = None

# 从配置文件加载配置
bot_config = load_bot_config()

# 安全获取配置值，确保类型正确
def safe_get_config(key, default):
    """安全获取配置值，处理None值"""
    value = bot_config.get(key, default)
    if value is None:
        return default
    
    # 特殊处理 test_mode，确保返回布尔值
    if key == 'test_mode':
        if isinstance(value, bool):
            return value
        elif isinstance(value, str):
            return value.lower() in ('true', '1', 'yes', 'on')
        else:
            return bool(value)
    
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

# 单进程模式优化：DeepSeek客户端初始化在deepseek_ok_3.0.py中，这里不再需要
# 环境变量检查在deepseek_ok_3.0.py中进行

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
    # 单进程模式优化：使用已导入的模块
    deepseek_module = get_bot_module()
    if deepseek_module is None:
        logger.error("无法导入 deepseek_ok_3_0 模块，无法初始化交易所")
        exchange = None  # 设置为None，后续检查
    else:
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

def get_exchange_instance():
    """获取exchange实例（单进程模式优化：优先使用bot模块的exchange）"""
    bot_module = get_bot_module()
    if bot_module:
        model_key = getattr(bot_module, 'DEFAULT_MODEL_KEY', 'deepseek')
        ctx = get_model_context(model_key)
        if ctx and ctx.exchange:
            return ctx.exchange
    return exchange  # 回退到app.py的exchange

def setup_exchange():
    """设置OKX交易所参数（本项目仅支持OKX交易所）"""
    try:
        # 单进程模式优化：优先使用bot模块的exchange
        exchange_instance = get_exchange_instance()
        if exchange_instance is None:
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
        exchange_instance.private_post_account_set_leverage(params)
        logger.info(f"OKX杠杆已设置: {leverage}x")
        
        # 获取OKX账户余额（直接API调用，使用account/balance端点）
        balance_response = exchange_instance.private_get_account_balance({'ccy': 'USDT'})
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
        
        # 验证API连接
        return True
    except Exception as e:
        logger.error(f"OKX交易所设置失败: {e}")
        logger.error(f"错误类型: {type(e).__name__}")
        import traceback
        logger.error(f"详细错误信息: {traceback.format_exc()}")
        logger.error("请检查OKX API密钥是否正确，以及是否设置了IP白名单")
        return False

def get_btc_ohlcv():
    """从OKX获取BTC/USDT永续合约K线数据（单进程模式优化：使用bot模块的exchange）"""
    try:
        exchange_instance = get_exchange_instance()
        if exchange_instance is None:
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
        response = exchange_instance.public_get_market_candles(params)
        
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
    """从OKX获取当前持仓情况（单进程模式优化：使用bot模块的exchange）"""
    try:
        exchange_instance = get_exchange_instance()
        if exchange_instance is None:
            logger.error("OKX交易所未初始化，无法获取持仓信息")
            return None
        
        symbol = 'BTC/USDT:USDT'  # OKX永续合约格式
        inst_id = 'BTC-USDT-SWAP'
        
        # 获取持仓（直接API调用）
        response = exchange_instance.private_get_account_positions({'instId': inst_id})
        if not response or 'data' not in response:
            raise Exception(f"获取持仓失败: API返回数据为空")
        
        positions_data = response['data']
        
        # 获取账户余额（直接API调用，使用account/balance端点）
        balance_response = exchange_instance.private_get_account_balance({'ccy': 'USDT'})
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

# 单进程模式优化：交易逻辑已移至 deepseek_ok_3.0.py
# 以下遗留函数已删除：analyze_with_deepseek, create_market_order_safe, execute_trade, trading_bot

# 路由定义
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status')
@rate_limit
def get_status():
    """获取机器人状态"""
    try:
        # 单进程模式优化：通过PM2检查进程实际运行状态
        import subprocess
        import platform
        bot_running = False
        
        try:
            is_windows = platform.system() == 'Windows'
            if is_windows:
                result = subprocess.run('pm2 jlist', shell=True, capture_output=True, text=True, timeout=5)
            else:
                result = subprocess.run(['pm2', 'jlist'], capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                import json
                processes = json.loads(result.stdout)
                for proc in processes:
                    if proc.get('name') == 'dsok':
                        status = proc.get('pm2_env', {}).get('status', 'unknown')
                        bot_running = status == 'online'
                        break
        except Exception:
            # PM2检查失败，不影响其他功能
            pass
        
        bot_module = get_bot_module()
        
        position = get_current_position()
        price_data = get_btc_ohlcv()
        
        # 从内存获取最新信号（单进程模式优化）
        latest_signal = load_latest_signal()
        if latest_signal:
            latest_signal_type = latest_signal.get('signal', 'HOLD')
            latest_confidence = latest_signal.get('confidence', 'MEDIUM')
            signal_timestamp = latest_signal.get('timestamp', 'N/A')
        else:
            latest_signal_type = 'HOLD'
            latest_confidence = 'N/A'
            signal_timestamp = 'N/A'
        
        # 加载交易统计信息
        trade_stats = load_trade_stats()
        
        # 计算总盈亏：当前资金 - 初始资金
        current_balance = 0
        initial_balance = 0
        
        # 单进程模式优化：优先使用bot模块的exchange
        exchange_instance = None
        if bot_module:
            model_key = getattr(bot_module, 'DEFAULT_MODEL_KEY', 'deepseek')
            ctx = get_model_context(model_key)
            if ctx and ctx.exchange:
                exchange_instance = ctx.exchange
        if exchange_instance is None:
            exchange_instance = exchange  # 回退到app.py的exchange
        
        # 获取当前账户余额（总是直接获取，确保准确性）
        try:
            if exchange_instance is not None:
                balance_response = exchange_instance.private_get_account_balance({'ccy': 'USDT'})
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
        
        # 从文件读取最新配置（确保返回最新的test_mode值）
        current_config = load_bot_config()
        # 同步更新内存中的trading_config
        trading_config.update(current_config)
        
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
            result = subprocess.run('pm2 start dsok', 
                                  shell=True,
                                  capture_output=True, 
                                  text=True, 
                                  timeout=10)
        else:
            result = subprocess.run(['pm2', 'start', 'dsok'], 
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
            result = subprocess.run('pm2 stop dsok', 
                                  shell=True,
                                  capture_output=True, 
                                  text=True, 
                                  timeout=10)
        else:
            result = subprocess.run(['pm2', 'stop', 'dsok'], 
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
        import shutil
        
        logger.info("收到重启机器人请求")
        
        # 确定项目目录（优先使用 /dsok，否则使用当前文件所在目录）
        project_dir = '/dsok' if os.path.exists('/dsok') else BASE_DIR
        logger.info(f"项目目录: {project_dir}")
        
        # 查找 PM2 可执行文件路径
        pm2_path = shutil.which('pm2')
        if not pm2_path:
            # 尝试常见路径
            import glob
            common_paths = [
                '/usr/local/bin/pm2',
                '/usr/bin/pm2',
                '/opt/nodejs/bin/pm2',
                '/home/ubuntu/.nvm/versions/node/*/bin/pm2',
                os.path.expanduser('~/.nvm/versions/node/*/bin/pm2'),
                '/root/.nvm/versions/node/*/bin/pm2'
            ]
            for path_pattern in common_paths:
                matches = glob.glob(path_pattern)
                if matches:
                    pm2_path = matches[0]
                    if os.path.exists(pm2_path) and os.access(pm2_path, os.X_OK):
                        break
                    pm2_path = None
        
        # 如果仍然找不到，尝试直接使用 'pm2'（假设它在 PATH 中，但 which 可能因为环境变量问题找不到）
        if not pm2_path:
            pm2_path = 'pm2'
            logger.warning("PM2 路径未找到，将尝试直接使用 'pm2' 命令")
        else:
            logger.info(f"使用 PM2 路径: {pm2_path}")
        
        # Windows 环境下需要使用 shell=True
        is_windows = platform.system() == 'Windows'
        
        # 构建命令 - 使用完整路径，并切换到项目目录
        if is_windows:
            cmd = f'cd /d "{project_dir}" && "{pm2_path}" restart dsok'
            cmd_display = cmd
            result = subprocess.run(cmd, 
                                  shell=True,
                                  capture_output=True, 
                                  text=True, 
                                  timeout=15,
                                  env=os.environ.copy(),
                                  cwd=project_dir)
        else:
            # Linux 环境：使用 bash -c 来加载环境变量（更可靠）
            # 切换到项目目录，加载环境变量，然后执行 PM2 命令
            bash_cmd = f'''cd "{project_dir}" || exit 1
# 尝试加载 nvm（如果存在）
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && source "$NVM_DIR/nvm.sh" 2>/dev/null || true
[ -s "$HOME/.nvm/nvm.sh" ] && source "$HOME/.nvm/nvm.sh" 2>/dev/null || true

# 加载用户环境变量
[ -s "$HOME/.bashrc" ] && source "$HOME/.bashrc" 2>/dev/null || true
[ -s "$HOME/.profile" ] && source "$HOME/.profile" 2>/dev/null || true
[ -s "$HOME/.bash_profile" ] && source "$HOME/.bash_profile" 2>/dev/null || true

# 执行 PM2 重启命令
{pm2_path} restart dsok 2>&1'''
            cmd_display = f"bash -c 'cd {project_dir} && ... (加载环境变量) ... {pm2_path} restart dsok'"
            result = subprocess.run(bash_cmd, 
                                  shell=True,
                                  executable='/bin/bash',
                                  capture_output=True, 
                                  text=True, 
                                  timeout=15,
                                  env=os.environ.copy(),
                                  cwd=project_dir)
        
        logger.info(f"PM2 restart 命令: {cmd_display}")
        logger.info(f"PM2 restart 工作目录: {project_dir}")
        logger.info(f"PM2 restart 返回码: {result.returncode}")
        logger.info(f"PM2 restart 标准输出: {result.stdout[:1000] if result.stdout else '(空)'}")
        if result.stderr:
            logger.info(f"PM2 restart 错误输出: {result.stderr[:1000]}")
        
        # PM2 restart 即使成功也可能返回非0，检查输出内容
        output = (result.stdout or '') + (result.stderr or '')
        output_lower = output.lower()
        
        # 检查是否成功（多种判断方式）
        success_indicators = [
            result.returncode == 0,
            'restarted' in output_lower,
            'restarting' in output_lower,
            'successfully' in output_lower,
            'online' in output_lower,
            'process restarted' in output_lower,
            '✓' in output  # PM2 成功标志
        ]
        
        # 检查是否是因为进程不存在（这种情况下应该尝试启动）
        if 'not found' in output_lower or 'doesn\'t exist' in output_lower or 'name not found' in output_lower:
            logger.warning(f"PM2 进程 'dsok' 不存在，尝试启动...")
            # 尝试启动进程
            if is_windows:
                start_cmd = f'cd /d "{project_dir}" && "{pm2_path}" start ecosystem.config.js --name dsok'
            else:
                start_cmd = f'''cd "{project_dir}" || exit 1
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && source "$NVM_DIR/nvm.sh" 2>/dev/null || true
[ -s "$HOME/.nvm/nvm.sh" ] && source "$HOME/.nvm/nvm.sh" 2>/dev/null || true
[ -s "$HOME/.bashrc" ] && source "$HOME/.bashrc" 2>/dev/null || true
[ -s "$HOME/.profile" ] && source "$HOME/.profile" 2>/dev/null || true
{pm2_path} start ecosystem.config.js --name dsok 2>&1'''
            
            start_result = subprocess.run(start_cmd, 
                                         shell=True,
                                         executable='/bin/bash' if not is_windows else None,
                                         capture_output=True, 
                                         text=True, 
                                         timeout=15,
                                         env=os.environ.copy(),
                                         cwd=project_dir)
            
            logger.info(f"PM2 start 返回码: {start_result.returncode}")
            logger.info(f"PM2 start 输出: {start_result.stdout[:500] if start_result.stdout else '(空)'}")
            
            if start_result.returncode == 0 or 'online' in (start_result.stdout or '').lower():
                logger.info("交易机器人启动命令执行成功")
                import time
                time.sleep(1)
                return jsonify({'success': True, 'message': '机器人已启动（进程不存在，已重新启动）！页面将在5秒后自动刷新。'})
            else:
                error_msg = start_result.stderr if start_result.stderr else start_result.stdout
                logger.error(f"启动机器人失败: {error_msg}")
                return jsonify({'success': False, 'message': f'进程不存在且启动失败: {error_msg[:200]}'}), 500
        
        if any(success_indicators):
            logger.info("交易机器人重启命令执行成功")
            # 等待一小段时间确保进程重启
            import time
            time.sleep(1)
            return jsonify({'success': True, 'message': '机器人重启命令已执行！页面将在5秒后自动刷新。'})
        else:
            error_msg = result.stderr if result.stderr else result.stdout
            if not error_msg:
                error_msg = f'未知错误 (返回码: {result.returncode})'
            logger.error(f"重启机器人失败: 返回码={result.returncode}, 错误={error_msg}")
            return jsonify({'success': False, 'message': f'重启失败: {error_msg[:300]}'}), 500
            
    except subprocess.TimeoutExpired:
        logger.error("重启机器人超时")
        return jsonify({'success': False, 'message': '重启超时，请稍后手动检查'}), 500
    except FileNotFoundError as e:
        logger.error(f"PM2 未找到: {e}")
        return jsonify({'success': False, 'message': f'PM2 未安装或不在 PATH 中: {str(e)}'}), 500
    except Exception as e:
        logger.error(f"重启机器人失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
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
                # 单进程模式：检查进程名 'dsok'
                if proc.get('name') == 'dsok':
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
        global trading_config, bot_config
        
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
        
        # 更新 bot_config
        bot_config = load_bot_config()
        
        # 更新配置
        test_mode_value = None
        if 'test_mode' in data:
            # 确保正确转换为布尔值
            test_mode_value = data['test_mode']
            if isinstance(test_mode_value, str):
                test_mode_value = test_mode_value.lower() in ('true', '1', 'yes', 'on')
            else:
                test_mode_value = bool(test_mode_value)
            bot_config['test_mode'] = test_mode_value
            trading_config['test_mode'] = test_mode_value
        
        if 'leverage' in data:
            leverage_value = int(data['leverage'])
            bot_config['leverage'] = leverage_value
            trading_config['leverage'] = leverage_value
        if 'timeframe' in data:
            timeframe_value = str(data['timeframe'])
            bot_config['timeframe'] = timeframe_value
            trading_config['timeframe'] = timeframe_value
        if 'base_usdt_amount' in data:
            base_usdt_value = float(data['base_usdt_amount'])
            bot_config['base_usdt_amount'] = base_usdt_value
            trading_config['base_usdt_amount'] = base_usdt_value
        
        # 保存到文件（确保立即写入磁盘）
        if not save_bot_config(bot_config):
            return jsonify({'success': False, 'message': '保存配置文件失败'}), 500
        
        # 验证保存结果（重新读取文件确认）
        saved_config = load_bot_config()
        saved_test_mode = saved_config.get('test_mode')
        if test_mode_value is not None:
            logger.info(f"配置已更新并保存: test_mode={saved_test_mode} (请求值={test_mode_value})")
            if saved_test_mode != test_mode_value:
                logger.error(f"⚠️ 配置保存后验证失败: 期望={test_mode_value}, 实际={saved_test_mode}")
                # 如果验证失败，尝试再次保存
                saved_config['test_mode'] = test_mode_value
                save_bot_config(saved_config)
        
        return jsonify({
            'success': True, 
            'message': '配置已保存',
            'config': dict(trading_config)
        })
            
    except Exception as e:
        logger.error(f"更新配置失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'message': f'更新失败: {str(e)}'}), 500

@app.route('/api/refresh_data', methods=['POST'])
@rate_limit
def refresh_data():
    """立即刷新数据"""
    try:
        price_data = get_btc_ohlcv()
        position = get_current_position()
        
        # 从内存获取最新信号（单进程模式优化）
        latest_signal = load_latest_signal()
        if latest_signal:
            latest_signal_type = latest_signal.get('signal', 'HOLD')
            latest_confidence = latest_signal.get('confidence', 'MEDIUM')
        else:
            latest_signal_type = 'HOLD'
            latest_confidence = 'N/A'
        
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
    """获取交易机器人的实时日志（单进程模式：合并读取所有日志文件）"""
    try:
        # PM2日志文件路径（单进程模式：读取所有可能的日志文件）
        pm2_log_files = [
            os.path.join(BASE_DIR, 'logs', 'pm2-combined.log'),
            os.path.join(BASE_DIR, 'logs', 'pm2-out.log'),
            os.path.join(BASE_DIR, 'logs', 'pm2-error.log'),
            os.path.join(BASE_DIR, 'logs', 'app.log'),
            os.path.join(BASE_DIR, 'logs', 'trading_bot.log')
        ]
        
        # 收集所有存在的日志文件的内容
        all_lines = []
        log_files_found = []
        
        for log_file in pm2_log_files:
            if os.path.exists(log_file):
                try:
                    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                        file_lines = f.readlines()
                        # 为每行添加文件标识（用于调试）
                        for line in file_lines:
                            all_lines.append((log_file, line.strip()))
                        log_files_found.append(log_file)
                except Exception as e:
                    logger.debug(f"读取日志文件失败 {log_file}: {e}")
                    continue
        
        # 如果所有日志文件都不存在，返回提示信息
        if not all_lines:
            return jsonify({
                'success': True,
                'logs': ['交易机器人尚未启动，日志文件不存在'],
                'file_exists': False
            })
        
        # 按时间戳排序（最新的在前）
        # 尝试从日志行中提取时间戳进行排序
        import re
        def extract_timestamp(line_tuple):
            _, line = line_tuple
            # PM2格式: "1|dsok | 2025-11-05T17:42:02: 消息内容"
            # 或: "2025-11-05T17:42:02: 消息内容"
            # 或: "2025-11-05 17:42:02,123 - INFO - 消息内容"
            # 或: "2025-11-05 17:42:02 - INFO - 消息内容"
            
            # 优先尝试 PM2 格式
            if '|' in line and 'T' in line:
                parts = line.split('|', 2)
                if len(parts) >= 3:
                    time_part = parts[2].strip()
                    # 提取 ISO 格式时间戳
                    match = re.search(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})', time_part)
                    if match:
                        return match.group(1)
            
            # 尝试标准 ISO 格式 (2025-11-05T17:42:02)
            match = re.search(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})', line)
            if match:
                return match.group(1)
            
            # 尝试标准日期时间格式 (2025-11-05 17:42:02)
            match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
            if match:
                # 转换为 ISO 格式以便排序
                return match.group(1).replace(' ', 'T')
            
            # 如果都没有，返回空字符串（这些日志会排在最后）
            return ''
        
        # 按时间戳排序，最新的在前（空字符串会排到最后）
        all_lines.sort(key=extract_timestamp, reverse=True)
        
        # 过滤和格式化日志行（只保留bot的运行日志）
        formatted_logs = []
        
        # 简化过滤：只读取 pm2-out.log 文件，只保留包含 |dsok 的行
        # 这些是bot的实际运行日志（参考用户提供的日志格式）
        filtered_lines = []
        for file_path, line in all_lines:
            if not line or not line.strip():
                continue
            
            # 只保留 pm2-out.log 中包含 |dsok 的行（这是bot的标准输出）
            if 'pm2-out.log' in file_path:
                # PM2格式: "0|dsok     | 2025-11-05T22:40:06: 消息内容"
                if '|dsok' in line:
                    # 只过滤掉明显的 web 服务器日志
                    line_lower = line.lower()
                    # 只过滤明确的 HTTP 请求日志
                    if 'werkzeug' in line_lower or ('get /api/' in line_lower and 'trading_logs' not in line_lower):
                        continue
                    filtered_lines.append(line)
        
        # 只返回最近200行（最新的在前）
        recent_lines = filtered_lines[:200]
        
        # 格式化日志行：提取时间戳和消息内容
        for line in recent_lines:
            # PM2格式: "0|dsok     | 2025-11-05T22:40:06: 消息内容"
            if '|' in line and 'T' in line:
                parts = line.split('|', 2)
                if len(parts) >= 3:
                    # 提取时间戳和消息部分: "2025-11-05T22:40:06: 消息内容"
                    time_and_msg = parts[2].strip()
                    if time_and_msg:
                        formatted_logs.append(time_and_msg)
                        continue
            # 如果格式不匹配，保留原始行
            formatted_logs.append(line)
        
        return jsonify({
            'success': True,
            'logs': formatted_logs,
            'file_exists': True,
            'total_lines': len(all_lines),
            'log_files': [os.path.basename(f) for f in log_files_found]
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
            # 获取模型上下文（单进程模式：直接从内存获取）
            bot_module = get_bot_module()
            if bot_module is None:
                pass  # 继续执行，使用默认值
            else:
                model_key = request.args.get('model', getattr(bot_module, 'DEFAULT_MODEL_KEY', 'deepseek'))
                ctx = get_model_context(model_key)
            
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
            # 单进程模式：直接从内存获取
            bot_module = get_bot_module()
            if bot_module:
                model_key = request.args.get('model', getattr(bot_module, 'DEFAULT_MODEL_KEY', 'deepseek'))
                ctx = get_model_context(model_key)
                
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
                        initial_timestamp = (datetime.now() - timedelta(days=1)).isoformat()
                else:
                    # 如果没有配置时间，使用当前时间减去1天作为入金时间
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
        bot_module = get_bot_module()
        if bot_module is None:
            return jsonify({'error': '无法获取bot模块'}), 500
        
        payload = bot_module.get_overview_payload(range_key)
        payload['models_metadata'] = bot_module.get_model_metadata()
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
        bot_module = get_bot_module()
        if bot_module is None:
            return jsonify({'error': '无法获取bot模块'}), 500
        
        return jsonify({
            'default': bot_module.DEFAULT_MODEL_KEY,
            'models': bot_module.get_model_metadata()
        })
    except Exception as e:
        logger.error(f"获取模型列表失败: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/ai_decisions')
@rate_limit
def get_ai_decisions():
    """获取AI决策历史（单进程模式优化：直接从内存获取）"""
    try:
        bot_module = get_bot_module()
        if bot_module is None:
            return jsonify([])
        
        symbol = request.args.get('symbol')
        model_key = request.args.get('model', getattr(bot_module, 'DEFAULT_MODEL_KEY', 'deepseek'))
        
        # 直接从内存获取（单进程模式）
        ctx = get_model_context(model_key)
        if ctx and hasattr(ctx, 'web_data') and 'symbols' in ctx.web_data:
            symbols_data = ctx.web_data['symbols']
            all_decisions = []
            
            for sym, symbol_data in symbols_data.items():
                if symbol and symbol != sym:
                    continue
                ai_decisions = symbol_data.get('ai_decisions', [])
                if ai_decisions and isinstance(ai_decisions, list):
                    all_decisions.extend(ai_decisions)
            
            if all_decisions:
                try:
                    all_decisions.sort(key=lambda x: x.get('timestamp', '') if x and isinstance(x, dict) else '', reverse=True)
                    decisions = all_decisions[:20]
                except Exception:
                    decisions = all_decisions[:20]
                
                return jsonify(decisions)
        
        return jsonify([])
    except Exception as e:
        logger.error(f"获取AI决策历史失败: {e}")
        return jsonify([])

@app.route('/api/trades')
@rate_limit
def get_trades():
    """获取交易记录（从OKX API直接读取）"""
    try:
        bot_module = get_bot_module()
        if bot_module is None:
            return jsonify([])
        
        symbol = request.args.get('symbol')
        model_key = request.args.get('model', getattr(bot_module, 'DEFAULT_MODEL_KEY', 'deepseek'))
        
        # 获取模型上下文（单进程模式：直接从内存获取）
        ctx = get_model_context(model_key)
        if ctx is None:
            return jsonify([])
        
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
                
                # 解析持仓方向 - 直接使用 OKX API 返回的 posSide 字段
                # OKX API positions-history 接口返回的 posSide 字段值：
                # - "long" 表示多头持仓
                # - "short" 表示空头持仓
                # - "net" 表示净持仓（双向持仓模式，通常不会出现在历史记录中）
                
                pos_side_raw = pos.get('posSide', '').strip()
                
                if pos_side_raw:
                    pos_side = pos_side_raw.lower()
                    if pos_side in ['long', 'short']:
                        side_display = pos_side
                    elif pos_side == 'net':
                        # 净持仓模式（双向持仓模式），通过价格变化和盈亏判断方向
                        open_price = pos.get('openAvgPx', '0')
                        close_price = pos.get('closeAvgPx', '0')
                        realized_pnl = pos.get('realizedPnl', '0')
                        
                        try:
                            open_px = float(open_price) if open_price else 0
                            close_px = float(close_price) if close_price else 0
                            pnl_val = float(realized_pnl) if realized_pnl else 0
                            
                            if open_px > 0 and close_px > 0:
                                price_change = close_px - open_px
                                if (price_change > 0 and pnl_val > 0) or (price_change < 0 and pnl_val < 0):
                                    side_display = 'long'
                                elif (price_change < 0 and pnl_val > 0) or (price_change > 0 and pnl_val < 0):
                                    side_display = 'short'
                                else:
                                    side_display = 'long'
                            else:
                                side_display = 'long'
                        except (ValueError, TypeError):
                            side_display = 'long'
                    else:
                        side_display = 'long'
                else:
                    # posSide 字段不存在或为空，尝试通过价格和盈亏推断方向
                    open_price = pos.get('openAvgPx', '0')
                    close_price = pos.get('closeAvgPx', '0')
                    realized_pnl = pos.get('realizedPnl', '0')
                    
                    try:
                        open_px = float(open_price) if open_price else 0
                        close_px = float(close_price) if close_price else 0
                        pnl_val = float(realized_pnl) if realized_pnl else 0
                        
                        if open_px > 0 and close_px > 0:
                            price_change = close_px - open_px
                            if (price_change > 0 and pnl_val > 0) or (price_change < 0 and pnl_val < 0):
                                side_display = 'long'
                            elif (price_change < 0 and pnl_val > 0) or (price_change > 0 and pnl_val < 0):
                                side_display = 'short'
                            else:
                                side_display = 'long'
                        else:
                            side_display = 'long'
                    except (ValueError, TypeError):
                        side_display = 'long'
                
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
            
            return jsonify(trades)
            
        except Exception as api_error:
            logger.error(f"调用OKX API获取历史仓位记录失败: {api_error}")
            return jsonify([])
    except Exception as e:
        logger.error(f"获取交易记录失败: {e}")
        return jsonify([])

@app.route('/api/dashboard')
@rate_limit
def get_dashboard_data():
    """获取所有交易对的仪表板数据"""
    try:
        bot_module = get_bot_module()
        if bot_module is None:
            return jsonify({'error': '无法获取bot模块'}), 500
        
        model_key = request.args.get('model', getattr(bot_module, 'DEFAULT_MODEL_KEY', 'deepseek'))
        
        # 获取模型快照（单进程模式：直接从内存获取）
        snapshot = bot_module.get_model_snapshot(model_key)
        
        # 构建仪表板数据
        symbols_data = []
        for symbol, config in bot_module.TRADE_CONFIGS.items():
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
        bot_module = get_bot_module()
        if bot_module is None:
            return jsonify([])
        
        model_key = request.args.get('model', getattr(bot_module, 'DEFAULT_MODEL_KEY', 'deepseek'))
        symbol = request.args.get('symbol', 'BTC/USDT:USDT')
        
        # 获取模型快照（单进程模式：直接从内存获取）
        snapshot = bot_module.get_model_snapshot(model_key)
        
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
        bot_module = get_bot_module()
        if bot_module is None:
            return jsonify({'error': '无法获取bot模块'}), 500
        
        model_key = request.args.get('model', getattr(bot_module, 'DEFAULT_MODEL_KEY', 'deepseek'))
        range_key = request.args.get('range', '7d')
        
        start_ts, end_ts = bot_module.resolve_time_range(range_key)
        data = bot_module.history_store.fetch_balance_range(model_key, start_ts, end_ts)
        
        if not data:
            snapshot = bot_module.get_model_snapshot(model_key)
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
        bot_module = get_bot_module()
        if bot_module is None:
            return jsonify({'error': '无法获取bot模块'}), 500
        
        # 获取所有模型的状态（单进程模式：直接从内存获取）
        models_status = bot_module.get_models_status()
        
        return jsonify(models_status)
    except Exception as e:
        logger.error(f"获取AI模型信息失败: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/signals')
@rate_limit
def get_signals():
    """获取信号历史统计（信号分布和信心等级）"""
    try:
        bot_module = get_bot_module()
        if bot_module is None:
            return jsonify({
                'signal_stats': {'BUY': 0, 'SELL': 0, 'HOLD': 0},
                'confidence_stats': {'HIGH': 0, 'MEDIUM': 0, 'LOW': 0},
                'total_signals': 0,
                'recent_signals': []
            })
        
        symbol = request.args.get('symbol')
        model_key = request.args.get('model', getattr(bot_module, 'DEFAULT_MODEL_KEY', 'deepseek'))
        
        # 获取模型上下文（单进程模式：直接从内存获取）
        ctx = get_model_context(model_key)
        if ctx is None:
            return jsonify({
                'signal_stats': {'BUY': 0, 'SELL': 0, 'HOLD': 0},
                'confidence_stats': {'HIGH': 0, 'MEDIUM': 0, 'LOW': 0},
                'total_signals': 0,
                'recent_signals': []
            })
        
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

def run_trading_bot():
    """在独立线程中运行交易机器人（单进程模式：使用已导入的模块）"""
    try:
        # 使用已导入的模块（单进程模式优化）
        bot_module = get_bot_module()
        if bot_module is None:
            logger.error("❌ 无法获取bot模块，交易机器人线程无法启动")
            return
        
        # 运行交易机器人的主循环
        logger.info("🤖 交易机器人线程启动中...")
        bot_module.main()
    except Exception as e:
        logger.error(f"❌ 交易机器人线程异常: {e}")
        import traceback
        logger.error(traceback.format_exc())


if __name__ == '__main__':
    # 启动多交易对交易机器人Web监控
    print("\n" + "=" * 60)
    print("🚀 启动多交易对交易机器人Web监控...")
    print("=" * 60 + "\n")
    
    # 启动交易机器人线程（后台运行）
    bot_thread = threading.Thread(target=run_trading_bot, daemon=True)
    bot_thread.start()
    logger.info("✅ 交易机器人线程已启动（后台运行）")
    
    # 等待一小段时间，确保bot线程初始化完成
    time.sleep(2)
    
    # 启动Web服务器
    PORT = 5000
    print("\n" + "=" * 60)
    print("🌐 Web管理界面启动成功！")
    print(f"📊 访问地址: http://0.0.0.0:{PORT}")
    print(f"📁 项目目录: {BASE_DIR}")
    print("=" * 60 + "\n")
    
    try:
        logger.info(f"[Web Server] 正在启动Flask服务器，监听端口 {PORT}...")
        socketio.run(app, host='0.0.0.0', port=PORT, debug=False, allow_unsafe_werkzeug=True, use_reloader=False)
    except Exception as e:
        logger.error(f"[Web Server] 启动失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)
