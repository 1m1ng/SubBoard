"""XUI管理器工具"""
from xui_client import XUIManager
from models import ServerConfig
from extensions import logger

# 全局变量，用于缓存XUIManager实例
_xui_manager = None


def load_xui_config():
    """
    从数据库加载3XUI面板配置
    
    Returns:
        XUIManager: XUI管理器实例，如果没有配置则返回None
    """
    try:
        servers = ServerConfig.query.all()
        config = {'boards': {}}
        
        for server in servers:
            config['boards'][server.board_name] = server.to_dict()
        
        if config['boards']:
            return XUIManager(config)
        else:
            logger.warning("数据库中没有服务器配置")
            return None
    except Exception as e:
        logger.error(f"加载服务器配置失败: {str(e)}")
        return None


def get_xui_manager():
    """
    获取XUIManager实例，如果不存在则加载
    
    Returns:
        XUIManager: XUI管理器实例
    """
    global _xui_manager
    if _xui_manager is None:
        _xui_manager = load_xui_config()
    return _xui_manager


def reload_xui_manager():
    """重新加载XUI管理器"""
    global _xui_manager
    _xui_manager = load_xui_config()
    return _xui_manager
