"""IP锁定记录模型"""
from datetime import datetime
from extensions import db


class IPBlock(db.Model):
    """IP锁定记录数据模型"""
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(45), unique=True, nullable=False)
    failed_attempts = db.Column(db.Integer, default=0)
    blocked_until = db.Column(db.DateTime(timezone=True), nullable=True)  # 添加 timezone=True
    last_attempt = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<IPBlock {self.ip_address}>'
