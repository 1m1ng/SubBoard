"""Flask上下文处理器 - 为模板提供全局变量"""
from flask import request
from utils import verify_token


def register_context_processors(app):
    """注册上下文处理器"""
    
    @app.context_processor
    def inject_user_info():
        """
        为所有模板注入用户信息
        从JWT token中提取用户信息，替代session
        """
        # 从cookie中获取token
        token = request.cookies.get('access_token')
        
        # 默认值
        user_info = {
            'user_id': None,
            'username': None,
            'is_admin': False,
            'is_authenticated': False
        }
        
        # 如果有token，尝试验证并提取信息
        if token:
            payload = verify_token(token)
            if payload:
                user_info = {
                    'user_id': payload.get('user_id'),
                    'username': payload.get('username'),
                    'is_admin': payload.get('is_admin', False),
                    'is_authenticated': True
                }
        
        return user_info
