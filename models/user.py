"""用户模型"""
from datetime import datetime
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # 订阅相关字段
    subscription_token = db.Column(db.String(64), unique=True, nullable=True)

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
