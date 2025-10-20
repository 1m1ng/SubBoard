"""节点信息缓存管理"""
import time
from typing import Optional, List, Dict
from config import Config


class InboundsCache:
    """入站节点列表缓存类（全局单例）"""
    
    def __init__(self, duration=60):
        """
        初始化缓存
        
        Args:
            duration: 缓存持续时间（秒），默认60秒
        """
        # 存储每个面板的缓存数据
        # 格式: {board_name: {'data': [...], 'timestamp': float}}
        self._board_cache: Dict[str, Dict] = {}
        
        # 存储聚合后的所有面板数据（用于API返回）
        self._aggregated_cache: Optional[List[Dict]] = None
        self._aggregated_timestamp: Optional[float] = None
        
        self._duration = duration
    
    def get_board(self, board_name: str) -> tuple:
        """
        获取指定面板的缓存数据
        
        Args:
            board_name: 面板名称
            
        Returns:
            tuple: (缓存数据, 是否来自缓存, 缓存年龄)
        """
        current_time = time.time()
        
        if board_name in self._board_cache:
            cache_entry = self._board_cache[board_name]
            cache_age = int(current_time - cache_entry['timestamp'])
            
            if cache_age < self._duration:
                return cache_entry['data'], True, cache_age
        
        return None, False, 0
    
    def set_board(self, board_name: str, data: List[Dict]):
        """
        设置指定面板的缓存数据
        
        Args:
            board_name: 面板名称
            data: 要缓存的入站列表数据
        """
        self._board_cache[board_name] = {
            'data': data,
            'timestamp': time.time()
        }
    
    def get_aggregated(self) -> tuple:
        """
        获取聚合后的所有面板数据
        
        Returns:
            tuple: (缓存数据, 是否来自缓存)
        """
        current_time = time.time()
        
        if self._aggregated_cache is not None and self._aggregated_timestamp is not None:
            cache_age = int(current_time - self._aggregated_timestamp)
            
            if cache_age < self._duration:
                return self._aggregated_cache, True
        
        return None, False
    
    def set_aggregated(self, data: List[Dict]):
        """
        设置聚合后的缓存数据
        
        Args:
            data: 聚合后的所有面板入站列表
        """
        self._aggregated_cache = data
        self._aggregated_timestamp = time.time()
    
    def clear(self, board_name: Optional[str] = None):
        """
        清除缓存
        
        Args:
            board_name: 面板名称，如果为None则清除所有缓存
        """
        if board_name is None:
            self._board_cache.clear()
            self._aggregated_cache = None
            self._aggregated_timestamp = None
        elif board_name in self._board_cache:
            del self._board_cache[board_name]
            # 清除聚合缓存，因为数据已变化
            self._aggregated_cache = None
            self._aggregated_timestamp = None
    
    def find_inbound(self, board_name: str, inbound_id: int) -> Optional[Dict]:
        """
        从缓存中查找特定的入站节点信息
        
        Args:
            board_name: 面板名称
            inbound_id: 入站节点ID
            
        Returns:
            节点信息字典，未找到返回None
        """
        data, from_cache, _ = self.get_board(board_name)
        if data and from_cache:
            for inbound in data:
                if inbound.get('id') == inbound_id:
                    return inbound
        return None
    
    def get_all_boards(self) -> Dict[str, List[Dict]]:
        """
        获取所有面板的缓存数据（不检查过期）
        
        Returns:
            字典: {board_name: [inbound_list]}
        """
        result = {}
        for board_name, cache_entry in self._board_cache.items():
            result[board_name] = cache_entry['data']
        return result


# 创建全局入站列表缓存实例（缓存60秒）
inbounds_cache = InboundsCache(duration=60)
