"""Flask路由装饰器"""
from functools import wraps
from flask import flash, redirect, url_for, jsonify, request, g
from utils.auth import verify_token


def login_required(f):
    """
    登录验证装饰器
    用于需要用户登录才能访问的路由
    使用JWT token进行验证
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 从cookie中获取token
        token = request.cookies.get('access_token')
        
        if not token:
            # 如果是API请求，返回JSON
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': '未登录'}), 401
            # 如果是页面请求，重定向到登录页（不显示flash消息，因为用户可能只是访问需要登录的页面）
            return redirect(url_for('auth.login'))
        
        # 验证token
        payload = verify_token(token)
        if not payload:
            # token无效或过期
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': '登录已过期，请重新登录'}), 401
            return redirect(url_for('auth.login'))
        
        # 将用户信息存储到g对象中供路由使用
        g.user_id = payload['user_id']
        g.username = payload['username']
        g.is_admin = payload['is_admin']
        
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """
    管理员权限验证装饰器
    用于需要管理员权限才能访问的路由
    自动包含登录验证
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 从cookie中获取token
        token = request.cookies.get('access_token')
        
        if not token:
            # 如果是API请求，返回JSON
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': '未登录'}), 401
            # 如果是页面请求，重定向到登录页
            return redirect(url_for('auth.login'))
        
        # 验证token
        payload = verify_token(token)
        if not payload:
            # token无效或过期
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': '登录已过期，请重新登录'}), 401
            return redirect(url_for('auth.login'))
        
        # 将用户信息存储到g对象中供路由使用
        g.user_id = payload['user_id']
        g.username = payload['username']
        g.is_admin = payload['is_admin']
        
        # 检查是否为管理员
        if not payload.get('is_admin'):
            # 如果是API请求，返回JSON
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': '权限不足'}), 403
            # 如果是页面请求，显示错误并重定向
            flash('只有管理员可以访问此页面！', 'error')
            return redirect(url_for('main.index'))
        
        return f(*args, **kwargs)
    return decorated_function
