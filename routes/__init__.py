"""路由模块"""
from .auth import auth_bp
from .admin import admin_bp
from .subscription import subscription_bp
from .servers import servers_bp
from .mihomo import mihomo_bp
from .main import main_bp
from .packages import packages_bp

__all__ = ['auth_bp', 'admin_bp', 'subscription_bp', 'servers_bp', 'mihomo_bp', 'main_bp', 'packages_bp']
