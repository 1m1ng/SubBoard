"""服务器配置模型"""
from datetime import datetime
from extensions import db


class ServerConfig(db.Model):
    """服务器配置数据模型"""
    id = db.Column(db.Integer, primary_key=True)
    board_name = db.Column(db.String(50), unique=True, nullable=False)
    server = db.Column(db.String(255), nullable=False)
    port = db.Column(db.Integer, nullable=False)
    path = db.Column(db.String(255), nullable=False)
    sub_path = db.Column(db.String(255), nullable=False)  # 订阅路径
    username = db.Column(db.String(255), nullable=False)
    password = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<ServerConfig {self.board_name}>'
    
    def to_dict(self):
        """转换为字典格式"""
        return {
            'server': self.server,
            'port': self.port,
            'path': self.path,
            'sub_path': self.sub_path,
            'username': self.username,
            'password': self.password
        }
