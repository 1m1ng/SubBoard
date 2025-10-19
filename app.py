"""SubBoard应用主文件 - 模块化版本"""
import os
from flask import Flask
from waitress import serve
from extensions import db, logger
from config import config
from models import User
from utils import generate_random_password, register_template_filters
from routes import auth_bp, admin_bp, subscription_bp, servers_bp, mihomo_bp, main_bp


def create_app(config_name='default'):
    """
    应用工厂函数
    
    Args:
        config_name: 配置名称 ('development', 'production', 'default')
        
    Returns:
        Flask: Flask应用实例
    """
    app = Flask(__name__)
    
    # 加载配置
    app.config.from_object(config[config_name])
    
    # 初始化扩展
    db.init_app(app)
    
    # 注册模板过滤器和上下文处理器
    register_template_filters(app)
    
    # 注册蓝图
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(subscription_bp)
    app.register_blueprint(servers_bp)
    app.register_blueprint(mihomo_bp)
    
    # 初始化数据库
    with app.app_context():
        init_database()
    
    return app


def init_database():
    """初始化数据库"""
    db.create_all()
    
    # 检查是否已存在管理员账号
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        # 生成随机密码
        admin_password = generate_random_password(16)
        
        # 创建默认管理员账号
        admin = User()
        admin.username = 'admin'
        admin.email = 'admin@system.local'
        admin.is_admin = True
        admin.set_password(admin_password)
        
        db.session.add(admin)
        db.session.commit()
        
        # 记录到日志
        logger.info('='*60)
        logger.info('数据库初始化成功！')
        logger.info('默认管理员账号已创建：')
        logger.info(f'  用户名: admin')
        logger.info(f'  密码: {admin_password}')
        logger.info('请妥善保管此密码，建议登录后立即修改！')
        logger.info('='*60)
    else:
        # 检查是否有管理员账号
        admin_count = User.query.filter_by(is_admin=True).count()
        if admin_count == 0:
            logger.warning("警告：数据库中没有管理员账号！")


if __name__ == '__main__':
    # 确定运行环境
    env = os.getenv('FLASK_ENV', 'production')
    
    # 创建应用
    app = create_app(env if env in config else 'default')
    
    # 使用 Waitress WSGI 服务器（支持 Windows 和 Linux）
    host = app.config['HOST']
    port = app.config['PORT']
    threads = app.config['THREADS']
    
    logger.info("启动 Waitress WSGI 服务器...")
    logger.info(f"访问地址: http://{host}:{port}")
    logger.info(f"运行环境: {env}")
    
    serve(app, host=host, port=port, threads=threads)
