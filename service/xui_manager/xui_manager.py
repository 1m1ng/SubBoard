from .xui_client import XUIClient 
from typing import Dict, Optional, List
from models import User, Package, PackageNode
from utils.extensions import logger


class XUIManager:
    def __init__(self, config: Dict):
        self.servers: Dict[str, XUIClient] = {}
        boards: Dict[str, Dict] = config.get('boards', {})
        for board_name, board_config in boards.items():
            server = XUIClient(
                board_name=board_name,
                server=board_config.get('server', ''),
                port=board_config.get('port', 80),
                path=board_config.get('path', ''),
                username=board_config.get('username', ''),
                password=board_config.get('password', ''),
                sub_path=board_config.get('sub_path', '')
            )
            self.servers[board_name] = server
            
    def get_subscriptions(self, user: User) -> Optional[List[str]]:
        package: Package = Package.query.get(user.package_id) # type: ignore
        if package:
            nodes: List[PackageNode] = package.nodes # type: ignore
            
            subscriptions = []
            for node in nodes:
                server = self.servers.get(node.board_name)
                if server:
                    client = server.get_client(node.inbound_id, user.email)
                    if client:
                        sub_content = server.get_subscription(node.inbound_id, user.email)
                        if sub_content:
                            subscriptions.append(sub_content)
            return subscriptions
        
        return None
    
    def add_client_to_package_nodes(self, user: User) -> bool:
        package: Package = Package.query.get(user.package_id) # type: ignore
        if package:
            nodes: List[PackageNode] = package.nodes # type: ignore
            if not nodes:
                logger.warning(f"套餐 {package.id} 没有配置任何节点")
                return False
            
            success_count = 0
            total_count = 0
            
            for node in nodes:
                server = self.servers.get(node.board_name)
                if server:
                    total_count += 1
                    if not server.add_client(node.inbound_id, user.email):
                        logger.warning(f"无法为用户 {user.username} 在节点 {node.board_name} 的入站 {node.inbound_id} 添加客户端")
                    else:
                        success_count += 1
            logger.info(f"用户 {user.username} 在套餐 {package.id} 中成功添加了 {success_count} 个客户端，失败了 {total_count - success_count} 个")
            return True
        else:
            logger.warning(f"用户 {user.username} 的套餐 ID {user.package_id} 无效")
            return False

    def delete_client_from_package_nodes(self, email: str, package_id: int) -> bool:
        package: Package = Package.query.get(package_id) # type: ignore
        if package:
            nodes: List[PackageNode] = package.nodes # type: ignore
            if not nodes:
                logger.warning(f"套餐 {package.id} 没有配置任何节点")
                return False
            
            success_count = 0
            total_count = 0
            
            for node in nodes:
                server = self.servers.get(node.board_name)
                if server:
                    total_count += 1
                    if not server.delete_client(node.inbound_id, email):
                        logger.warning(f"无法为用户 {email} 在节点 {node.board_name} 的入站 {node.inbound_id} 移除客户端")
                    else:
                        success_count += 1
            logger.info(f"用户 {email} 在套餐 {package.id} 中成功移除了 {success_count} 个客户端，失败了 {total_count - success_count} 个")
            return True
        else:
            logger.warning(f"用户 {email} 的套餐 ID {package_id} 无效")
            return False
        
    def clear_cache_all_servers(self) -> None:
        for server in self.servers.values():
            server.clear_cache()

    def refresh_client_from_package_nodes(self, user: User) -> bool:
        package: Package = Package.query.get(user.package_id) # type: ignore
        if package:
            nodes: List[PackageNode] = package.nodes # type: ignore
            if not nodes:
                logger.warning(f"套餐 {package.id} 没有配置任何节点")
                return False
            
            success_count = 0
            total_count = 0
            
            for node in nodes:
                server = self.servers.get(node.board_name)
                if server:
                    total_count += 1
                    if not server.refresh_client_key(node.inbound_id, user.email):
                        logger.warning(f"无法为用户 {user.username} 在节点 {node.board_name} 的入站 {node.inbound_id} 更新客户端")
                    else:
                        success_count += 1
            logger.info(f"用户 {user.username} 在套餐 {package.id} 中成功更新了 {success_count} 个客户端，失败了 {total_count - success_count} 个")
            return True
        else:
            logger.warning(f"用户 {user.username} 的套餐 ID {user.package_id} 无效")
            return False

    def get_all_inbounds(self) -> List[Dict]:
        """获取所有服务器的入站信息，并将每个入站信息添加 board_name 字段"""
        all_inbounds = []
        for board_name, server in self.servers.items():
            inbounds = server.get_inbounds()
            if inbounds:
                for inbound in inbounds:
                    inbound['board_name'] = board_name  # 为每个入站信息添加 board_name 字段
                    all_inbounds.append(inbound)
        return all_inbounds
    
    def delete_clients_from_node(self, board_name: str, inbound_id: int, emails: List[str]) -> bool:
        server = self.servers.get(board_name)
        if not server:
            logger.warning(f"节点服务器 {board_name} 未找到")
            return False
        
        success_count = 0
        total_count = 0
        
        for email in emails:
            total_count += 1
            if not server.delete_client(inbound_id, email):
                logger.warning(f"无法为用户 {email} 在节点 {board_name} 的入站 {inbound_id} 移除客户端")
            else:
                success_count += 1
        logger.info(f"在节点 {board_name} 的入站 {inbound_id} 中成功移除了 {success_count} 个客户端，失败了 {total_count - success_count} 个")
        return True
    
    def add_clients_to_node(self, board_name: str, inbound_id: int, emails: List[str]) -> bool:
        server = self.servers.get(board_name)
        if not server:
            logger.warning(f"节点服务器 {board_name} 未找到")
            return False
        
        success_count = 0
        total_count = 0
        
        for email in emails:
            total_count += 1
            if not server.add_client(inbound_id, email):
                logger.warning(f"无法为用户 {email} 在节点 {board_name} 的入站 {inbound_id} 添加客户端")
            else:
                success_count += 1
        logger.info(f"在节点 {board_name} 的入站 {inbound_id} 中成功添加了 {success_count} 个客户端，失败了 {total_count - success_count} 个")
        return True
    
    def disable_client_from_package_nodes(self, user: User) -> bool:
        package: Package = Package.query.get(user.package_id) # type: ignore
        if package:
            nodes: List[PackageNode] = package.nodes # type: ignore
            if not nodes:
                logger.warning(f"套餐 {package.id} 没有配置任何节点")
                return False
            
            success_count = 0
            total_count = 0
            
            for node in nodes:
                server = self.servers.get(node.board_name)
                if server:
                    total_count += 1
                    client = server.get_client(node.inbound_id, user.email)
                    if not client:
                        logger.warning(f"无法为用户 {user.email} 在节点 {node.board_name} 的入站 {node.inbound_id} 找到客户端以禁用")
                    else:
                        client['enable'] = False
                        if server.update_client(node.inbound_id, user.email, client):
                            success_count += 1
                        else:
                            logger.warning(f"无法为用户 {user.email} 在节点 {node.board_name} 的入站 {node.inbound_id} 禁用客户端")

            logger.info(f"用户 {user.email} 在套餐 {package.id} 中成功禁用了 {success_count} 个客户端，失败了 {total_count - success_count} 个")
            return True
        else:
            logger.warning(f"用户 {user.email} 的套餐 ID {user.package_id} 无效")
            return False
        
    def enable_client_from_package_nodes(self, user: User) -> bool:
        package: Package = Package.query.get(user.package_id) # type: ignore
        if package:
            nodes: List[PackageNode] = package.nodes # type: ignore
            if not nodes:
                logger.warning(f"套餐 {package.id} 没有配置任何节点")
                return False
            
            success_count = 0
            total_count = 0
            
            for node in nodes:
                server = self.servers.get(node.board_name)
                if server:
                    total_count += 1
                    client = server.get_client(node.inbound_id, user.email)
                    if not client:
                        logger.warning(f"无法为用户 {user.email} 在节点 {node.board_name} 的入站 {node.inbound_id} 找到客户端以启用")
                    else:
                        client['enable'] = True
                        if server.update_client(node.inbound_id, user.email, client):
                            success_count += 1
                        else:
                            logger.warning(f"无法为用户 {user.email} 在节点 {node.board_name} 的入站 {node.inbound_id} 启用客户端")

            logger.info(f"用户 {user.email} 在套餐 {package.id} 中成功启用了 {success_count} 个客户端，失败了 {total_count - success_count} 个")
            return True
        else:
            logger.warning(f"用户 {user.email} 的套餐 ID {user.package_id} 无效")
            return False

    def get_used_traffic(self, user: User) -> Optional[Dict[str, int]]:
        package: Package = Package.query.get(user.package_id) # type: ignore
        if package:
            nodes: List[PackageNode] = package.nodes # type: ignore
            if not nodes:
                logger.warning(f"套餐 {package.id} 没有配置任何节点")
                return None
            
            total_upload = 0
            total_download = 0
            
            for node in nodes:
                server = self.servers.get(node.board_name)
                if server:
                    stat = server.get_client_traffic(node.inbound_id, user.email)
                    # 查找该节点的流量倍率（使用 board_name 和 inbound_id 匹配）
                    package_node = next(
                        (pn for pn in nodes 
                        if pn.board_name == node.board_name and pn.inbound_id == node.inbound_id),
                        None
                    )
                    if not package_node:
                        logger.warning(f"无法为用户 {user.email} 在节点 {node.board_name} 的入站 {node.inbound_id} 找到对应的套餐节点以获取流量倍率")
                        continue
                    if stat:
                        upload = stat.get('up', 0) * package_node.traffic_rate
                        download = stat.get('down', 0) * package_node.traffic_rate
                        total_upload += upload
                        total_download += download
                    else:
                        logger.warning(f"无法为用户 {user.email} 在节点 {node.board_name} 的入站 {node.inbound_id} 获取流量统计")
            
            return {
                'up': total_upload,
                'down': total_download,
                'total': total_upload + total_download
            }
        else:
            logger.warning(f"用户 {user.email} 的套餐 ID {user.package_id} 无效")
            return None
        