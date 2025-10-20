"""
订阅链接转换工具
支持将标准订阅链接转换为 Mihomo 配置格式
"""
import re
import base64
import json
from urllib.parse import urlparse, parse_qs, unquote
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


def parse_vless_url(url: str) -> Optional[Dict]:
    """解析 VLESS URL"""
    try:
        # vless://uuid@server:port?params#remark
        match = re.match(r'vless://([^@]+)@([^:]+):(\d+)\?(.+)#(.+)', url)
        if not match:
            return None
        
        uuid, server, port, params_str, remark = match.groups()
        params = parse_qs(params_str)
        
        proxy = {
            "type": "vless",
            "name": unquote(remark),
            "server": server,
            "port": int(port),
            "uuid": uuid,
            "udp": True
        }
        
        # 解析参数
        if params.get('type'):
            proxy['network'] = params['type'][0]
        
        if params.get('encryption'):
            proxy['encryption'] = params['encryption'][0]
        
        if params.get('security'):
            security = params['security'][0]
            if security == 'reality':
                proxy['tls'] = True
                reality_opts = {}
                
                if params.get('pbk'):
                    reality_opts['public-key'] = params['pbk'][0]
                if params.get('sid'):
                    reality_opts['short-id'] = params['sid'][0]
                if params.get('spx'):
                    reality_opts['_spider-x'] = unquote(params['spx'][0])
                
                proxy['reality-opts'] = reality_opts
                
                if params.get('sni'):
                    proxy['servername'] = params['sni'][0]
                if params.get('fp'):
                    proxy['client-fingerprint'] = params['fp'][0]
                    
            elif security == 'tls':
                proxy['tls'] = True
                if params.get('sni'):
                    proxy['servername'] = params['sni'][0]
                if params.get('fp'):
                    proxy['client-fingerprint'] = params['fp'][0]
        
        if params.get('flow'):
            proxy['flow'] = params['flow'][0]
        
        proxy['skip-cert-verify'] = False
        
        return proxy
    except Exception as e:
        logger.error(f"解析 VLESS URL 失败: {str(e)}")
        return None


def parse_ss_url(url: str) -> Optional[Dict]:
    """解析 Shadowsocks URL"""
    try:
        # ss://base64@server:port#remark 或 ss://method:password@server:port#remark
        match = re.match(r'ss://([^@]+)@([^:]+):(\d+)(?:\?[^#]*)?#(.+)', url)
        if not match:
            return None
        
        userinfo, server, port, remark = match.groups()
        
        # 尝试解码 base64
        try:
            decoded = base64.b64decode(userinfo).decode('utf-8')
            if ':' in decoded:
                cipher, password = decoded.split(':', 1)
            else:
                cipher = 'unknown'
                password = decoded
        except:
            # 不是 base64，直接解析
            if ':' in userinfo:
                cipher, password = userinfo.split(':', 1)
            else:
                return None
        
        proxy = {
            "type": "ss",
            "name": unquote(remark),
            "server": server,
            "port": int(port),
            "cipher": cipher,
            "password": password,
            "udp": True
        }
        
        return proxy
    except Exception as e:
        logger.error(f"解析 SS URL 失败: {str(e)}")
        return None


def parse_vmess_url(url: str) -> Optional[Dict]:
    """解析 VMess URL"""
    try:
        # vmess://base64
        vmess_data = url.replace('vmess://', '')
        decoded = base64.b64decode(vmess_data).decode('utf-8')
        config = json.loads(decoded)
        
        proxy = {
            "type": "vmess",
            "name": config.get('ps', 'VMess'),
            "server": config.get('add'),
            "port": int(config.get('port', 443)),
            "uuid": config.get('id'),
            "alterId": int(config.get('aid', 0)),
            "cipher": config.get('scy', 'auto'),
            "udp": True
        }
        
        # 网络类型
        net = config.get('net', 'tcp')
        proxy['network'] = net
        
        # TLS
        if config.get('tls') == 'tls':
            proxy['tls'] = True
            if config.get('sni'):
                proxy['servername'] = config['sni']
        
        # WebSocket
        if net == 'ws':
            ws_opts = {}
            if config.get('path'):
                ws_opts['path'] = config['path']
            if config.get('host'):
                ws_opts['headers'] = {'Host': config['host']}
            proxy['ws-opts'] = ws_opts
        
        # HTTP/2
        elif net == 'h2':
            h2_opts = {}
            if config.get('path'):
                h2_opts['path'] = config['path']
            if config.get('host'):
                h2_opts['host'] = [config['host']]
            proxy['h2-opts'] = h2_opts
        
        # gRPC
        elif net == 'grpc':
            grpc_opts = {}
            if config.get('path'):
                grpc_opts['grpc-service-name'] = config['path']
            proxy['grpc-opts'] = grpc_opts
        
        return proxy
    except Exception as e:
        logger.error(f"解析 VMess URL 失败: {str(e)}")
        return None


