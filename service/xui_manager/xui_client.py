import requests
from typing import List, Optional, Dict
import time
import os
import json
import random
import string
import uuid
import subprocess
import base64
from utils.extensions import logger


class XUIClient:
    def __init__(self, board_name: str, server: str, port: int, path: str, username: str, password: str, sub_path: str) -> None:
        self.board_name = board_name
        self.username = username
        self.password = password
        self.server = server
        
        self.session = requests.Session()
        self.base_url = f"https://{server}:{port}/{path}"
        self.sub_url = f"https://{server}:{port}/{sub_path}"
        
        self.cache_duration = int(os.getenv("CACHE_INBOUNDS_DURATION", 60))  # seconds
        self.cache_timestamp: float = 0
        self.cache_inbounds = None
        
        self.login()

    def login(self) -> bool:
        login_url = f"{self.base_url}/login"
        payload = {
            "username": self.username,
            "password": self.password
        }
        
        try:
            response = self.session.post(login_url, json=payload, verify=True, timeout=10)
            data = response.json()
            
            if data["success"]:
                return True
            else:
                raise Exception(data.get('msg'))
        except Exception as e:
            logger.error(f"[{self.board_name}] Exception during login: {e}")
            return False

    def _make_request(self, method: str, url: str, **kwargs) -> Dict:
        for attempt in range(2):
            try:
                response = self.session.request(method, url, verify=True, timeout=10, **kwargs)
                
                if response.status_code == 401 or response.status_code == 403 or response.status_code == 404:
                    if self.login() and attempt == 0:
                        continue
                    raise Exception("Authentication failed.")
                
                try:
                    data = response.json()
                except ValueError as json_error:
                    raise Exception(f"JSON decode error: {json_error}")
                
                if data["success"]:
                    return data
                else:
                    raise Exception(data.get('msg'))
                
            except Exception as e:
                raise Exception(f"Request error: {e}")
                
        raise Exception("Max retries exceeded.")

    def get_inbounds(self, use_cache=True) -> Optional[List[Dict]]:
        inbounds_url = f"{self.base_url}/panel/api/inbounds/list"

        if use_cache and self.cache_inbounds:
            if int(time.time() - self.cache_timestamp) < self.cache_duration:
                logger.debug(f"[{self.board_name}] Returning cached inbounds.")
                return self.cache_inbounds
        
        try:
            data = self._make_request("GET", inbounds_url)
            if data['success']:
                self.cache_inbounds = data.get("obj", [])
                self.cache_timestamp = time.time()
                return self.cache_inbounds
            else:
                raise Exception(data.get('msg'))
        except Exception as e:
            logger.error(f"[{self.board_name}] Exception during inbounds retrieval: {e}")
            return None
    
    def clear_cache(self) -> None:
        self.cache_inbounds = None
        self.cache_timestamp = 0
        logger.debug(f"[{self.board_name}] Cache cleared.")
    
    def get_inbound(self, inbound_id: int) -> Optional[Dict]:
        inbounds = self.get_inbounds()
        if inbounds is None:
            return None
        
        for inbound in inbounds:
            if inbound.get("id") == inbound_id:
                return inbound
        
        logger.warning(f"[{self.board_name}] Inbound {inbound_id} not found.")
        return None

    def get_client(self, inbound_id: int, email: str) -> Optional[Dict]:
        inbound = self.get_inbound(inbound_id)
        if inbound is None:
            return None

        clients = json.loads(inbound.get("settings", "{}")).get("clients", [])
        for client in clients:
            if client.get("email") == email:
                return client
        return None

    def get_subscription(self, inbound_id: int, email: str) -> Optional[str]:
        client = self.get_client(inbound_id, email)
        if client is None:
            return None
        subId = client.get("subId", None)
        if subId is None:
            logger.debug(f"[{self.board_name}] No subId found for client {email}.")
            return None
        
        sub_url = self.sub_url + f"/{subId}"

        try:
            response = self.session.get(sub_url, verify=True, timeout=10)
            if response.status_code == 200:
                sub_content = response.text.strip()
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
                return ''.join(processed_lines)
            else:
                raise Exception(f"HTTP {response.status_code}")
        except Exception as e:
            logger.error(f"[{self.board_name}] Exception during subscription retrieval: {e}")
            return None

    def delete_client(self, inbound_id: int, email: str) -> bool:
        inbound = self.get_inbound(inbound_id)
        if inbound is None:
            logger.warning(f"[{self.board_name}] Inbound {inbound_id} not found for client deletion.")
            return False
        protocol = inbound.get('protocol', '')
        if protocol in ['vless', 'vmess']:
            client = self.get_client(inbound_id, email)
            if client is None:
                logger.warning(f"[{self.board_name}] Client {email} not found for deletion.")
                return False
            value = client.get("id")
        else:
            value = email
        
        delete_url = f"{self.base_url}/panel/api/inbounds/{inbound_id}/delClient/{value}"
        
        try:
            data = self._make_request("POST", delete_url)
            if data['success']:
                self.clear_cache()
                return True
            else:
                raise Exception(data.get('msg'))
        except Exception as e:
            logger.error(f"[{self.board_name}] Exception during client deletion: {e}")
            return False

    def is_uuid_used(self, inbound_id: int, uuid: str) -> bool:
        inbound = self.get_inbound(inbound_id)
        if inbound is None:
            return False
        
        clients = json.loads(inbound.get("settings", "{}")).get("clients", [])
        for client in clients:
            if client.get("id") == uuid:
                return True
        return False
        
    def generate_uuid(self, inbound_id: int) -> Optional[str]:
        new_uuid = str(uuid.uuid4())
        while self.is_uuid_used(inbound_id, new_uuid):
            new_uuid = str(uuid.uuid4())
        return new_uuid
        
    def get_default_client_flow(self, inbound_id: int) -> str:
        inbound = self.get_inbound(inbound_id)
        if inbound is None:
            return ""
        
        default_client = self.get_client(inbound_id, "default")
        if default_client is None:
            return ""
        return default_client.get("flow", "")
        
    def generate_shadowsocks_password(self, method: str) -> Optional[str]:
        # 定义支持的加密协议及其密钥长度
        method_key_length = {
            "2022-blake3-aes-128-gcm": 16,
            "2022-blake3-aes-256-gcm": 32,
            "2022-blake3-chacha20-poly1305": 32
        }
        
        if method not in method_key_length:
            logger.error(f"不支持的加密协议: {method}")
            return None
        
        key_length = method_key_length[method]
        
        try:
            # 使用 openssl 生成随机密钥
            result = subprocess.run(
                ["openssl", "rand", "-base64", str(key_length)],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                password = result.stdout.strip()
                return password
            else:
                raise Exception(f"openssl 命令失败，返回码: {result.returncode}")
                
        except FileNotFoundError:
            logger.error("未找到 openssl 命令，请确保已安装 OpenSSL")
            return None
        except subprocess.TimeoutExpired:
            logger.error("openssl 命令执行超时")
            return None
        except Exception as e:
            logger.error(f"生成密码时发生错误: {str(e)}")
            return None

    def add_client(self, inbound_id: int, email: str) -> bool:
        add_url = f"{self.base_url}/panel/api/inbounds/addClient"
        
        inbound = self.get_inbound(inbound_id)
        if inbound is None:
            return False
        
        try:
            # 检查客户端是否已存在
            client = self.get_client(inbound_id, email)
            if client:
                if not self.delete_client(inbound_id, email):
                    logger.debug(f"[{self.board_name}] Existing client {email} deleted before adding new one.")
            
            client_data = {
                "id": "",
                "password": "",
                "email": email,
                "flow": "",
                "method": "",
                "limitIp": 0,
                "totalGB": 0,
                "expireTime": 0,
                "enable": True,
                "tgId": "",
                "subId": ''.join(random.choices(string.ascii_lowercase + string.digits, k=16)),
                "comment": "",
                "reset": 0,
                "createTime": int(time.time() * 1000),
                "updateTime": int(time.time() * 1000)
            }
            
            protocol = inbound.get('protocol', '')
            if protocol in ['vless', 'vmess']:
                client_data["id"] = self.generate_uuid(inbound_id)
                client_data["flow"] = self.get_default_client_flow(inbound_id)
            elif protocol == 'shadowsocks':
                method = json.loads(inbound.get("settings", "{}")).get("method", "")
                password = self.generate_shadowsocks_password(method)
                if password is None:
                    raise Exception("Failed to generate Shadowsocks password.")
                client_data["password"] = password
            else:
                raise Exception(f"Unsupported protocol: {protocol}")
            
            payload = {
                "id": inbound_id,
                "settings": json.dumps({"clients": [client_data]})
            }
            
            data = self._make_request("POST", add_url, json=payload)
            if data['success']:
                self.clear_cache()
                return True
            else:
                raise Exception(data.get('msg'))
        except Exception as e:
            logger.error(f"[{self.board_name}] Exception during client addition: {e}")
            return False
        
    def update_client(self, inbound_id: int, email: str, client_data: Dict) -> bool:
        inbound = self.get_inbound(inbound_id)
        if inbound is None:
            logger.warning(f"[{self.board_name}] Inbound {inbound_id} not found for client deletion.")
            return False
        protocol = inbound.get('protocol', '')
        if protocol in ['vless', 'vmess']:
            client = self.get_client(inbound_id, email)
            if client is None:
                logger.warning(f"[{self.board_name}] Client {email} not found for deletion.")
                return False
            value = client.get("id")
        else:
            value = email
        
        update_url = f"{self.base_url}/panel/api/inbounds/updateClient/{value}"
        
        payload = {
            "id": inbound_id,
            "settings": json.dumps({"clients": [client_data]})
        }
        
        try:
            data = self._make_request("POST", update_url, json=payload)
            if data['success']:
                self.clear_cache()
                return True
            else:
                raise Exception(data.get('msg'))
        except Exception as e:
            logger.error(f"[{self.board_name}] Exception during client update: {e}")
            return False
        
    def refresh_client_key(self, inbound_id: int, email: str) -> bool:
        client = self.get_client(inbound_id, email)
        if client is None:
            logger.error(f"[{self.board_name}] Client {email} not found for key refresh.")
            return False
        
        protocol = self.get_inbound(inbound_id).get('protocol', '') # type: ignore
        try:
            if protocol in ['vless', 'vmess']:
                new_uuid = self.generate_uuid(inbound_id)
                client['id'] = new_uuid
            elif protocol == 'shadowsocks':
                method = json.loads(self.get_inbound(inbound_id).get("settings", "{}")).get("method", "") # type: ignore
                new_password = self.generate_shadowsocks_password(method)
                if new_password is None:
                    raise Exception("Failed to generate new Shadowsocks password.")
                client['password'] = new_password
            else:
                raise Exception(f"Unsupported protocol: {protocol}")
            
            return self.update_client(inbound_id, email, client)
        except Exception as e:
            logger.error(f"[{self.board_name}] Exception during key refresh for client {email}: {e}")
            return False
        
    def reset_client_traffic(self, inbound_id: int, email: str) -> bool:
        reset_url = f"{self.base_url}/panel/api/inbounds/{inbound_id}/resetClientTraffic/{email}"
        
        try:
            data = self._make_request("POST", reset_url)
            if data['success']:
                self.clear_cache()
                return True
            else:
                raise Exception(data.get('msg'))
        except Exception as e:
            logger.error(f"[{self.board_name}] Exception during traffic reset for client {email}: {e}")
            return False
    
    def get_client_traffic(self, inbound_id: int, email: str) -> Optional[Dict]:
        inbound = self.get_inbound(inbound_id)
        clientStats = inbound.get("clientStats", []) if inbound else []
        for stat in clientStats:
            if stat.get("email") == email:
                return stat
        return None
    