"""
3XUI API客户端
用于与3XUI面板进行交互
"""
import requests
import logging
from typing import Dict, Optional, List
import base64
import json
import urllib3
from utils.cache import inbounds_cache

# 禁用SSL警告（用于自签名证书）
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


class XUIClient:
    """3XUI面板API客户端"""
    
    def __init__(self, server: str, port: int, path: str, username: str, password: str, sub_path: str, board_name: Optional[str] = None):
        self.server = server
        self.port = port
        self.path = path.strip('/')
        self.sub_path = sub_path.strip('/')  # 订阅路径
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.base_url = f"https://{server}:{port}/{path}"
        self.logged_in = False
        self.board_name = board_name  # 面板名称，用于缓存标识
        
    def login(self) -> bool:
        """
        登录到3XUI面板
        返回: 登录是否成功
        """
        login_url = f"{self.base_url}/login"
        payload = {
            "username": self.username,
            "password": self.password
        }
        
        try:
            response = self.session.post(login_url, json=payload, verify=False, timeout=10)
            data = response.json()
            
            if data.get('success'):
                self.logged_in = True
                logger.info(f"成功登录到 {self.server}:{self.port}")
                return True
            else:
                logger.error(f"登录失败 {self.server}:{self.port}: {data.get('msg')}")
                return False
        except Exception as e:
            logger.error(f"登录到 {self.server}:{self.port} 时发生错误: {str(e)}")
            return False
    
    def get_client_traffic(self, email: str) -> List[Dict]:
        """
        获取客户端流量信息（支持同一Email在多个节点中的情况）
        参数:
            email: 用户邮箱
        返回:
            包含所有匹配节点流量信息的列表
        """
        if not self.logged_in:
            if not self.login():
                return []

        # 获取所有入站节点列表
        inbounds = self.get_inbounds_list()
        if not inbounds:
            return []

        traffic_list = []
        
        # 遍历所有入站节点，查找匹配的客户端信息
        for inbound in inbounds:
            inbound_id = inbound.get('id')
            if not inbound_id:
                continue

            # 获取入站节点的详细信息
            inbound_info = self.get_inbound_info(inbound_id)
            if not inbound_info:
                continue

            # 查找匹配的客户端信息
            client_stats = inbound_info.get('clientStats', [])
            if not client_stats:  # 如果 clientStats 为 None 或空列表
                continue
                
            for client in client_stats:
                if client.get('email') == email:
                    node_name = inbound_info.get('remark', inbound_info.get('tag', ''))
                    traffic_list.append({
                        "inboundId": inbound_id,
                        "nodeName": node_name,
                        "up": client.get('up', 0),
                        "down": client.get('down', 0),
                        "total": client.get('total', 0),
                        "expiryTime": client.get('expiryTime', 0),
                        "subId": client.get('subId')
                    })

        if not traffic_list:
            logger.warning(f"未找到匹配的客户端流量信息，Email: {email}")
        
        return traffic_list
    
    def get_subscription(self, sub_id: str) -> Optional[str]:
        """
        获取订阅链接的BASE64内容
        参数:
            sub_id: 订阅ID
        返回:
            BASE64编码的订阅内容，失败返回None
        """
        sub_url = f"https://{self.server}:{self.port}/{self.sub_path}/{sub_id}"
        
        try:
            response = requests.get(sub_url, verify=False, timeout=10)
            if response.status_code == 200:
                # 返回的内容应该已经是BASE64编码的
                return response.text.strip()
            else:
                logger.warning(f"获取订阅失败 {self.server}:{self.port}, sub_id: {sub_id}")
                return None
        except Exception as e:
            logger.error(f"获取订阅时发生错误 {self.server}:{self.port}: {str(e)}")
            return None
    
    def get_inbound_info(self, inbound_id: int) -> Optional[Dict]:
        """
        获取入站节点的详细信息（从缓存的入站列表中查找）
        参数:
            inbound_id: 入站节点ID
        返回:
            包含节点信息的字典，失败返回None
        """
        # 先从缓存的入站列表中查找
        if self.board_name:
            cached_inbound = inbounds_cache.find_inbound(self.board_name, inbound_id)
            if cached_inbound:
                return cached_inbound
        
        # 如果缓存未命中，获取完整的入站列表（这会更新缓存）
        inbounds = self.get_inbounds_list()
        if inbounds:
            for inbound in inbounds:
                if inbound.get('id') == inbound_id:
                    return inbound
        
        logger.warning(f"未找到节点信息，inbound_id: {inbound_id}")
        return None
    
    def get_inbounds_list(self) -> Optional[List]:
        """
        获取所有入站节点列表（使用缓存）
        返回:
            包含所有节点信息的列表，失败返回None
        """
        # 如果有 board_name，尝试从缓存获取
        if self.board_name:
            cached_data, from_cache, cache_age = inbounds_cache.get_board(self.board_name)
            if from_cache:
                logger.debug(f"使用缓存的入站列表 {self.board_name}，缓存年龄: {cache_age}秒")
                return cached_data
        
        # 缓存未命中，从API获取
        if not self.logged_in:
            if not self.login():
                return None
        
        inbounds_url = f"{self.base_url}/panel/api/inbounds/list"
        
        # 最多重试一次（检测到 session 失效时重新登录）
        for attempt in range(2):
            try:
                response = self.session.get(inbounds_url, verify=False, timeout=10)
                
                # 检查响应状态码
                if response.status_code == 401 or response.status_code == 403:
                    # 未授权，session 可能已过期
                    logger.warning(f"Session 可能已过期 {self.server}:{self.port}，尝试重新登录...")
                    self.logged_in = False
                    if attempt == 0 and self.login():
                        continue  # 重新登录成功，重试请求
                    return None
                
                # 尝试解析 JSON
                try:
                    data = response.json()
                except ValueError as json_error:
                    # JSON 解析失败，可能是返回了 HTML（登录页面）
                    logger.warning(f"JSON 解析失败 {self.server}:{self.port}，可能 session 已过期: {str(json_error)}")
                    self.logged_in = False
                    if attempt == 0 and self.login():
                        continue  # 重新登录成功，重试请求
                    return None
                
                if data.get('success'):
                    inbounds_list = data.get('obj', [])
                    
                    # 保存到缓存
                    if self.board_name and inbounds_list:
                        inbounds_cache.set_board(self.board_name, inbounds_list)
                        logger.debug(f"已缓存入站列表 {self.board_name}，共 {len(inbounds_list)} 个节点")
                    
                    return inbounds_list
                else:
                    logger.warning(f"获取节点列表失败 {self.server}:{self.port}: {data.get('msg')}")
                    return None
                    
            except Exception as e:
                logger.error(f"获取节点列表时发生错误 {self.server}:{self.port}: {str(e)}")
                if attempt == 0:
                    # 第一次失败，尝试重新登录
                    self.logged_in = False
                    if self.login():
                        continue  # 重新登录成功，重试请求
                return None
        
        return None
    
    def update_client(self, client_uuid: str, inbound_id: int, client_data: Dict) -> bool:
        """
        更新客户端配置
        参数:
            client_uuid: 客户端UUID
            inbound_id: 入站节点ID
            client_data: 客户端完整数据
        返回:
            是否成功
        """
        if not self.logged_in:
            if not self.login():
                return False
        
        update_url = f"{self.base_url}/panel/api/inbounds/updateClient/{client_uuid}"
        
        # 准备请求数据：inbound_id 和客户端配置的 JSON 字符串
        payload = {
            'id': inbound_id,
            'settings': json.dumps({"clients": [client_data]})  # 确保 settings 是嵌套 JSON 字符串
        }
        logger.debug(f"更新客户端请求数据: {payload}")
        
        for attempt in range(2):
            try:
                response = self.session.post(update_url, json=payload, verify=False, timeout=10)
                
                if response.status_code == 401 or response.status_code == 403:
                    logger.warning(f"Session 可能已过期 {self.server}:{self.port}，尝试重新登录...")
                    self.logged_in = False
                    if attempt == 0 and self.login():
                        continue
                    return False
                
                try:
                    data = response.json()
                except ValueError as e:
                    logger.error(
                        f"更新客户端响应JSON解析失败 {self.server}:{self.port}\n"
                        f"状态码: {response.status_code}\n"
                        f"响应内容: {response.text[:500]}\n"
                        f"错误: {str(e)}"
                    )
                    return False
                
                if data.get('success'):
                    logger.info(f"成功更新客户端 {client_uuid} 在节点 {inbound_id}")
                    return True
                else:
                    logger.warning(f"更新客户端失败: {data.get('msg')}")
                    return False
                    
            except Exception as e:
                logger.error(f"更新客户端时发生错误: {str(e)}")
                if attempt == 0:
                    self.logged_in = False
                    if self.login():
                        continue
                return False
        
        return False
    
    def reset_client_traffic(self, inbound_id: int, email: str) -> bool:
        """
        重置客户端流量
        参数:
            inbound_id: 入站节点ID
            email: 客户端邮箱
        返回:
            是否成功
        """
        if not self.logged_in:
            if not self.login():
                return False
        
        reset_url = f"{self.base_url}/panel/api/inbounds/{inbound_id}/resetClientTraffic/{email}"
        
        for attempt in range(2):
            try:
                response = self.session.post(reset_url, verify=False, timeout=10)
                
                if response.status_code == 401 or response.status_code == 403:
                    logger.warning(f"Session 可能已过期 {self.server}:{self.port}，尝试重新登录...")
                    self.logged_in = False
                    if attempt == 0 and self.login():
                        continue
                    return False
                
                try:
                    data = response.json()
                except ValueError:
                    logger.error(f"重置流量响应JSON解析失败 {self.server}:{self.port}")
                    return False
                
                if data.get('success'):
                    logger.info(f"成功重置客户端流量: {email} 在节点 {inbound_id}")
                    return True
                else:
                    logger.warning(f"重置客户端流量失败: {data.get('msg')}")
                    return False
                    
            except Exception as e:
                logger.error(f"重置客户端流量时发生错误: {str(e)}")
                if attempt == 0:
                    self.logged_in = False
                    if self.login():
                        continue
                return False
        
        return False
    
    def get_new_uuid(self) -> Optional[str]:
        """
        生成新的UUID
        返回:
            UUID字符串，失败返回None
        """
        if not self.logged_in:
            if not self.login():
                return None
        
        uuid_url = f"{self.base_url}/panel/api/server/getNewUUID"
        
        for attempt in range(2):
            try:
                response = self.session.get(uuid_url, verify=False, timeout=10)
                
                if response.status_code == 401 or response.status_code == 403:
                    logger.warning(f"Session 可能已过期 {self.server}:{self.port}，尝试重新登录...")
                    self.logged_in = False
                    if attempt == 0 and self.login():
                        continue
                    return None
                
                try:
                    data = response.json()
                except ValueError:
                    logger.error(f"获取UUID响应JSON解析失败 {self.server}:{self.port}")
                    return None
                
                if data.get('success'):
                    uuid = data.get('obj', {}).get('uuid')
                    if uuid:
                        logger.debug(f"成功生成UUID: {uuid}")
                        return uuid
                    else:
                        logger.error(f"UUID响应数据格式错误")
                        return None
                else:
                    logger.warning(f"生成UUID失败: {data.get('msg')}")
                    return None
                    
            except Exception as e:
                logger.error(f"生成UUID时发生错误: {str(e)}")
                if attempt == 0:
                    self.logged_in = False
                    if self.login():
                        continue
                return None
        
        return None
    
    def get_default_client_flow(self, inbound_id: int) -> str:
        """
        获取入站节点的默认客户端flow值
        参数:
            inbound_id: 入站节点ID
        返回:
            flow值，失败返回空字符串
        """
        inbound_info = self.get_inbound_info(inbound_id)
        if not inbound_info:
            return ""
        
        try:
            settings = json.loads(inbound_info.get('settings', '{}'))
            clients = settings.get('clients', [])
            
            for client in clients:
                if client.get('email') == 'default':
                    return client.get('flow', '')
            
            # 如果没有找到default客户端，返回第一个客户端的flow
            if clients:
                return clients[0].get('flow', '')
            
        except Exception as e:
            logger.error(f"解析入站节点设置失败: {str(e)}")
        
        return ""
    
    def add_client(self, inbound_id: int, email: str) -> bool:
        """
        添加客户端到入站节点
        参数:
            inbound_id: 入站节点ID
            email: 客户端邮箱
        返回:
            是否成功
        """
        if not self.logged_in:
            if not self.login():
                return False
        
        # 先检查客户端是否已存在
        inbound_info = self.get_inbound_info(inbound_id)
        if inbound_info:
            client_stats = inbound_info.get('clientStats', [])
            for client_stat in client_stats:
                if client_stat.get('email') == email:
                    # 客户端已存在，更新配置
                    logger.info(f"客户端 {email} 已存在于节点 {inbound_id}，执行更新操作")
                    client_uuid = client_stat.get('uuid')
                    if not client_uuid:
                        logger.error(f"无法获取客户端UUID")
                        return False
                    
                    # 构建客户端数据
                    import random
                    import string
                    import time
                    
                    # 生成新的subId
                    sub_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=16))
                    current_time = int(time.time() * 1000)
                    
                    # 获取默认flow值
                    flow = self.get_default_client_flow(inbound_id)
                    
                    client_data = {
                        "id": client_uuid,
                        "flow": flow,
                        "email": email,
                        "limitIp": 0,
                        "totalGB": 0,
                        "expiryTime": 0,
                        "enable": True,
                        "tgId": "",
                        "subId": sub_id,
                        "comment": "",
                        "reset": 0,
                        "created_at": current_time,
                        "updated_at": current_time
                    }
                    
                    return self.update_client(client_uuid, inbound_id, client_data)
        
        # 客户端不存在，添加新客户端
        add_url = f"{self.base_url}/panel/api/inbounds/addClient"
        
        # 生成UUID
        client_uuid = self.get_new_uuid()
        if not client_uuid:
            logger.error(f"生成UUID失败")
            return False
        
        # 生成subId
        import random
        import string
        sub_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=16))
        
        # 获取当前时间戳（毫秒）
        import time
        current_time = int(time.time() * 1000)
        
        # 获取默认flow值
        flow = self.get_default_client_flow(inbound_id)
        
        # 构建客户端数据
        client_data = {
            "id": client_uuid,
            "flow": flow,
            "email": email,
            "limitIp": 0,
            "totalGB": 0,
            "expiryTime": 0,
            "enable": True,
            "tgId": "",
            "subId": sub_id,
            "comment": "",
            "reset": 0,
            "created_at": current_time,
            "updated_at": current_time
        }
        
        # 准备请求数据
        payload = {
            'id': inbound_id,
            'settings': json.dumps({"clients": [client_data]})
        }
        
        logger.debug(f"添加客户端请求数据: {payload}")
        
        for attempt in range(2):
            try:
                response = self.session.post(add_url, json=payload, verify=False, timeout=10)
                
                if response.status_code == 401 or response.status_code == 403:
                    logger.warning(f"Session 可能已过期 {self.server}:{self.port}，尝试重新登录...")
                    self.logged_in = False
                    if attempt == 0 and self.login():
                        continue
                    return False
                
                try:
                    data = response.json()
                except ValueError as e:
                    logger.error(f"添加客户端响应JSON解析失败 {self.server}:{self.port}: {response.text}")
                    return False
                
                if data.get('success'):
                    logger.info(f"成功添加客户端: {email} 到节点 {inbound_id}")
                    # 清除缓存，以便下次获取最新数据
                    if self.board_name:
                        inbounds_cache.clear(self.board_name)
                    return True
                else:
                    logger.warning(f"添加客户端失败: {data.get('msg')}")
                    return False
                    
            except Exception as e:
                logger.error(f"添加客户端时发生错误: {str(e)}")
                if attempt == 0:
                    self.logged_in = False
                    if self.login():
                        continue
                return False
        
        return False
    
    def delete_client(self, inbound_id: int, email: str) -> bool:
        """
        从入站节点删除客户端
        参数:
            inbound_id: 入站节点ID
            email: 客户端邮箱
        返回:
            是否成功
        """
        if not self.logged_in:
            if not self.login():
                return False
        
        # 先获取客户端UUID
        inbound_info = self.get_inbound_info(inbound_id)
        if not inbound_info:
            logger.error(f"无法获取节点信息，inbound_id: {inbound_id}")
            return False
        
        client_stats = inbound_info.get('clientStats', [])
        client_uuid = None
        for client_stat in client_stats:
            if client_stat.get('email') == email:
                client_uuid = client_stat.get('uuid')
                break
        
        if not client_uuid:
            logger.warning(f"未找到客户端 {email} 在节点 {inbound_id} 中")
            return False
        
        delete_url = f"{self.base_url}/panel/api/inbounds/{inbound_id}/delClient/{client_uuid}"
        
        for attempt in range(2):
            try:
                response = self.session.post(delete_url, verify=False, timeout=10)
                
                if response.status_code == 401 or response.status_code == 403:
                    logger.warning(f"Session 可能已过期 {self.server}:{self.port}，尝试重新登录...")
                    self.logged_in = False
                    if attempt == 0 and self.login():
                        continue
                    return False
                
                try:
                    data = response.json()
                except ValueError:
                    logger.error(f"删除客户端响应JSON解析失败 {self.server}:{self.port}")
                    return False
                
                if data.get('success'):
                    logger.info(f"成功删除客户端: {email} 从节点 {inbound_id}")
                    # 清除缓存，以便下次获取最新数据
                    if self.board_name:
                        inbounds_cache.clear(self.board_name)
                    return True
                else:
                    logger.warning(f"删除客户端失败: {data.get('msg')}")
                    return False
                    
            except Exception as e:
                logger.error(f"删除客户端时发生错误: {str(e)}")
                if attempt == 0:
                    self.logged_in = False
                    if self.login():
                        continue
                return False
        
        return False


