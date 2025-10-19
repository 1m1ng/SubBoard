"""节点信息缓存管理"""
import time
from config import Config


class NodeCache:
    """节点信息缓存类"""
    
    def __init__(self):
        """初始化缓存"""
        self._cache = {}
        self._duration = Config.CACHE_DURATION
    
    def get(self, user_id, force_refresh=False):
        """
        获取缓存数据
        
        Args:
            user_id: 用户ID
            force_refresh: 是否强制刷新
            
        Returns:
            tuple: (缓存数据, 是否来自缓存, 缓存年龄)
        """
        current_time = time.time()
        
        if not force_refresh and user_id in self._cache:
            cache_entry = self._cache[user_id]
            cache_age = int(current_time - cache_entry['timestamp'])
            
            if cache_age < self._duration:
                return cache_entry['data'], True, cache_age
        
        return None, False, 0
    
    def set(self, user_id, data):
        """
        设置缓存数据
        
        Args:
            user_id: 用户ID
            data: 要缓存的数据
        """
        self._cache[user_id] = {
            'data': data,
            'timestamp': time.time()
        }
    
    def clear(self, user_id=None):
        """
        清除缓存
        
        Args:
            user_id: 用户ID，如果为None则清除所有缓存
        """
        if user_id is None:
            self._cache.clear()
        elif user_id in self._cache:
            del self._cache[user_id]


# 创建全局缓存实例
nodes_cache = NodeCache()
