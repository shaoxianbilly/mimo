#!/usr/bin/env python3
"""
API Key Validator - 快速甄别API KEY有效性

URL列表：
- SGP（新加坡）: https://token-plan-sgp.xiaomimimo.com/v1
- CN（国内）: https://token-plan-cn.xiaomimimo.com/v1

模型: mimo-v2.5-pro

功能：
- 自动清洗杂乱文本，提取API Key
- 支持Base64解码（单次/双重）
- 支持删除混淆（中文干扰字符）
- 自动尝试所有URL，识别区域
- 限流检测 + 自动/手动重测
- 状态管理：可用/不可用/使用中/限流中
"""

import requests
import json
import base64
import re
import time
import threading
from dataclasses import dataclass, asdict
from typing import Optional, List, Tuple
from datetime import datetime
from pathlib import Path

# 存储文件路径
DATA_FILE = Path(__file__).parent / "api_keys.json"

# 默认URL列表
DEFAULT_URLS = {
    "sgp": "https://token-plan-sgp.xiaomimimo.com/v1",
    "cn": "https://token-plan-cn.xiaomimimo.com/v1",
    "sgp-anthropic": "https://token-plan-sgp.xiaomimimo.com/anthropic",
    "cn-anthropic": "https://token-plan-cn.xiaomimimo.com/anthropic",
}

# 默认模型
DEFAULT_MODEL = "mimo-v2.5-pro"

# OmniRoute配置
DEFAULT_OMNIROUTE_URL = "http://localhost:20128"
DEFAULT_OMNIROUTE_API_KEY = ""  # OmniRoute的管理API Key

# 配置文件路径
CONFIG_FILE = Path(__file__).parent / "config.json"


@dataclass
class ApiKeyInfo:
    """API Key信息"""
    key: str
    region: str = "unknown"       # "sgp", "cn", "unknown"
    status: str = "unavailable"   # "available", "unavailable", "in_use", "rate_limited"
    url: str = ""
    tested_at: str = ""
    added_at: str = ""            # 加入时间
    latency: int = 0              # 延迟(ms)
    error: Optional[str] = None
    omniroute_id: str = ""        # OmniRoute中的连接ID
    score: int = 0                # 推荐分数(0-100)
    test_count: int = 0           # 测试次数
    rate_limit_count: int = 0     # 限速次数
    source: str = "local"         # 来源: local / omniroute


