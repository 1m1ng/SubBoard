"""Flask路由装饰器"""
from functools import wraps
from flask import session, flash, redirect, url_for, jsonify, request


def login_required(f):
    """
    登录验证装饰器
    用于需要用户登录才能访问的路由
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            # 如果是API请求，返回JSON
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': '未登录'}), 401
            # 如果是页面请求，重定向到登录页
            flash('请先登录！', 'error')
            return redirect(url_for('auth.login'))
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
        # 首先检查是否登录
        if 'user_id' not in session:
            # 如果是API请求，返回JSON
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': '未登录'}), 401
            # 如果是页面请求，重定向到登录页
            flash('请先登录！', 'error')
            return redirect(url_for('auth.login'))
        
        # 检查是否为管理员
        if not session.get('is_admin'):
            # 如果是API请求，返回JSON
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': '权限不足'}), 403
            # 如果是页面请求，显示错误并重定向
            flash('只有管理员可以访问此页面！', 'error')
            return redirect(url_for('main.index'))
        
        return f(*args, **kwargs)
    return decorated_function
