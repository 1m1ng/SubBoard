"""
3XUI API客户端
用于与3XUI面板进行交互
"""
import requests
import logging
from typing import Dict, Optional, List
import base64
import urllib3

# 禁用SSL警告（用于自签名证书）
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


class XUIClient:
    """3XUI面板API客户端"""
    
    def __init__(self, server: str, port: int, path: str, username: str, password: str, sub_path: str):
        self.server = server
        self.port = port
        self.path = path.strip('/')
        self.sub_path = sub_path.strip('/')  # 订阅路径
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.base_url = f"https://{server}:{port}/{path}"
        self.logged_in = False
        
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
    
    def get_client_traffic(self, email: str) -> Optional[Dict]:
        """
        获取客户端流量信息
        参数:
            email: 用户邮箱
        返回:
            包含流量信息的字典，失败返回None
        """
        if not self.logged_in:
            if not self.login():
                return None
        
        traffic_url = f"{self.base_url}/panel/api/inbounds/getClientTraffics/{email}"
        
        try:
            response = self.session.get(traffic_url, verify=False, timeout=10)
            data = response.json()
            
            if data.get('success'):
                return data.get('obj')
            else:
                logger.warning(f"获取流量失败 {self.server}:{self.port}, email: {email}: {data.get('msg')}")
                return None
        except Exception as e:
            logger.error(f"获取流量信息时发生错误 {self.server}:{self.port}: {str(e)}")
            return None
    
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
        获取入站节点的详细信息
        参数:
            inbound_id: 入站节点ID
        返回:
            包含节点信息的字典，失败返回None
        """
        if not self.logged_in:
            if not self.login():
                return None
        
        inbound_url = f"{self.base_url}/panel/api/inbounds/get/{inbound_id}"
        
        try:
            response = self.session.get(inbound_url, verify=False, timeout=10)
            data = response.json()
            
            if data.get('success'):
                return data.get('obj')
            else:
                logger.warning(f"获取节点信息失败 {self.server}:{self.port}, inbound_id: {inbound_id}: {data.get('msg')}")
                return None
        except Exception as e:
            logger.error(f"获取节点信息时发生错误 {self.server}:{self.port}: {str(e)}")
            return None


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
                    sub_path=board_config['sub_path']
                )
                self.clients[board_name] = client
                logger.info(f"已加载面板配置: {board_name}")
            except Exception as e:
                logger.error(f"加载面板配置 {board_name} 失败: {str(e)}")
    
    def get_all_traffic_info(self, email: str) -> List[Dict]:
        """
        从所有面板获取用户的流量信息
        参数:
            email: 用户邮箱
        返回:
            包含所有节点流量信息的列表
        """
        import re
        traffic_list = []
        
        for board_name, client in self.clients.items():
            traffic_info = client.get_client_traffic(email)
            if traffic_info:
                # 添加面板名称标识
                traffic_info['board_name'] = board_name
                traffic_info['server'] = client.server
                
                # 获取节点详细信息（包括remark）
                inbound_id = traffic_info.get('inboundId')
                if inbound_id:
                    inbound_info = client.get_inbound_info(inbound_id)
                    if inbound_info:
                        remark = inbound_info.get('remark', '')
                        traffic_info['node_name'] = remark
                        
                        # 提取国旗emoji并转换为国家代码
                        flag_match = re.match(r'^([\U0001F1E6-\U0001F1FF]{2})', remark)
                        if flag_match:
                            flag_emoji = flag_match.group(1)
                            # 将emoji转换为国家代码（ISO 3166-1 alpha-2）
                            # emoji国旗是由两个Regional Indicator字符组成的
                            # 例如：🇨🇳 = U+1F1E8 U+1F1F3 -> CN
                            country_code = ''
                            for char in flag_emoji:
                                code_point = ord(char)
                                if 0x1F1E6 <= code_point <= 0x1F1FF:
                                    # 转换为A-Z字母
                                    country_code += chr(code_point - 0x1F1E6 + ord('A'))
                            traffic_info['country_code'] = country_code.lower()
                            traffic_info['flag_emoji'] = flag_emoji
                        else:
                            traffic_info['country_code'] = None
                            traffic_info['flag_emoji'] = '🌐'
                
                traffic_list.append(traffic_info)
        
        return traffic_list
    
    def get_aggregated_subscription(self, email: str) -> Optional[tuple]:
        """
        获取聚合的订阅信息
        参数:
            email: 用户邮箱
        返回:
            (base64_content, traffic_info) 元组
            base64_content: 聚合后的BASE64订阅内容
            traffic_info: {upload, download, total, expire} 字典
        """
        all_nodes = []
        total_upload = 0
        total_download = 0
        total_traffic = 0
        max_expire = 0
        
        # 获取所有面板的流量信息
        traffic_list = self.get_all_traffic_info(email)
        
        for traffic_info in traffic_list:
            sub_id = traffic_info.get('subId')
            if not sub_id:
                continue
            
            # 获取对应的客户端
            board_name = traffic_info.get('board_name')
            client = self.clients.get(board_name)
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
                            url_part, remark = line.split('#', 1)
                            
                            # 查找邮箱在备注中的位置
                            if email in remark:
                                # 找到邮箱前面的 "-" 位置
                                email_index = remark.find(email)
                                if email_index > 0 and remark[email_index - 1] == '-':
                                    # 删除从 "-邮箱" 开始到结尾的所有内容
                                    remark = remark[:email_index - 1]
                                elif email_index == 0:
                                    # 如果邮箱就在开头，删除整个备注
                                    remark = ''
                                else:
                                    # 如果邮箱前面不是 "-"，只删除邮箱及其后面的内容
                                    remark = remark[:email_index].rstrip('-')
                            
                            # 重新组合节点信息
                            if remark:
                                processed_lines.append(f"{url_part}#{remark}")
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
            
            # 累计流量信息
            total_upload += traffic_info.get('up', 0)
            total_download += traffic_info.get('down', 0)
            total_traffic += traffic_info.get('total', 0)
            
            # 找出最晚的过期时间
            expiry = traffic_info.get('expiryTime', 0)
            if expiry > max_expire:
                max_expire = expiry
        
        if not all_nodes:
            return None
        
        # 聚合所有节点，用换行符分割
        aggregated = '\n'.join(all_nodes)
        
        # 重新编码为BASE64
        aggregated_base64 = base64.b64encode(aggregated.encode('utf-8')).decode('utf-8')
        
        # 构建流量信息
        traffic_info = {
            'upload': total_upload,
            'download': total_download,
            'total': total_traffic,
            'expire': max_expire // 1000  # 转换为秒
        }
        
        return aggregated_base64, traffic_info
