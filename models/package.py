"""流量套餐模型"""
from datetime import datetime
from utils.extensions import db


class Package(db.Model):
    """流量套餐数据模型"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    total_traffic = db.Column(db.BigInteger, nullable=False)  # 总流量（字节）
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 与套餐节点的关联
    nodes = db.relationship('PackageNode', backref='package', lazy=True, cascade='all, delete-orphan')
    
    # 与用户的关联
    users = db.relationship('User', backref='package', lazy=True)

    def __repr__(self):
        return f'<Package {self.name}>'
    
    def to_dict(self):
        """转换为字典格式"""
        return {
            'id': self.id,
            'name': self.name,
            'total_traffic': self.total_traffic,
            'nodes': [node.to_dict() for node in self.nodes], # type: ignore
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S')
        }


class PackageNode(db.Model):
    """套餐节点关联模型"""
    id = db.Column(db.Integer, primary_key=True)
    package_id = db.Column(db.Integer, db.ForeignKey('package.id'), nullable=False)
    board_name = db.Column(db.String(50), nullable=False)  # 节点所属服务器
    inbound_id = db.Column(db.Integer, nullable=False)  # 入站节点ID
    node_name = db.Column(db.String(255), nullable=False)  # 节点名称
    traffic_rate = db.Column(db.Float, default=1.0, nullable=False)  # 流量倍率
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<PackageNode {self.node_name} @ {self.board_name} (ID:{self.inbound_id}, rate: {self.traffic_rate}x)>'
    
    def to_dict(self):
        """转换为字典格式"""
        return {
            'id': self.id,
            'package_id': self.package_id,
            'board_name': self.board_name,
            'inbound_id': self.inbound_id,
            'node_name': self.node_name,
            'traffic_rate': self.traffic_rate
        }