class XUIManager:
    """管理所有3XUI面板实例"""
    
    def __init__(self, config: Dict):
        self.clients: Dict[str, XUIClient] = {}
        self._load_config(config)
    
    def _load_config(self, config: Dict):
        """加载配置并创建客户端实例"""
        boards = config.get('boards', {})
        for board_name, board_config in boards.items():
            try:
                client = XUIClient(
                    server=board_config['server'],
                    port=board_config['port'],
                    path=board_config['path'],
                    username=board_config['username'],
                    password=board_config['password'],
                    sub_path=board_config['sub_path'],
                    board_name=board_name  # 传递 board_name 用于缓存
                )
                self.clients[board_name] = client
                logger.info(f"已加载面板配置: {board_name}")
            except Exception as e:
                logger.error(f"加载面板配置 {board_name} 失败: {str(e)}")
    
    def get_aggregated_subscription(self, email: str, user=None) -> Optional[tuple]:
        """
        获取聚合的订阅信息
        参数:
            email: 用户邮箱
            user: User对象（可选），用于获取套餐流量和到期时间信息
        返回:
            (base64_content, traffic_info) 元组
            base64_content: 聚合后的BASE64订阅内容
            traffic_info: {upload, download, total, expire} 字典
        """
        all_nodes = []
        
        # 获取所有面板的流量信息
        traffic_list = []
        for board_name, client in self.clients.items():
            # 获取该面板中所有匹配Email的节点流量
            traffic_info_list = client.get_client_traffic(email)
            
            # 为每个节点添加面板信息
            for traffic_info in traffic_info_list:
                traffic_info['board_name'] = board_name
                traffic_info['server'] = client.server
                traffic_list.append(traffic_info)
        
        for traffic_info in traffic_list:
            sub_id = traffic_info.get('subId')
            if not sub_id:
                continue
            
            # 获取对应的客户端
            board_name = traffic_info.get('board_name')
            client = self.clients.get(board_name) if board_name else None
            if not client:
                continue
            
            # 获取订阅内容
            sub_content = client.get_subscription(sub_id)
            if sub_content:
                try:
                    # 解码BASE64
                    decoded = base64.b64decode(sub_content).decode('utf-8')
                    
                    # 处理每一行节点信息
                    processed_lines = []
                    for line in decoded.split('\n'):
                        line = line.strip()
                        if not line:
                            continue
                        
                        # 检查是否包含 # 备注部分
                        if '#' in line:
                            # 使用 rsplit 确保只在最后一个 # 处分割（因为 URL 中可能包含 #）
                            url_part, remark = line.rsplit('#', 1)
                            
                            # URL 解码备注（邮箱可能被编码为 %40 等）
                            from urllib.parse import unquote
                            decoded_remark = unquote(remark)
                            
                            # 查找邮箱在备注中的位置（在解码后的备注中查找）
                            if email in decoded_remark:
                                # 找到邮箱前面的 "-" 位置
                                email_index = decoded_remark.find(email)
                                if email_index > 0 and decoded_remark[email_index - 1] == '-':
                                    # 删除从 "-邮箱" 开始到结尾的所有内容
                                    cleaned_remark = decoded_remark[:email_index - 1].strip()
                                elif email_index == 0:
                                    # 如果邮箱就在开头，删除整个备注
                                    cleaned_remark = ''
                                else:
                                    # 如果邮箱前面不是 "-"，只删除邮箱及其后面的内容
                                    cleaned_remark = decoded_remark[:email_index].rstrip('-').strip()
                                
                                # URL 编码清理后的备注
                                from urllib.parse import quote
                                encoded_remark = quote(cleaned_remark, safe='')
                            else:
                                # 没有找到邮箱，保持原样
                                encoded_remark = remark
                            
                            # 重新组合节点信息
                            if encoded_remark:
                                processed_lines.append(f"{url_part}#{encoded_remark}")
                            else:
                                processed_lines.append(url_part)
                        else:
                            # 没有备注的节点直接添加
                            processed_lines.append(line)
                    
                    # 将处理后的节点添加到列表
                    if processed_lines:
                        all_nodes.extend(processed_lines)
                        
                except Exception as e:
                    logger.error(f"解码订阅内容失败 {board_name}: {str(e)}")
        
        if not all_nodes:
            return None
        
        # 聚合所有节点，用换行符分割
        aggregated = '\n'.join(all_nodes)
        
        # 重新编码为BASE64
        aggregated_base64 = base64.b64encode(aggregated.encode('utf-8')).decode('utf-8')
        
        # 构建流量信息
        # 如果提供了user对象且有套餐信息，使用套餐数据
        if user and user.package_id:
            from models import Package
            package = Package.query.get(user.package_id)
            if package:
                # 使用套餐信息
                used_traffic_bytes = int((user.used_traffic or 0) * 1024 * 1024 * 1024)  # GB转字节
                total_traffic_bytes = package.total_traffic
                expire_timestamp = int(user.package_expire_time.timestamp()) if user.package_expire_time else 0
                
                traffic_info = {
                    'upload': 0,  # 不显示上传流量
                    'download': used_traffic_bytes,  # 使用已用流量
                    'total': total_traffic_bytes,  # 套餐总流量
                    'expire': expire_timestamp  # 套餐到期时间（秒级时间戳）
                }
            else:
                # 套餐不存在，使用默认值
                traffic_info = {
                    'upload': 0,
                    'download': 0,
                    'total': 0,
                    'expire': 0
                }
        else:
            # 没有套餐信息，使用默认值
            traffic_info = {
                'upload': 0,
                'download': 0,
                'total': 0,
                'expire': 0
            }
        
        return aggregated_base64, traffic_info
    
    def get_all_inbounds(self) -> List[Dict]:
        """
        从所有面板获取节点列表
        返回:
            包含所有节点信息的列表
        """
        inbounds_list = []
        
        for board_name, client in self.clients.items():
            inbounds = client.get_inbounds_list()
            if inbounds:
                for inbound in inbounds:
                    # 添加服务器信息
                    inbound['board_name'] = board_name
                    inbound['server'] = client.server
                    inbounds_list.append(inbound)
        
        return inbounds_list
    
    def get_client_traffic(self, email: str) -> List[Dict]:
        """
        从所有面板获取指定邮箱的流量信息
        参数:
            email: 用户邮箱
        返回:
            流量信息列表，每个元素包含 {board_name, server, inbound_id, up, down, total, expiryTime}
        """
        all_traffic = []
        
        for board_name, client in self.clients.items():
            traffic_list = client.get_client_traffic(email)
            
            # 为每个流量记录添加面板信息
            for traffic in traffic_list:
                traffic['board_name'] = board_name
                traffic['server'] = client.server
                all_traffic.append(traffic)
        
        return all_traffic
    
    def get_all_clients_by_email(self, email: str) -> List[Dict]:
        """
        从所有面板获取指定邮箱的客户端信息
        参数:
            email: 用户邮箱
        返回:
            客户端信息列表，每个元素包含 {board_name, server, inbound_id, client}
        """
        all_clients = []
        
        for board_name, client in self.clients.items():
            inbounds = client.get_inbounds_list()
            if not inbounds:
                continue
            
            for inbound in inbounds:
                try:
                    settings = json.loads(inbound.get('settings', '{}'))
                    clients = settings.get('clients', [])
                    
                    for cli in clients:
                        if cli.get('email') == email:
                            all_clients.append({
                                'board_name': board_name,
                                'server': client.server,
                                'inbound_id': inbound['id'],
                                'client': cli
                            })
                except Exception as e:
                    logger.error(f"解析节点 {inbound.get('id')} 的客户端信息失败: {str(e)}")
        
        return all_clients
    
    def update_client(self, board_name: str, client_uuid: str, inbound_id: int, client_data: Dict) -> bool:
        """
        更新客户端配置（在指定面板中）
        参数:
            board_name: 面板名称
            client_uuid: 客户端UUID
            inbound_id: 入站节点ID
            client_data: 客户端完整数据
        返回:
            是否成功
        """
        client = self.clients.get(board_name)
        if not client:
            logger.error(f"未找到面板: {board_name}")
            return False
        
        return client.update_client(client_uuid, inbound_id, client_data)
    
    def reset_client_traffic(self, board_name: str, inbound_id: int, email: str) -> bool:
        """
        重置客户端流量（在指定面板中）
        参数:
            board_name: 面板名称
            inbound_id: 入站节点ID
            email: 客户端邮箱
        返回:
            是否成功
        """
        client = self.clients.get(board_name)
        if not client:
            logger.error(f"未找到面板: {board_name}")
            return False
        
        return client.reset_client_traffic(inbound_id, email)
    
    def add_client_to_package_nodes(self, email: str, package_id: int) -> bool:
        """
        将用户添加到套餐内的所有节点
        参数:
            email: 用户邮箱
            package_id: 套餐ID
        返回:
            是否全部成功
        """
        from models import Package
        package = Package.query.get(package_id)
        if not package:
            logger.error(f"未找到套餐: {package_id}")
            return False
        
        # 获取套餐节点列表
        nodes = package.nodes
        if not nodes:
            logger.warning(f"套餐 {package_id} 没有配置节点")
            return True
        
        success_count = 0
        total_count = 0
        
        for node in nodes:
            board_name = node.board_name
            inbound_id = node.inbound_id
            
            if not board_name or not inbound_id:
                logger.warning(f"节点配置缺少必要字段: {node}")
                continue
            
            total_count += 1
            client = self.clients.get(board_name)
            if not client:
                logger.error(f"未找到面板: {board_name}")
                continue
            
            if client.add_client(inbound_id, email):
                success_count += 1
                logger.info(f"成功添加客户端 {email} 到面板 {board_name} 节点 {inbound_id}")
            else:
                logger.error(f"添加客户端 {email} 到面板 {board_name} 节点 {inbound_id} 失败")
        
        logger.info(f"添加客户端到套餐节点完成: 成功 {success_count}/{total_count}")
        return success_count == total_count
    
    def delete_client_from_package_nodes(self, email: str, package_id: int) -> bool:
        """
        从套餐内的所有节点删除用户
        参数:
            email: 用户邮箱
            package_id: 套餐ID
        返回:
            是否全部成功
        """
        from models import Package
        package = Package.query.get(package_id)
        if not package:
            logger.error(f"未找到套餐: {package_id}")
            return False
        
        # 获取套餐节点列表
        nodes = package.nodes
        if not nodes:
            logger.warning(f"套餐 {package_id} 没有配置节点")
            return True
        
        success_count = 0
        total_count = 0
        
        for node in nodes:
            board_name = node.board_name
            inbound_id = node.inbound_id
            
            if not board_name or not inbound_id:
                logger.warning(f"节点配置缺少必要字段: {node}")
                continue
            
            total_count += 1
            client = self.clients.get(board_name)
            if not client:
                logger.error(f"未找到面板: {board_name}")
                continue
            
            if client.delete_client(inbound_id, email):
                success_count += 1
                logger.info(f"成功删除客户端 {email} 从面板 {board_name} 节点 {inbound_id}")
            else:
                logger.warning(f"删除客户端 {email} 从面板 {board_name} 节点 {inbound_id} 失败")
        
        logger.info(f"从套餐节点删除客户端完成: 成功 {success_count}/{total_count}")
        return success_count == total_count
