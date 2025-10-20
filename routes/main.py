"""主页路由"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, g
from extensions import db, logger
from models import User, Package
from utils.cache import inbounds_cache
from utils.xui import get_xui_manager
from utils.decorators import login_required, admin_required
from datetime import datetime
import time

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
@login_required
def index():
    """首页"""
    user = db.session.get(User, g.user_id)
    if not user:
        flash('用户不存在！', 'error')
        return redirect(url_for('auth.login'))

    # 生成订阅URL
    subscription_url = None
    if user.subscription_token:
        subscription_url = url_for('subscription.subscription', token=user.subscription_token, _external=True, _scheme='https')
    elif user.email:
        # 如果还没有Token，自动生成一个
        user.generate_subscription_token()
        db.session.commit()
        subscription_url = url_for('subscription.subscription', token=user.subscription_token, _external=True, _scheme='https')

    # 获取用户套餐信息
    package = None
    if user.package_id:
        package = db.session.get(Package, user.package_id)

    # 首次加载时不获取节点信息，由前端异步加载
    return render_template('index.html', user=user, nodes=None, subscription_url=subscription_url, package=package, now=datetime.now())


@main_bp.route('/refresh_token', methods=['POST'])
@login_required
def refresh_token():
    """刷新订阅Token"""
    user = db.session.get(User, g.user_id)
    
    # 检查用户是否有套餐
    if not user.package_id: # type: ignore
        flash('您还没有流量套餐，无法使用订阅功能！', 'error')
        return redirect(url_for('main.index'))
    
    # 检查套餐是否过期
    if not user.package_expire_time or user.package_expire_time <= datetime.now(): # type: ignore
        flash('您的流量套餐已过期，无法刷新订阅Token！', 'error')
        return redirect(url_for('main.index'))
    
    user.generate_subscription_token() # type: ignore
    db.session.commit()
    
    logger.info(f'用户 {user.username} 刷新了订阅Token') # type: ignore
    flash('订阅Token已刷新！', 'success')
    return redirect(url_for('main.index'))


@main_bp.route('/nodes')
@login_required
def nodes():
    """节点信息页面（管理员看所有节点，普通用户看套餐内节点）"""
    user = db.session.get(User, g.user_id)
    if not user:
        flash('用户不存在！', 'error')
        return redirect(url_for('auth.login'))
    
    return render_template('nodes.html', user=user)


@main_bp.route('/api/inbounds')
@login_required
def get_inbounds():
    """API：获取节点信息（管理员获取所有节点，普通用户获取套餐内节点）"""
    user = db.session.get(User, g.user_id)
    if not user:
        return jsonify({'error': '用户不存在'}), 404
    
    # 管理员：返回所有节点
    if user.is_admin:
        # 检查聚合缓存
        cached_data, is_cached = inbounds_cache.get_aggregated()
        if is_cached:
            logger.info(f'使用缓存的节点数据（管理员）- 用户: {user.username}')
            return jsonify({
                'inbounds': cached_data,
                'cached': True
            })
        
        # 缓存不存在或已过期，重新获取数据
        logger.info(f'获取新的节点数据（管理员）- 用户: {user.username}')
        manager = get_xui_manager()
        
        if not manager:
            return jsonify({'error': 'XUI管理器未初始化'}), 503
        
        # 获取所有节点（会自动更新各面板缓存）
        inbounds = manager.get_all_inbounds()
        
        if inbounds:
            # 更新聚合缓存
            inbounds_cache.set_aggregated(inbounds)
            return jsonify({
                'inbounds': inbounds,
                'cached': False
            })
        
        return jsonify({'error': '无法获取节点信息'}), 500
    
    # 普通用户：只返回套餐内的节点
    else:
        # 检查用户是否有套餐
        if not user.package_id:
            logger.info(f'用户无套餐 - 用户: {user.username}')
            return jsonify({
                'inbounds': [],
                'message': '您当前没有流量套餐'
            })
        
        # 获取用户套餐信息
        package = db.session.get(Package, user.package_id)
        if not package:
            logger.warning(f'用户套餐不存在 - 用户: {user.username}, package_id: {user.package_id}')
            return jsonify({
                'inbounds': [],
                'error': '套餐不存在'
            }), 404
        
        # 获取套餐关联的节点
        from models import PackageNode
        package_nodes = PackageNode.query.filter_by(package_id=package.id).all()
        
        if not package_nodes:
            logger.info(f'套餐无关联节点 - 用户: {user.username}, package: {package.name}')
            return jsonify({
                'inbounds': [],
                'message': '您的套餐暂无可用节点'
            })
        
        # 从缓存中获取所有节点
        cached_data, is_cached = inbounds_cache.get_aggregated()
        
        if not cached_data:
            # 如果缓存为空，尝试重新获取
            manager = get_xui_manager()
            if manager:
                cached_data = manager.get_all_inbounds()
                if cached_data:
                    inbounds_cache.set_aggregated(cached_data)
        
        if not cached_data:
            return jsonify({'error': '无法获取节点信息'}), 500
        
        # 过滤出用户套餐内的节点
        user_inbounds = []
        for inbound in cached_data:
            board_name = inbound.get('board_name')
            node_name = inbound.get('remark') or inbound.get('tag', '')
            
            # 检查该节点是否在用户套餐中
            for package_node in package_nodes:
                if package_node.board_name == board_name and package_node.node_name == node_name:
                    # 添加流量倍率信息
                    inbound_copy = inbound.copy()
                    inbound_copy['traffic_rate'] = package_node.traffic_rate
                    user_inbounds.append(inbound_copy)
                    break
        
        logger.info(f'返回用户套餐节点 - 用户: {user.username}, 节点数: {len(user_inbounds)}')
        return jsonify({
            'inbounds': user_inbounds,
            'cached': is_cached,
            'package_name': package.name
        })
