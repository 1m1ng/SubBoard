"""Mihomo配置模板模型"""
from datetime import datetime
from extensions import db


class MihomoTemplate(db.Model):
    """Mihomo配置模板数据模型"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    template_content = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<MihomoTemplate {self.name}>'