class ApiKeyValidator:
    """API Key验证器"""
    
    def __init__(self, model: str = DEFAULT_MODEL):
        self.model = model
        self.urls = DEFAULT_URLS.copy()
        self.keys = self._load_keys()
        self._auto_thread = None
        self._auto_stop = threading.Event()
        self.config = self._load_config()
    
    def _load_keys(self):
        """从文件加载已保存的keys"""
        if DATA_FILE.exists():
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
                result = {}
                for k, v in data.items():
                    result[k] = ApiKeyInfo(
                        key=v.get('key', k),
                        region=v.get('region', 'unknown'),
                        status=v.get('status', 'unavailable'),
                        url=v.get('url', ''),
                        tested_at=v.get('tested_at', ''),
                        added_at=v.get('added_at', ''),
                        latency=v.get('latency', 0),
                        error=v.get('error'),
                        omniroute_id=v.get('omniroute_id', ''),
                        score=v.get('score', 0),
                        test_count=v.get('test_count', 0),
                        rate_limit_count=v.get('rate_limit_count', 0),
                        source=v.get('source', 'local')
                    )
                return result
        return {}
    
    def _calculate_score(self, info: ApiKeyInfo) -> int:
        """
        计算Key的推荐分数(0-100)
        
        评分规则：
        - 基础分：50分
        - 状态分：available +30, rate_limited +10, unavailable 0
        - 延迟分：延迟越低越好，最高+20分
        - 限速扣分：每次限速扣5分，最低0分
        - 测试次数加分：测试越多越可靠，最高+10分
        """
        score = 50  # 基础分
        
        # 状态分
        if info.status == "available":
            score += 30
        elif info.status == "rate_limited":
            score += 10
        # unavailable 不加分
        
        # 延迟分（延迟越低越好）
        if info.latency > 0:
            if info.latency < 500:
                score += 20
            elif info.latency < 1000:
                score += 15
            elif info.latency < 2000:
                score += 10
            elif info.latency < 3000:
                score += 5
        
        # 限速扣分
        score -= info.rate_limit_count * 5
        
        # 测试次数加分（测试越多越可靠）
        if info.test_count >= 10:
            score += 10
        elif info.test_count >= 5:
            score += 7
        elif info.test_count >= 3:
            score += 5
        elif info.test_count >= 1:
            score += 3
        
        # 确保分数不为负数（无上限）
        return max(0, score)
    
    def _save_keys(self):
        """保存keys到文件"""
        with open(DATA_FILE, 'w') as f:
            json.dump({k: asdict(v) for k, v in self.keys.items()}, f, indent=2, ensure_ascii=False)
    
    def _load_config(self):
        """加载配置文件"""
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        return {
            'omniroute_url': DEFAULT_OMNIROUTE_URL,
            'omniroute_api_key': DEFAULT_OMNIROUTE_API_KEY,
            'last_update_check': ''
        }
    
    def _save_config(self):
        """保存配置文件"""
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)
    
    def _decode_base64(self, text: str) -> str:
        """尝试Base64解码（支持双重编码）"""
        try:
            if re.match(r'^[A-Za-z0-9+/]*={0,2}$', text) and len(text) > 16:
                decoded = base64.b64decode(text).decode('utf-8')
                if re.match(r'^[A-Za-z0-9+/]*={0,2}$', decoded) and len(decoded) > 16:
                    decoded = base64.b64decode(decoded).decode('utf-8')
                return decoded
        except Exception:
            pass
        return text
    
    def clean_text(self, text: str) -> Tuple[List[str], List[str]]:
        """
        从杂乱文本中提取和清洗API Key
        
        支持：
        - 直接的key：tp-xxx, sk-xxx
        - Base64编码的key（单次/双重）
        - 带中文干扰字符的key（如：tp-xxx删xxx）
        - 包含URL和key的混合文本
        - 删除混淆（自动移除非字母数字字符）
        
        返回: (keys列表, urls列表)
        """
        keys = []
        
        # 0. 提取URL
        urls = re.findall(r'https?://[^\s"\'<>]+', text)
        
        # 1. 按行分割，每行单独处理
        lines = text.split('\n')
        
        for line in lines:
            # 提取Base64编码的字符串并尝试解码
            b64_strings = re.findall(r'[A-Za-z0-9+/]{20,}={0,2}', line)
            for b64 in b64_strings:
                decoded = self._decode_base64(b64)
                if decoded != b64 and ('tp-' in decoded or 'sk-' in decoded):
                    found = re.findall(r'(?:tp|sk)-[A-Za-z0-9]{20,60}', decoded)
                    keys.extend(found)
            
            # 2. 直接提取 tp-xxx 或 sk-xxx（限制最大60字符，避免拼接）
            direct_keys = re.findall(r'(?:tp|sk)-[A-Za-z0-9]{20,60}', line)
            keys.extend(direct_keys)
            
            # 3. 移除中文干扰字符（删除混淆），拼接后提取
            no_chinese = re.sub(r'[\u4e00-\u9fff]+', '', line)
            no_chinese_keys = re.findall(r'(?:tp|sk)-[A-Za-z0-9]{20,60}', no_chinese)
            keys.extend(no_chinese_keys)
        
        # 去重保持顺序
        seen = set()
        unique_keys = []
        for k in keys:
            if k not in seen:
                seen.add(k)
                unique_keys.append(k)
        
        return unique_keys, urls
    
    def _test_key(self, api_key: str, url: str) -> Tuple[bool, str, str, int]:
        """
        测试单个key和url组合
        返回: (是否有效, 状态, 错误信息, 延迟ms)
        """
        import time as time_mod
        try:
            # 判断是OpenAI格式还是Anthropic格式
            is_anthropic = '/anthropic' in url
            
            if is_anthropic:
                headers = {
                    "x-api-key": api_key,
                    "Content-Type": "application/json",
                    "anthropic-version": "2023-06-01"
                }
                payload = {
                    "model": self.model,
                    "messages": [{"role": "user", "content": "Hi"}],
                    "max_tokens": 5
                }
                endpoint = f"{url}/v1/messages"
            else:
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": self.model,
                    "messages": [{"role": "user", "content": "Hi"}],
                    "max_tokens": 5
                }
                endpoint = f"{url}/chat/completions"
            
            start_time = time_mod.time()
            resp = requests.post(
                endpoint,
                headers=headers,
                json=payload,
                timeout=10
            )
            latency = int((time_mod.time() - start_time) * 1000)
            
            if resp.status_code == 200:
                return True, "available", "", latency
            elif resp.status_code == 429:
                return True, "rate_limited", "Too many requests", latency
            elif resp.status_code == 401:
                return False, "unavailable", "Invalid API Key", latency
            else:
                return False, "unavailable", f"HTTP {resp.status_code}", latency
                
        except Exception as e:
            return False, "unavailable", str(e), 0
    
    def validate(self, key: str) -> ApiKeyInfo:
        """
        验证单个key，自动尝试所有URL
        支持Base64编码的key
        """
        decoded_key = self._decode_base64(key.strip())
        
        # 检查是否已存在，保留原始加入时间和统计数据
        existing = self.keys.get(decoded_key)
        added_at = existing.added_at if existing else datetime.now().isoformat()
        test_count = (existing.test_count + 1) if existing else 1
        rate_limit_count = existing.rate_limit_count if existing else 0
        
        for region, url in self.urls.items():
            is_valid, status, error, latency = self._test_key(decoded_key, url)
            if is_valid:
                # 如果是限速，增加限速计数
                if status == "rate_limited":
                    rate_limit_count += 1
                
                info = ApiKeyInfo(
                    key=decoded_key,
                    region=region,
                    status=status,
                    url=url,
                    tested_at=datetime.now().isoformat(),
                    added_at=added_at,
                    latency=latency,
                    error=error if error else None,
                    test_count=test_count,
                    rate_limit_count=rate_limit_count
                )
                # 计算评分
                info.score = self._calculate_score(info)
                self.keys[decoded_key] = info
                self._save_keys()
                return info
        
        info = ApiKeyInfo(
            key=decoded_key,
            region="unknown",
            status="unavailable",
            url="",
            tested_at=datetime.now().isoformat(),
            added_at=added_at,
            latency=0,
            error="All URLs failed",
            test_count=test_count,
            rate_limit_count=rate_limit_count
        )
        # 计算评分
        info.score = self._calculate_score(info)
        self.keys[decoded_key] = info
        self._save_keys()
        return info
    
    def paste_validate(self, text: str) -> List[ApiKeyInfo]:
        """
        粘贴杂乱文本，自动清洗提取key并验证
        这是最常用的入口
        """
        keys, urls = self.clean_text(text)
        
        if not keys:
            print("未从文本中提取到API Key")
            return []
        
        print(f"提取到 {len(keys)} 个Key，开始验证...")
        
        results = []
        for key in keys:
            result = self.validate(key)
            emoji = {"available": "✅", "unavailable": "❌", "rate_limited": "⚠️", "in_use": "🔄"}.get(result.status, "❓")
            region_name = {"sgp": "新加坡", "cn": "国内"}.get(result.region, "未知")
            print(f"  {emoji} {key[:30]}... → {region_name} ({result.status})")
            results.append(result)
        
        return results
    
    def retest(self, key: str = None, test_all: bool = False) -> List[ApiKeyInfo]:
        """
        重新测试
        key=None 且 test_all=False 时重测所有限流中的key
        key=None 且 test_all=True 时重测所有key
        """
        if key:
            decoded = self._decode_base64(key.strip())
            if decoded in self.keys:
                print(f"重测: {decoded[:30]}...")
                return [self.validate(decoded)]
            else:
                print("Key不存在于列表中")
                return []
        
        # 确定要测试的keys
        if test_all:
            # 测试所有key
            keys_to_test = list(self.keys.keys())
            print(f"重测所有 {len(keys_to_test)} 个key...")
        else:
            # 只测试限流中的key
            keys_to_test = [k for k, v in self.keys.items() if v.status == "rate_limited"]
            if not keys_to_test:
                print("没有限流中的key需要重测")
                return []
            print(f"重测 {len(keys_to_test)} 个限流中的key...")
        
        results = []
        for k in keys_to_test:
            result = self.validate(k)
            emoji = {"available": "✅", "unavailable": "❌", "rate_limited": "⚠️"}.get(result.status, "❓")
            print(f"  {emoji} {k[:30]}... → {result.status}")
            results.append(result)
        return results
    
    def auto_retest(self, interval: int = 180):
        """
        启动自动重测（后台线程，定期测试所有key）
        interval: 基础间隔秒数，默认180秒（3分钟）
        实际间隔会在120-300秒（2-5分钟）之间随机
        """
        import random
        
        if self._auto_thread and self._auto_thread.is_alive():
            print("自动重测已在运行中，先停止再启动")
            return
        
        self._auto_stop.clear()
        
        def _loop():
            while not self._auto_stop.is_set():
                # 测试所有key（不只是限流的）
                all_keys = list(self.keys.keys())
                if all_keys:
                    print(f"\n[自动重测] 测试 {len(all_keys)} 个key...")
                    for k in all_keys:
                        if self._auto_stop.is_set():
                            break
                        result = self.validate(k)
                        emoji = {"available": "✅", "rate_limited": "⚠️", "unavailable": "❌"}.get(result.status, "❓")
                        print(f"  {emoji} {k[:30]}... → {result.status}")
                else:
                    print(f"\n[自动重测] 无key需要测试")
                
                # 随机间隔 120-300秒（2-5分钟）
                random_interval = random.randint(120, 300)
                print(f"[自动重测] 下次测试在 {random_interval} 秒后")
                self._auto_stop.wait(random_interval)
        
        self._auto_thread = threading.Thread(target=_loop, daemon=True)
        self._auto_thread.start()
        print(f"自动重测已启动（每{interval}秒）")
    
    def stop_auto_retest(self):
        """停止自动重测"""
        self._auto_stop.set()
        if self._auto_thread:
            self._auto_thread.join(timeout=5)
        print("自动重测已停止")
    
    def set_status(self, key: str, status: str):
        """手动设置key状态"""
        if key in self.keys:
            self.keys[key].status = status
            self._save_keys()
            print(f"已更新: {key[:30]}... → {status}")
        else:
            print("Key不存在")
    
    def list_keys(self):
        """列出所有keys及状态"""
        if not self.keys:
            print("暂无已验证的keys")
            return
        
        print("\n" + "="*60)
        print("API Keys 列表")
        print("="*60)
        
        by_status = {"available": [], "rate_limited": [], "in_use": [], "unavailable": []}
        for key, info in self.keys.items():
            by_status[info.status].append((key, info))
        
        status_names = {
            "available": "✅ 可用",
            "rate_limited": "⚠️ 有效（限流中）",
            "in_use": "🔄 使用中",
            "unavailable": "❌ 不可用"
        }
        
        for status, items in by_status.items():
            if items:
                print(f"\n{status_names[status]}:")
                for key, info in items:
                    region_name = {"sgp": "新加坡", "cn": "国内"}.get(info.region, "未知")
                    print(f"  - {key[:40]}... [{region_name}] {info.url}")
        
        print("\n" + "="*60)
        print(f"总计: {len(self.keys)} 个Key")
        print("="*60)
    
    def get_usable_keys(self) -> List[ApiKeyInfo]:
        """获取可用的keys（包括限流中的）"""
        return [k for k in self.keys.values() if k.status in ("available", "rate_limited")]
    
    def delete_key(self, key: str) -> bool:
        """删除指定key"""
        if key in self.keys:
            del self.keys[key]
            self._save_keys()
            return True
        return False
    
    def clear_all(self) -> int:
        """清空所有key"""
        count = len(self.keys)
        self.keys.clear()
        self._save_keys()
        return count
    
    def clear_unavailable(self) -> int:
        """清除所有不可用的key"""
        to_delete = [k for k, v in self.keys.items() if v.status == "unavailable"]
        for k in to_delete:
            del self.keys[k]
        if to_delete:
            self._save_keys()
        return len(to_delete)
    
    def export_to_omniroute(self, omniroute_url: str = DEFAULT_OMNIROUTE_URL, 
                            omniroute_api_key: str = DEFAULT_OMNIROUTE_API_KEY) -> Tuple[int, List[str]]:
        """
        将可用的Key导出到OmniRoute（只导出MIMO的Key）
        每个Key创建两个配置：OpenAI兼容 + Anthropic兼容
        
        去重策略：检查OmniRoute中是否已存在相同的Key，跳过重复
        
        返回: (成功数, 错误列表, 跳过数)
        """
        # 只导出可用的Key
        available_keys = [k for k, v in self.keys.items() if v.status == "available"]
        
        if not available_keys:
            return 0, ["没有可用的Key"], 0
        
        # 获取OmniRoute中已存在的MIMO Key
        existing_keys = set()
        try:
            headers = {"Content-Type": "application/json"}
            if omniroute_api_key:
                headers["Authorization"] = f"Bearer {omniroute_api_key}"
            
            resp = requests.get(
                f"{omniroute_url}/api/providers",
                headers=headers,
                timeout=10
            )
            
            if resp.status_code == 200:
                data = resp.json()
                for conn in data.get('connections', []):
                    # 只检查MIMO provider
                    if conn.get('provider') == 'xiaomi-mimo':
                        api_key = conn.get('apiKey', '')
                        if api_key:
                            existing_keys.add(api_key[:20])
        except Exception as e:
            return 0, [f"无法连接OmniRoute: {str(e)}"], 0
        
        success_count = 0
        skip_count = 0
        errors = []
        
        for key in available_keys:
            info = self.keys[key]
            
            # 检查是否已存在（用前20位匹配）
            if key[:20] in existing_keys:
                skip_count += 1
                continue
            
            # 确定URL基础路径
            if 'anthropic' in info.url:
                base_url = info.url.replace('/anthropic', '')
            elif '/v1' in info.url:
                base_url = info.url.replace('/v1', '')
            else:
                base_url = info.url.rstrip('/')
            
            # 区域名
            region_name = {"sgp": "SGP", "cn": "CN"}.get(info.region, "Unknown")
            
            # 创建两个配置：OpenAI兼容 + Anthropic兼容
            configs = [
                {
                    "url": f"{base_url}/v1",
                    "suffix": "OpenAI",
                    "provider": "xiaomi-mimo"
                },
                {
                    "url": f"{base_url}/anthropic",
                    "suffix": "Anthropic",
                    "provider": "xiaomi-mimo"
                }
            ]
            
            for config in configs:
                try:
                    headers = {"Content-Type": "application/json"}
                    if omniroute_api_key:
                        headers["Authorization"] = f"Bearer {omniroute_api_key}"
                    
                    name = f"MIMO-{region_name}-{config['suffix']}-{key[:8]}"
                    
                    payload = {
                        "provider": config["provider"],
                        "apiKey": key,
                        "name": name,
                        "priority": 1,
                        "providerSpecificData": {
                            "baseUrl": config["url"]
                        }
                    }
                    
                    resp = requests.post(
                        f"{omniroute_url}/api/providers",
                        headers=headers,
                        json=payload,
                        timeout=10
                    )
                    
                    if resp.status_code in (200, 201):
                        success_count += 1
                    else:
                        errors.append(f"{name}: HTTP {resp.status_code}")
                        
                except Exception as e:
                    errors.append(f"{key[:20]}...: {str(e)}")
        
        return success_count, errors, skip_count
    
    def import_from_omniroute(self, omniroute_url: str = DEFAULT_OMNIROUTE_URL, 
                              omniroute_api_key: str = DEFAULT_OMNIROUTE_API_KEY) -> Tuple[int, List[str]]:
        """
        从OmniRoute导入MIMO的Key到本地
        
        返回: (导入数, 错误列表)
        """
        try:
            headers = {"Content-Type": "application/json"}
            if omniroute_api_key:
                headers["Authorization"] = f"Bearer {omniroute_api_key}"
            
            resp = requests.get(
                f"{omniroute_url}/api/providers",
                headers=headers,
                timeout=10
            )
            
            if resp.status_code != 200:
                return 0, [f"无法连接OmniRoute: HTTP {resp.status_code}"]
            
            connections = resp.json().get('connections', [])
            
            # 只筛选MIMO provider
            mimo_connections = [c for c in connections if c.get('provider') == 'xiaomi-mimo']
            
            if not mimo_connections:
                return 0, ["OmniRoute中没有MIMO配置"]
            
            imported_count = 0
            errors = []
            
            for conn in mimo_connections:
                api_key = conn.get('apiKey', '')
                conn_id = conn.get('id', '')
                conn_name = conn.get('name', '')
                psd = conn.get('providerSpecificData', {})
                base_url = psd.get('baseUrl', '')
                
                if not api_key:
                    continue
                
                # 检查本地是否已存在
                if api_key in self.keys:
                    # 更新omniroute_id
                    self.keys[api_key].omniroute_id = conn_id
                    continue
                
                # 确定区域
                region = "unknown"
                if 'sgp' in base_url.lower():
                    region = "sgp"
                elif 'cn' in base_url.lower():
                    region = "cn"
                
                # 创建新的KeyInfo
                info = ApiKeyInfo(
                    key=api_key,
                    region=region,
                    status="unknown",  # 需要测试后确定
                    url=base_url,
                    added_at=datetime.now().isoformat(),
                    omniroute_id=conn_id,
                    source="omniroute"
                )
                self.keys[api_key] = info
                imported_count += 1
            
            if imported_count > 0:
                self._save_keys()
            
            return imported_count, errors
            
        except Exception as e:
            return 0, [str(e)]


