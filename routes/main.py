"""主页路由"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from extensions import db, logger
from models import User
from utils.cache import nodes_cache
from utils.xui import get_xui_manager
import time

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    """首页"""
    if 'user_id' in session:
        user = db.session.get(User, session['user_id'])
        if not user:
            flash('用户不存在！', 'error')
            return redirect(url_for('auth.login'))

        # 生成订阅URL
        subscription_url = None
        if user.subscription_token:
            subscription_url = url_for('subscription.subscription', token=user.subscription_token, _external=True)
        elif user.email:
            # 如果还没有Token，自动生成一个
            user.generate_subscription_token()
            db.session.commit()
            subscription_url = url_for('subscription.subscription', token=user.subscription_token, _external=True)

        # 首次加载时不获取节点信息，由前端异步加载
        return render_template('index.html', user=user, nodes=None, subscription_url=subscription_url)
    return redirect(url_for('auth.login'))


@main_bp.route('/api/nodes')
def get_nodes():
    """API：获取节点信息（带缓存）"""
    if 'user_id' not in session:
        return jsonify({'error': '未登录'}), 401
    
    user = db.session.get(User, session['user_id'])
    if not user:
        return jsonify({'error': '用户不存在'}), 404
    
    user_id = user.id
    
    # 检查是否强制刷新（通过查询参数 _= 时间戳来判断）
    force_refresh = request.args.get('_') is not None
    
    # 检查缓存
    cached_data, is_cached, cache_age = nodes_cache.get(user_id, force_refresh)
    if is_cached:
        logger.info(f'使用缓存数据 - 用户: {user.username}, 缓存年龄: {cache_age}秒')
        return jsonify({
            'nodes': cached_data,
            'cached': True,
            'cache_age': cache_age
        })
    
    # 缓存不存在、已过期或强制刷新，重新获取数据
    logger.info(f'获取新数据 - 用户: {user.username}, 强制刷新: {force_refresh}')
    nodes_info = []
    manager = get_xui_manager()
    if user.email and manager:
        nodes_info = manager.get_all_traffic_info(user.email)
    
    # 更新缓存
    nodes_cache.set(user_id, nodes_info)
    
    return jsonify({
        'nodes': nodes_info,
        'cached': False,
        'cache_age': 0
    })


@main_bp.route('/refresh_token', methods=['POST'])
def refresh_token():
    """刷新订阅Token"""
    if 'user_id' not in session:
        flash('请先登录！', 'error')
        return redirect(url_for('auth.login'))
    
    user = db.session.get(User, session['user_id'])
    user.generate_subscription_token()
    db.session.commit()
    
    logger.info(f'用户 {user.username} 刷新了订阅Token')
    flash('订阅Token已刷新！', 'success')
    return redirect(url_for('main.index'))
