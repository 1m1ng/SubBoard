"""JWT令牌模型"""
from datetime import datetime, timezone
from utils.extensions import db


class JWTToken(db.Model):
    """JWT令牌数据模型 - 用于存储和验证有效的token"""
    __tablename__ = 'jwt_token'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    token = db.Column(db.String(500), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = db.Column(db.DateTime, nullable=False)
    is_revoked = db.Column(db.Boolean, default=False)  # 是否已撤销
    user_agent = db.Column(db.String(500), nullable=True)  # 用户代理
    ip_address = db.Column(db.String(50), nullable=True)  # IP地址
    
    # 关联用户
    user = db.relationship('User', backref=db.backref('tokens', lazy='dynamic'))

    def __repr__(self):
        return f'<JWTToken user_id={self.user_id} revoked={self.is_revoked}>'