def parse_trojan_url(url: str) -> Optional[Dict]:
    """解析 Trojan URL"""
    try:
        # trojan://password@server:port?params#remark
        match = re.match(r'trojan://([^@]+)@([^:]+):(\d+)(?:\?([^#]*))?#(.+)', url)
        if not match:
            return None
        
        password, server, port, params_str, remark = match.groups()
        
        proxy = {
            "type": "trojan",
            "name": unquote(remark),
            "server": server,
            "port": int(port),
            "password": password,
            "udp": True,
            "skip-cert-verify": False
        }
        
        if params_str:
            params = parse_qs(params_str)
            
            if params.get('sni'):
                proxy['sni'] = params['sni'][0]
            if params.get('type'):
                proxy['network'] = params['type'][0]
            if params.get('security'):
                if params['security'][0] == 'tls':
                    proxy['tls'] = True
        
        return proxy
    except Exception as e:
        logger.error(f"解析 Trojan URL 失败: {str(e)}")
        return None


def parse_subscription_urls(content: str) -> List[Dict]:
    """解析订阅内容中的所有代理"""
    proxies = []
    
    # 解码 base64（如果需要）
    try:
        decoded = base64.b64decode(content).decode('utf-8')
        logger.info(f"成功解码订阅内容，长度: {len(decoded)} 字符")
    except Exception as e:
        logger.warning(f"Base64 解码失败，尝试直接使用原始内容: {str(e)}")
        decoded = content
    
    # 按行分割
    lines = decoded.strip().split('\n')
    logger.info(f"订阅内容共 {len(lines)} 行")
    
    for idx, line in enumerate(lines, 1):
        line = line.strip()
        if not line:
            continue
        
        proxy = None
        try:
            if line.startswith('vless://'):
                proxy = parse_vless_url(line)
            elif line.startswith('ss://'):
                proxy = parse_ss_url(line)
            elif line.startswith('vmess://'):
                proxy = parse_vmess_url(line)
            elif line.startswith('trojan://'):
                proxy = parse_trojan_url(line)
            else:
                logger.warning(f"第 {idx} 行: 未知的代理协议: {line[:20]}...")
        except Exception as e:
            logger.error(f"第 {idx} 行: 解析代理失败: {str(e)}")
        
        if proxy:
            proxies.append(proxy)
            logger.debug(f"第 {idx} 行: 成功解析 {proxy.get('type')} 代理: {proxy.get('name')}")
    
    logger.info(f"成功解析 {len(proxies)} 个代理配置")
    return proxies


def generate_mihomo_config(proxies: List[Dict], template: str) -> str:
    """生成 Mihomo 配置文件"""
    import yaml
    
    try:
        logger.info(f"开始生成 Mihomo 配置，代理数量: {len(proxies)}")
        
        # 解析模板
        try:
            config = yaml.safe_load(template)
            logger.info("成功解析模板 YAML")
        except yaml.YAMLError as e:
            logger.error(f"模板 YAML 解析失败: {str(e)}")
            raise ValueError(f"模板格式错误: {str(e)}")
        
        if not isinstance(config, dict):
            raise ValueError("模板必须是一个 YAML 字典")
        
        # 添加代理列表
        config['proxies'] = proxies
        logger.info(f"已添加 {len(proxies)} 个代理到配置")
        
        # 转换为 YAML 字符串
        result = yaml.dump(config, allow_unicode=True, default_flow_style=False, sort_keys=False)
        logger.info(f"成功生成 Mihomo 配置，长度: {len(result)} 字符")
        
        return result
    except Exception as e:
        logger.error(f"生成 Mihomo 配置失败: {str(e)}", exc_info=True)
        raise


def convert_to_mihomo_yaml(base64_content: str, template: str) -> str:
    """将 base64 订阅内容转换为 Mihomo YAML 格式"""
    try:
        logger.info("开始转换订阅内容为 Mihomo YAML 格式")
        
        # 解析代理列表
        proxies = parse_subscription_urls(base64_content)
        
        if not proxies:
            logger.error("没有找到有效的代理配置")
            raise ValueError("没有找到有效的代理配置")
        
        logger.info(f"成功解析 {len(proxies)} 个代理")
        
        # 生成配置
        config = generate_mihomo_config(proxies, template)
        
        if not config:
            raise ValueError("生成的配置为空")
        
        logger.info("成功转换为 Mihomo YAML 配置")
        return config
    except Exception as e:
        logger.error(f"转换 Mihomo 配置失败: {str(e)}", exc_info=True)
        raise
