"""流量统计和用户状态模型"""
from datetime import datetime
from utils.extensions import db


class UserNodeStatus(db.Model):
    """用户节点状态模型（记录被停用的用户）"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    is_disabled = db.Column(db.Boolean, default=False)  # 是否已停用
    disable_reason = db.Column(db.String(100))  # 停用原因：traffic_exceeded, package_expired
    disabled_at = db.Column(db.DateTime)  # 停用时间
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关联用户
    user = db.relationship('User', backref='node_status')
    
    def __repr__(self):
        return f'<UserNodeStatus user_id={self.user_id} disabled={self.is_disabled}>'