def main():
    """交互式命令行"""
    validator = ApiKeyValidator()
    
    print("\n" + "="*60)
    print("API Key Validator")
    print("="*60)
    print("URL列表:")
    for region, url in validator.urls.items():
        region_name = {"sgp": "新加坡", "cn": "国内"}.get(region, region)
        print(f"  - {region_name}: {url}")
    print(f"模型: {validator.model}")
    print("\n命令:")
    print("  <粘贴任意文本>   - 自动提取key并验证")
    print("  retest [key]     - 手动重测（限流检测）")
    print("  auto [秒数]      - 启动自动重测（默认60秒）")
    print("  stop             - 停止自动重测")
    print("  list             - 查看所有key")
    print("  usable           - 只看可用key")
    print("  set <key> <status> - 手动设置状态")
    print("  urls             - 管理URL列表")
    print("  quit             - 退出")
    print("="*60)
    
    while True:
        try:
            cmd = input("\n> ").strip()
            
            if not cmd:
                continue
            
            parts = cmd.split(maxsplit=1)
            action = parts[0].lower()
            
            if action in ("quit", "q", "exit"):
                validator.stop_auto_retest()
                break
            
            elif action in ("retest", "rt"):
                if len(parts) > 1:
                    validator.retest(parts[1])
                else:
                    validator.retest()
            
            elif action in ("auto", "a"):
                interval = int(parts[1]) if len(parts) > 1 else 60
                validator.auto_retest(interval)
            
            elif action in ("stop",):
                validator.stop_auto_retest()
            
            elif action in ("list", "ls"):
                validator.list_keys()
            
            elif action in ("usable", "u"):
                usable = validator.get_usable_keys()
                print(f"\n可用keys: {len(usable)}")
                for k in usable:
                    region_name = {"sgp": "新加坡", "cn": "国内"}.get(k.region, "未知")
                    emoji = "✅" if k.status == "available" else "⚠️"
                    print(f"  {emoji} {k.key[:40]}... [{region_name}]")
            
            elif action in ("set", "s"):
                if len(parts) < 2:
                    print("用法: set <key> <status>")
                    continue
                args = parts[1].split()
                if len(args) < 2:
                    print("用法: set <key> <status>")
                    continue
                validator.set_status(args[0], args[1])
            
            elif action == "urls":
                print("\n当前URL列表:")
                for region, url in validator.urls.items():
                    region_name = {"sgp": "新加坡", "cn": "国内"}.get(region, region)
                    print(f"  - {region_name}: {url}")
                print("\n用法: add_url <url> | del_url <sgp|cn>")
            
            elif action == "add_url":
                if len(parts) < 2:
                    print("用法: add_url <url>")
                    continue
                url = parts[1].strip()
                name = f"custom_{len(validator.urls)}"
                validator.urls[name] = url
                print(f"已添加: {name} → {url}")
            
            elif action == "del_url":
                if len(parts) < 2:
                    print("用法: del_url <sgp|cn>")
                    continue
                key = parts[1].strip()
                if key in validator.urls:
                    removed = validator.urls.pop(key)
                    print(f"已删除: {removed}")
                else:
                    print("URL不存在")
            
            else:
                # 默认当作粘贴的文本处理，自动清洗提取
                keys, urls = validator.clean_text(cmd)
                if keys:
                    print(f"提取到 {len(keys)} 个Key:")
                    for k in keys:
                        print(f"  - {k}")
                    if urls:
                        print(f"提取到 {len(urls)} 个URL:")
                        for u in urls:
                            print(f"  - {u}")
                    
                    confirm = input("\n开始验证？[Y/n] ").strip().lower()
                    if confirm != 'n':
                        for k in keys:
                            validator.validate(k)
                else:
                    print("未提取到有效Key。请输入 validate <key> 或粘贴包含key的文本")
        
        except KeyboardInterrupt:
            print("\n使用 'quit' 退出")
        except Exception as e:
            print(f"错误: {e}")


if __name__ == "__main__":
    main()
