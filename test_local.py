#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地测试脚本 - 测试 OKXClient 类
"""

import os
import sys

# 设置 Windows 控制台编码
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_okx_client_import():
    """测试 OKXClient 类是否可以正常导入"""
    print("="*70)
    print("测试 1: 导入 OKXClient 类")
    print("="*70)
    
    try:
        # 动态导入（因为文件名包含点号）
        import importlib.util
        module_path = os.path.join(os.path.dirname(__file__), 'deepseek_ok_3.0.py')
        spec = importlib.util.spec_from_file_location("deepseek_ok_3_0", module_path)
        deepseek_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(deepseek_module)
        
        OKXClient = deepseek_module.OKXClient
        OKXAPIError = deepseek_module.OKXAPIError
        InsufficientFunds = deepseek_module.InsufficientFunds
        
        print("✅ OKXClient 类导入成功")
        print(f"✅ OKXAPIError 类导入成功")
        print(f"✅ InsufficientFunds 类导入成功")
        return True, OKXClient, OKXAPIError, InsufficientFunds
    except Exception as e:
        print(f"❌ 导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False, None, None, None

def test_okx_client_init():
    """测试 OKXClient 初始化"""
    print("\n" + "="*70)
    print("测试 2: 初始化 OKXClient")
    print("="*70)
    
    success, OKXClient, _, _ = test_okx_client_import()
    if not success:
        return False, None
    
    try:
        from dotenv import load_dotenv
        load_dotenv()
        
        api_key = os.getenv('OKX_API_KEY', '').strip()
        secret = os.getenv('OKX_SECRET', '').strip()
        password = os.getenv('OKX_PASSWORD', '').strip()
        
        if not all([api_key, secret, password]):
            print("⚠️  警告: 未配置 OKX API 密钥，跳过初始化测试")
            print("   请在 .env 文件中配置 OKX_API_KEY, OKX_SECRET, OKX_PASSWORD")
            return True, None
        
        client = OKXClient(
            api_key=api_key,
            secret=secret,
            password=password,
            sub_account=None,
            sandbox=False,
            enable_rate_limit=True
        )
        
        print("✅ OKXClient 初始化成功")
        print(f"   API Key: {api_key[:8]}...{api_key[-4:] if len(api_key) > 12 else '***'}")
        print(f"   Secret: {secret[:8]}...{secret[-4:] if len(secret) > 12 else '***'}")
        print(f"   Password 长度: {len(password)} 字符")
        return True, client
    except Exception as e:
        print(f"❌ 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False, None

def test_okx_client_methods():
    """测试 OKXClient 方法"""
    print("\n" + "="*70)
    print("测试 3: 检查 OKXClient 方法")
    print("="*70)
    
    success, client = test_okx_client_init()
    if not success or client is None:
        return False
    
    # 检查必需的方法
    required_methods = [
        '_sign',
        '_get_headers',
        '_request',
        'public_get_public_instruments',
        'public_get_market_candles',
        'private_get_account_balance',
        'private_get_account_positions',
        'private_post_account_set_leverage',
        'private_post_trade_order',
        'fetch_ohlcv',
        'fetch_positions',
        'fetch_balance',
        'create_market_order',
        'set_leverage',
        'load_markets',
    ]
    
    missing_methods = []
    for method in required_methods:
        if not hasattr(client, method):
            missing_methods.append(method)
    
    if missing_methods:
        print(f"❌ 缺少方法: {', '.join(missing_methods)}")
        return False
    else:
        print(f"✅ 所有必需方法都存在 ({len(required_methods)} 个)")
        return True

def test_api_connection():
    """测试 API 连接（如果配置了密钥）"""
    print("\n" + "="*70)
    print("测试 4: API 连接测试")
    print("="*70)
    
    # 检查是否配置了 API 密钥
    from dotenv import load_dotenv
    load_dotenv()
    
    api_key = os.getenv('OKX_API_KEY', '').strip()
    secret = os.getenv('OKX_SECRET', '').strip()
    password = os.getenv('OKX_PASSWORD', '').strip()
    
    if not all([api_key, secret, password]):
        print("⚠️  跳过 API 连接测试（未配置 API 密钥）")
        print("   如需测试 API 连接，请运行: python scripts/test_okx_api.py")
        return True
    
    # 运行完整的 API 测试
    print("运行完整的 API 连接测试...")
    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, 'scripts/test_okx_api.py'],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore'
        )
        
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
        
        return result.returncode == 0
    except Exception as e:
        print(f"❌ 运行测试脚本失败: {e}")
        print("   请手动运行: python scripts/test_okx_api.py")
        return False

def main():
    """主函数"""
    print("\n" + "="*70)
    print("本地测试 - OKXClient 类")
    print("="*70)
    print()
    
    results = []
    
    # 测试 1: 导入
    success, _, _, _ = test_okx_client_import()
    results.append(("导入 OKXClient", success))
    
    # 测试 2: 初始化
    success, _ = test_okx_client_init()
    results.append(("初始化 OKXClient", success))
    
    # 测试 3: 方法检查
    success = test_okx_client_methods()
    results.append(("方法检查", success))
    
    # 测试 4: API 连接（可选）
    success = test_api_connection()
    results.append(("API 连接测试", success))
    
    # 汇总结果
    print("\n" + "="*70)
    print("📊 测试结果汇总")
    print("="*70)
    for name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{name}: {status}")
    
    success_count = sum(1 for _, success in results if success)
    total_count = len(results)
    print(f"\n总计: {success_count}/{total_count} 测试通过")
    print("="*70)
    
    if success_count == total_count:
        print("\n🎉 所有测试通过！代码可以部署到服务器。")
        return 0
    else:
        print("\n⚠️  部分测试失败，请检查代码。")
        return 1

if __name__ == "__main__":
    sys.exit(main())

