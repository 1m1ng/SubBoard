"""Flask扩展初始化"""
from flask_sqlalchemy import SQLAlchemy
import logging
import os

# 初始化数据库
db = SQLAlchemy()

# 配置日志
def setup_logging():
    """配置应用日志"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('app.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    logging.getLogger().setLevel(os.getenv('LOG_LEVEL', 'INFO').upper())
    return logging.getLogger(__name__)

logger = setup_logging()
