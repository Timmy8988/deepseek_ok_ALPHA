#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OKX API 连接测试脚本
用于诊断 API 连接和签名问题
"""

import os
import sys

# 设置 Windows 控制台编码
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import json
import hmac
import hashlib
import base64
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv

# 加载环境变量
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, '.env'))

class OKXAPITester:
    def __init__(self):
        self.BASE_URL = "https://www.okx.com"
        self.API_VERSION = "v5"
        
        # 从环境变量读取配置
        self.api_key = os.getenv('OKX_API_KEY', '').strip()
        self.secret = os.getenv('OKX_SECRET', '').strip()
        self.password = os.getenv('OKX_PASSWORD', '').strip()
        self.sub_account = os.getenv('OKX_SUBACCOUNT', '').strip() or None
        
        # 检查配置
        if not all([self.api_key, self.secret, self.password]):
            print("❌ 错误：缺少必要的 API 配置")
            print("请确保 .env 文件中包含以下配置：")
            print("  OKX_API_KEY=your_api_key")
            print("  OKX_SECRET=your_secret_key")
            print("  OKX_PASSWORD=your_passphrase")
            sys.exit(1)
        
        print("="*70)
        print("OKX API 连接测试工具")
        print("="*70)
        print(f"API Key: {self.api_key[:8]}...{self.api_key[-4:] if len(self.api_key) > 12 else '***'}")
        print(f"Secret: {self.secret[:8]}...{self.secret[-4:] if len(self.secret) > 12 else '***'}")
        print(f"Password 长度: {len(self.password)} 字符")
        if self.sub_account:
            print(f"子账户: {self.sub_account}")
        print("="*70)
        print()
    
    def _generate_timestamp(self):
        """生成时间戳"""
        now = datetime.now(timezone.utc)
        timestamp = now.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
        return timestamp
    
    def _sign(self, timestamp: str, method: str, request_path: str, body: str = '', use_encrypted_passphrase: bool = False):
        """生成签名"""
        message = timestamp + method.upper() + request_path + body
        
        # 清理 secret
        secret_bytes = bytes(self.secret.strip(), encoding='utf8')
        message_bytes = bytes(message, encoding='utf8')
        
        # 生成签名
        mac = hmac.new(secret_bytes, message_bytes, digestmod=hashlib.sha256)
        signature = base64.b64encode(mac.digest()).decode()
        
        return signature, message
    
    def _get_headers(self, method: str, request_path: str, body: str = '', use_encrypted_passphrase: bool = False):
        """获取请求头"""
        timestamp = self._generate_timestamp()
        signature, sign_message = self._sign(timestamp, method, request_path, body, use_encrypted_passphrase)
        
        # 处理 passphrase
        if use_encrypted_passphrase:
            # 如果使用加密 passphrase，需要用 secret 对 password 进行 HMAC-SHA256 签名
            passphrase_signature = base64.b64encode(
                hmac.new(
                    bytes(self.secret.strip(), encoding='utf8'),
                    bytes(self.password.strip(), encoding='utf8'),
                    digestmod=hashlib.sha256
                ).digest()
            ).decode()
            passphrase_value = passphrase_signature
        else:
            # 明文 passphrase（大多数情况）
            passphrase_value = self.password.strip()
        
        headers = {
            'OK-ACCESS-KEY': self.api_key.strip(),
            'OK-ACCESS-SIGN': signature,
            'OK-ACCESS-TIMESTAMP': timestamp,
            'OK-ACCESS-PASSPHRASE': passphrase_value,
            'Content-Type': 'application/json'
        }
        
        if self.sub_account:
            headers['OK-ACCESS-SUBACCOUNT'] = self.sub_account
        
        return headers, timestamp, signature, sign_message, passphrase_value
    
    def _request(self, method: str, endpoint: str, params: dict = None, body: dict = None, use_encrypted_passphrase: bool = False, debug: bool = True):
        """发送请求"""
        url = f"{self.BASE_URL}/api/{self.API_VERSION}/{endpoint}"
        
        # 根据 OKX API v5 官方文档：
        # GET 请求的查询参数应该包含在 requestPath 中，而不是作为 body
        # Example: '/api/v5/account/balance?ccy=BTC'
        if method.upper() == 'GET':
            request_path = f"/api/{self.API_VERSION}/{endpoint}"
            if params and len(params) > 0:
                # 过滤 None 值和空字符串
                filtered_params = [(k, str(v)) for k, v in params.items() if v is not None and v != '']
                if filtered_params:
                    # 按 key 字母顺序排序
                    sorted_params = sorted(filtered_params, key=lambda x: x[0])
                    # 构建查询字符串：key=value&key2=value2
                    query_string = '&'.join([f"{k}={v}" for k, v in sorted_params])
                    # 将查询参数附加到 requestPath
                    request_path = f"{request_path}?{query_string}"
                    body_str = ''  # GET 请求的 body 为空
                else:
                    body_str = ''
            else:
                body_str = ''  # GET 请求的 body 为空
        elif method.upper() == 'POST':
            request_path = f"/api/{self.API_VERSION}/{endpoint}"
            # POST 请求：使用 JSON body（确保紧凑格式，无空格，键按字母顺序排序，用于签名）
            # 重要：签名必须基于实际发送的 body 字符串，所以使用 data=body_str 而不是 json=body
            if body:
                # 按字母顺序排序键，确保签名一致性
                sorted_body = dict(sorted(body.items()))
                body_str = json.dumps(sorted_body, separators=(',', ':'))
            else:
                body_str = ''
        else:
            raise ValueError(f"不支持的 HTTP 方法: {method}")
        
        # 获取请求头
        headers, timestamp, signature, sign_message, passphrase_value = self._get_headers(
            method, request_path, body_str, use_encrypted_passphrase
        )
        
        # 打印调试信息
        if debug:
            print("\n" + "="*70)
            print("📋 请求详情")
            print("="*70)
            print(f"方法: {method.upper()}")
            print(f"URL: {url}")
            print(f"请求路径: {request_path}")
            if params:
                print(f"查询参数: {params}")
            if body:
                print(f"请求体: {json.dumps(body, indent=2)}")
            print(f"签名消息 (用于签名): {sign_message}")
            print(f"时间戳: {timestamp}")
            print(f"签名: {signature[:32]}...")
            print(f"Passphrase 类型: {'加密' if use_encrypted_passphrase else '明文'}")
            print(f"Passphrase 值: {passphrase_value[:16]}...")
            print("="*70)
        
        # 发送请求
        try:
            if method.upper() == 'GET':
                response = requests.get(url, params=params, headers=headers, timeout=10)
            elif method.upper() == 'POST':
                # 使用 data=body_str 而不是 json=body，确保发送的字符串与签名时使用的字符串完全一致
                response = requests.post(url, data=body_str, headers=headers, timeout=10)
            
            result = response.json()
            
            if debug:
                print(f"\n📥 响应状态码: {response.status_code}")
                print(f"📥 响应内容: {json.dumps(result, indent=2, ensure_ascii=False)}")
            
            return result, response.status_code
            
        except requests.exceptions.RequestException as e:
            if debug:
                print(f"\n❌ 请求异常: {e}")
            raise
        except json.JSONDecodeError as e:
            if debug:
                print(f"\n❌ JSON 解析失败: {e}")
                print(f"原始响应: {response.text}")
            raise
    
    def test_public_api(self):
        """测试公开 API（无需签名）"""
        print("\n" + "="*70)
        print("🧪 测试 1: 公开 API（获取服务器时间）")
        print("="*70)
        
        try:
            url = f"{self.BASE_URL}/api/{self.API_VERSION}/public/time"
            response = requests.get(url, timeout=10)
            result = response.json()
            
            if result.get('code') == '0':
                print("✅ 公开 API 连接成功")
                print(f"服务器时间: {result.get('data', [{}])[0].get('ts', 'N/A')}")
                return True
            else:
                print(f"❌ 公开 API 失败: {result}")
                return False
        except Exception as e:
            print(f"❌ 公开 API 异常: {e}")
            return False
    
    def test_account_balance(self, use_encrypted_passphrase: bool = False):
        """测试获取账户余额"""
        print("\n" + "="*70)
        print(f"🧪 测试 2: 获取账户余额 (Passphrase: {'加密' if use_encrypted_passphrase else '明文'})")
        print("="*70)
        
        try:
            result, status_code = self._request(
                'GET',
                'account/balance',
                params={'ccy': 'USDT'},
                use_encrypted_passphrase=use_encrypted_passphrase,
                debug=True
            )
            
            if result.get('code') == '0':
                print("\n✅ 账户余额获取成功")
                data = result.get('data', [])
                if data:
                    details = data[0].get('details', [])
                    for detail in details:
                        if detail.get('ccy') == 'USDT':
                            print(f"  可用余额: {detail.get('availBal', '0')} USDT")
                            print(f"  总余额: {detail.get('eq', '0')} USDT")
                return True
            else:
                error_code = result.get('code', '')
                error_msg = result.get('msg', '未知错误')
                print(f"\n❌ 获取账户余额失败")
                print(f"错误代码: {error_code}")
                print(f"错误信息: {error_msg}")
                
                if error_code == '50113':
                    print("\n💡 诊断建议:")
                    print("  1. 检查签名算法是否正确")
                    print("  2. 确认 passphrase 是否需要加密（创建 API 密钥时的选项）")
                    print("  3. 检查 API Key、Secret、Password 是否正确")
                elif error_code == '50111':
                    print("\n💡 诊断建议:")
                    print("  1. 检查 API Key 是否正确")
                    print("  2. 确认 API Key 是否被禁用")
                    print("  3. 检查 IP 地址是否在白名单中")
                
                return False
                
        except Exception as e:
            print(f"\n❌ 测试异常: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def test_account_positions(self, use_encrypted_passphrase: bool = False):
        """测试获取持仓信息"""
        print("\n" + "="*70)
        print(f"🧪 测试 3: 获取持仓信息 (Passphrase: {'加密' if use_encrypted_passphrase else '明文'})")
        print("="*70)
        
        try:
            result, status_code = self._request(
                'GET',
                'account/positions',
                params={},
                use_encrypted_passphrase=use_encrypted_passphrase,
                debug=True
            )
            
            if result.get('code') == '0':
                print("\n✅ 持仓信息获取成功")
                data = result.get('data', [])
                print(f"持仓数量: {len(data)}")
                return True
            else:
                error_code = result.get('code', '')
                error_msg = result.get('msg', '未知错误')
                print(f"\n❌ 获取持仓信息失败")
                print(f"错误代码: {error_code}")
                print(f"错误信息: {error_msg}")
                return False
                
        except Exception as e:
            print(f"\n❌ 测试异常: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def run_all_tests(self):
        """运行所有测试"""
        results = []
        
        # 测试 1: 公开 API
        results.append(("公开API", self.test_public_api()))
        
        # 测试 2: 账户余额（明文 passphrase）
        results.append(("账户余额(明文)", self.test_account_balance(use_encrypted_passphrase=False)))
        
        # 如果明文 passphrase 失败，尝试加密 passphrase
        if not results[-1][1]:
            print("\n" + "⚠️" * 35)
            print("⚠️  明文 passphrase 失败，尝试加密 passphrase...")
            print("⚠️" * 35)
            results.append(("账户余额(加密)", self.test_account_balance(use_encrypted_passphrase=True)))
        
        # 测试 3: 持仓信息（使用成功的 passphrase 方式）
        if results[-1][1]:
            # 如果最后一个测试成功，使用相同的方式
            use_encrypted = "加密" in results[-1][0]
            results.append(("持仓信息", self.test_account_positions(use_encrypted_passphrase=use_encrypted)))
        
        # 汇总结果
        print("\n" + "="*70)
        print("📊 测试结果汇总")
        print("="*70)
        for name, success in results:
            status = "✅ 通过" if success else "❌ 失败"
            print(f"{name}: {status}")
        
        success_count = sum(1 for _, success in results if success)
        print(f"\n总计: {success_count}/{len(results)} 测试通过")
        print("="*70)
        
        return success_count == len(results)


def main():
    """主函数"""
    try:
        tester = OKXAPITester()
        success = tester.run_all_tests()
        
        if success:
            print("\n🎉 所有测试通过！API 配置正确。")
            sys.exit(0)
        else:
            print("\n⚠️  部分测试失败，请检查 API 配置。")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n⚠️  测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 测试过程中发生异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
