"""主页路由"""
from flask import Blueprint, render_template, redirect, url_for, flash, jsonify, g
from extensions import db, logger
from models import User, Package
from utils.cache import inbounds_cache
from utils.xui import get_xui_manager
from utils.decorators import login_required
from datetime import datetime

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
    
    # 检查套餐是否过期（允许无限期套餐）
    if user.package_expire_time is not None and user.package_expire_time <= datetime.now(): # type: ignore
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
    """节点信息页面（显示用户套餐内的节点及使用情况）"""
    user = db.session.get(User, g.user_id)
    if not user:
        flash('用户不存在！', 'error')
        return redirect(url_for('auth.login'))
    
    return render_template('nodes.html', user=user)


@main_bp.route('/api/inbounds')
@login_required
def get_inbounds():
    """API：获取节点信息和用户在各节点的流量使用情况"""
    user = db.session.get(User, g.user_id)
    if not user:
        return jsonify({'error': '用户不存在'}), 404
    
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
    
    # 获取XUI管理器
    manager = get_xui_manager()
    if not manager:
        return jsonify({'error': 'XUI管理器未初始化'}), 503
    
    # 获取用户在各节点的流量使用情况
    user_traffic_by_node = {}
    if user.email:
        for board_name, xui_client in manager.clients.items():
            try:
                traffic_list = xui_client.get_client_traffic(user.email)
                for traffic_info in traffic_list:
                    node_name = traffic_info.get('nodeName', '')
                    user_traffic_by_node[f"{board_name}|{node_name}"] = {
                        'up': traffic_info.get('up', 0),
                        'down': traffic_info.get('down', 0),
                        'total': traffic_info.get('total', 0)
                    }
            except Exception as e:
                logger.error(f'获取用户流量失败 - board: {board_name}, user: {user.email}, error: {str(e)}')
    
    # 从缓存中获取所有节点信息
    cached_data, is_cached = inbounds_cache.get_aggregated()
    
    if not cached_data:
        # 如果缓存为空，尝试重新获取
        cached_data = manager.get_all_inbounds()
        if cached_data:
            inbounds_cache.set_aggregated(cached_data)
    
    if not cached_data:
        return jsonify({'error': '无法获取节点信息'}), 500
    
    # 过滤出用户套餐内的节点并附加用户流量信息
    user_inbounds = []
    for inbound in cached_data:
        board_name = inbound.get('board_name')
        inbound_id = inbound.get('id')
        node_name = inbound.get('remark') or inbound.get('tag', '')
        
        # 检查该节点是否在用户套餐中（使用 board_name 和 inbound_id 匹配）
        for package_node in package_nodes:
            if package_node.board_name == board_name and package_node.inbound_id == inbound_id:
                # 获取用户在此节点的流量使用情况
                node_key = f"{board_name}|{node_name}"
                user_traffic = user_traffic_by_node.get(node_key, {'up': 0, 'down': 0, 'total': 0})
                
                # 只返回前端需要的安全信息，不泄露节点配置
                safe_inbound = {
                    'id': inbound_id,
                    'board_name': board_name,
                    'remark': node_name,
                    'protocol': inbound.get('protocol', ''),
                    'enable': inbound.get('enable', False),
                    'traffic_rate': package_node.traffic_rate,
                    # 用户在此节点的流量使用情况
                    'up': user_traffic['up'],
                    'down': user_traffic['down'],
                    'total': user_traffic['total']
                }
                
                user_inbounds.append(safe_inbound)
                break
    
    logger.info(f'返回用户套餐节点 - 用户: {user.username}, 节点数: {len(user_inbounds)}')
    return jsonify({
        'inbounds': user_inbounds,
        'cached': is_cached,
        'package_name': package.name
    })
