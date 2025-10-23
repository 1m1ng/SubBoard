"""主页路由"""
from flask import Blueprint, render_template, redirect, url_for, flash, jsonify, g
from utils.extensions import db, logger
from models import User, Package
from service.xui_manager import get_xui_manager
from utils.decorators import login_required
from datetime import datetime
from models import PackageNode

main_bp = Blueprint('main', __name__)


# 修改首页流量获取逻辑，改为使用 xui_manager 的 get_used_traffic 方法
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

    # 获取用户流量使用情况
    xui_manager = get_xui_manager()
    used_traffic = None
    if xui_manager:
        traffic_data = xui_manager.get_used_traffic(user)
        if traffic_data:
            used_traffic = traffic_data.get('total', 0)

    # 首次加载时不获取节点信息，由前端异步加载
    return render_template('index.html', user=user, nodes=None, subscription_url=subscription_url, package=package, now=datetime.now(), used_traffic=used_traffic)


@main_bp.route('/refresh_token', methods=['POST'])
@login_required
def refresh_token():
    """刷新订阅Token（同时刷新套餐内所有节点的UUID或密码）"""
    user: User = db.session.get(User, g.user_id) # type: ignore
    
    # 检查用户是否有套餐
    if not user.package_id:
        flash('您还没有流量套餐，无法使用订阅功能！', 'error')
        return redirect(url_for('main.index'))
    
    # 检查套餐是否过期（允许无限期套餐）
    if user.package_expire_time is not None and user.package_expire_time <= datetime.now():
        flash('您的流量套餐已过期，无法刷新订阅Token！', 'error')
        return redirect(url_for('main.index'))
    
    # 获取套餐信息
    package = db.session.get(Package, user.package_id)
    if not package:
        flash('套餐不存在！', 'error')
        return redirect(url_for('main.index'))
    
    # 获取XUI管理器
    xui_manager = get_xui_manager()
    if not xui_manager:
        flash('XUI管理器未初始化！', 'error')
        return redirect(url_for('main.index'))
    
    xui_manager.refresh_client_from_package_nodes(user)
    
    # 刷新订阅Token
    user.generate_subscription_token()
    db.session.commit()
    
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
    package: Package = Package.query.get(user.package_id) # type: ignore
    if not package:
        logger.warning(f'用户套餐不存在 - 用户: {user.username}, package_id: {user.package_id}')
        return jsonify({
            'inbounds': [],
            'error': '套餐不存在'
        }), 404
    
    nodes: list[PackageNode] = package.nodes  # type: ignore
    if not nodes:
        logger.info(f'套餐无关联节点 - 用户: {user.username}, package: {package.name}')
        return jsonify({
            'inbounds': [],
            'message': '您的套餐暂无可用节点'
        })
    
    # 获取XUI管理器
    xui_manager = get_xui_manager()
    if not xui_manager:
        return jsonify({'error': 'XUI管理器未初始化'}), 503
    
    user_inbounds = []
    
    for node in nodes:
        server = xui_manager.servers.get(node.board_name)
        if not server:
            logger.warning(f'节点服务器未找到 - 节点: {node.board_name}')
            continue
        
        inbound = server.get_inbound(node.inbound_id)
        if not inbound:
            logger.warning(f'入站配置未找到 - 节点: {node.board_name}, 入站ID: {node.inbound_id}')
            continue
        
        stat = server.get_client_traffic(node.inbound_id, user.email)
        if not stat:
            logger.warning(f'获取用户流量失败 - 用户: {user.username}, 节点: {node.board_name}, 入站ID: {node.inbound_id}')
            stat = {'up': 0, 'down': 0}
        
        user_inbounds.append({
            'board_name': node.board_name,
            'remark': inbound.get('remark', ''),
            'protocol': inbound.get('protocol', ''),
            'enable': inbound.get('enable', False),
            'traffic_rate': node.traffic_rate,
            'up': stat.get('up', 0),
            'down': stat.get('down', 0),
            'total': stat.get('up', 0) + stat.get('down', 0)
        })
    
    return jsonify({
        'inbounds': user_inbounds,
        'package_name': package.name
    })
