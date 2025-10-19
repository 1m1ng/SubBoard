"""应用配置"""
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


class Config:
    """基础配置"""
    # Flask配置
    SECRET_KEY = os.getenv('SECRET_KEY')
    
    # 数据库配置
    SQLALCHEMY_DATABASE_URI = 'sqlite:///data.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # 服务器配置
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 5000))
    THREADS = int(os.getenv("THREADS", 4))
    
    # 缓存配置
    CACHE_DURATION = 300  # 节点信息缓存时间（秒）
    
    # 安全配置
    MAX_FAILED_ATTEMPTS = 5  # 最大登录失败次数
    BLOCK_DURATION = 30  # IP锁定时长（分钟）


class DevelopmentConfig(Config):
    """开发环境配置"""
    DEBUG = True


class ProductionConfig(Config):
    """生产环境配置"""
    DEBUG = False


# 配置字典
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': ProductionConfig
}
