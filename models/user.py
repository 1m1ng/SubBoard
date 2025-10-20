"""用户模型"""
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
import secrets
from extensions import db


class User(db.Model):
    """用户数据模型"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    # 订阅相关字段
    subscription_token = db.Column(db.String(64), unique=True, nullable=True)
    
    # 套餐相关字段
    package_id = db.Column(db.Integer, db.ForeignKey('package.id'), nullable=True)
    package_expire_time = db.Column(db.DateTime, nullable=True)  # 套餐到期时间
    next_reset_time = db.Column(db.DateTime, nullable=True)  # 下一次流量重置时间
    used_traffic = db.Column(db.BigInteger, default=0)  # 已使用流量（字节）

    def set_password(self, password):
        """设置密码"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """验证密码"""
        return check_password_hash(self.password_hash, password)
    
    def generate_subscription_token(self):
        """生成订阅Token"""
        self.subscription_token = secrets.token_urlsafe(32)
        return self.subscription_token

    def __repr__(self):
        return f'<User {self.username}>'
