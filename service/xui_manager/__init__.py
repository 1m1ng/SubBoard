from .xui_manager import XUIManager
from models import ServerConfig
from utils.extensions import logger
from typing import Optional

_xui_manager: Optional[XUIManager] = None


def _init_xui_manager() -> Optional[XUIManager]:
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
    

def get_xui_manager() -> Optional[XUIManager]:
    global _xui_manager
    if _xui_manager is None:
        _xui_manager = _init_xui_manager()
    return _xui_manager


def reload_xui_manager() -> Optional[XUIManager]:
    return _init_xui_manager()

