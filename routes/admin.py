"""管理员路由"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from utils.extensions import db, logger
from models import User, IPBlock, Package, PackageNode
from utils.decorators import admin_required
from datetime import datetime, timedelta
from service.xui_manager import get_xui_manager

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.route('/')
@admin_required
def admin():
    """管理员页面：用户管理"""
    users = User.query.all()
    blocked_ips = IPBlock.query.filter(IPBlock.blocked_until.isnot(None)).all()
    packages = Package.query.all()
    return render_template('admin.html', users=users, blocked_ips=blocked_ips, packages=packages)


@admin_bp.route('/create_user', methods=['POST'])
@admin_required
def create_user():
    """管理员：创建用户"""
    
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')
    is_admin = request.form.get('is_admin') == 'on'
    package_id = request.form.get('package_id')
    package_expire_time = request.form.get('package_expire_time')
    next_reset_time = request.form.get('next_reset_time')
    
    # 验证
    if not username or not email or not password:
        flash('所有字段都是必填的！', 'error')
        return redirect(url_for('admin.admin'))
    
    if len(password) < 6:
        flash('密码长度至少为6位！', 'error')
        return redirect(url_for('admin.admin'))
    
    # 检查用户是否已存在
    if User.query.filter_by(username=username).first():
        flash('用户名已存在！', 'error')
        return redirect(url_for('admin.admin'))
    
    if User.query.filter_by(email=email).first():
        flash('邮箱已被注册！', 'error')
        return redirect(url_for('admin.admin'))
    
    # 创建新用户
    user = User(username=username, email=email, is_admin=is_admin) # type: ignore
    user.set_password(password)
    
    # 设置套餐信息
    if package_id:
        from datetime import datetime
        user.package_id = int(package_id)
        if package_expire_time:
            user.package_expire_time = datetime.fromisoformat(package_expire_time)
        if next_reset_time:
            user.next_reset_time = datetime.fromisoformat(next_reset_time)
        elif package_expire_time:
            # Calculate next reset time based on the expiration date's month and day
            expire_date = datetime.fromisoformat(package_expire_time)
            current_date = datetime.now()
            next_month = current_date.month % 12 + 1
            year_increment = 1 if next_month == 1 else 0
            try:
                # 更新 next_reset_time 的小时和分钟以匹配到期时间
                user.next_reset_time = current_date.replace(
                    year=current_date.year + year_increment, month=next_month, day=expire_date.day,
                    hour=expire_date.hour, minute=expire_date.minute
                )
            except ValueError:
                # 如果日期无效，则使用下个月的最后一天，并设置相同的小时和分钟
                last_day_of_next_month = (current_date.replace(
                    year=current_date.year + year_increment, month=next_month, day=1
                ) - timedelta(days=1)).day
                user.next_reset_time = current_date.replace(
                    year=current_date.year + year_increment, month=next_month, day=last_day_of_next_month,
                    hour=expire_date.hour, minute=expire_date.minute
                )
        else:
            user.next_reset_time = None
    
    db.session.add(user)
    db.session.commit()
    
    # 如果分配了套餐，添加用户到套餐节点
    if package_id:
        xui_manager = get_xui_manager()
        if xui_manager and not xui_manager.add_client_to_package_nodes(user):
            logger.warning(f'添加用户 {username} 到套餐节点时部分失败')
            flash(f'用户 {username} 创建成功，但添加到部分节点失败！', 'warning')
        elif xui_manager:
            logger.info(f'成功添加用户 {username} 到套餐所有节点')
        else:
            logger.warning(f'XUI管理器未初始化，无法添加用户到套餐节点')
    
    logger.info(f'管理员创建了新用户: {username} (Email: {email}), 管理员权限: {is_admin}')
    flash(f'用户 {username} 创建成功！', 'success')
    return redirect(url_for('admin.admin'))


@admin_bp.route('/edit_user/<int:user_id>', methods=['POST'])
@admin_required
def edit_user(user_id):
    """管理员：编辑用户"""
    user = db.session.get(User, user_id)
    if not user:
        flash('用户不存在！', 'error')
        return redirect(url_for('admin.admin'))
    
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')
    is_admin = request.form.get('is_admin') == 'on'
    package_id = request.form.get('package_id')
    package_expire_time = request.form.get('package_expire_time')
    next_reset_time = request.form.get('next_reset_time')
    
    # 验证
    if not username or not email:
        flash('用户名和邮箱不能为空！', 'error')
        return redirect(url_for('admin.admin'))
    
    # 检查用户名是否被其他用户占用
    existing_user = User.query.filter_by(username=username).first()
    if existing_user and existing_user.id != user_id:
        flash('用户名已存在！', 'error')
        return redirect(url_for('admin.admin'))
    
    # 检查邮箱是否被其他用户占用
    existing_email = User.query.filter_by(email=email).first()
    if existing_email and existing_email.id != user_id:
        flash('邮箱已被注册！', 'error')
        return redirect(url_for('admin.admin'))
    
    # 更新用户信息
    user.username = username
    user.email = email
    user.is_admin = is_admin
    
    # 如果提供了新密码，则更新密码
    if password and len(password) >= 6:
        user.set_password(password)
    elif password and len(password) < 6:
        flash('密码长度至少为6位，密码未更新！', 'error')
    
    # 记录原套餐ID
    old_package_id = user.package_id
    
    # 更新套餐信息
    if package_id:
        user.package_id = int(package_id)
        if package_expire_time:
            user.package_expire_time = datetime.fromisoformat(package_expire_time)
        else:
            user.package_expire_time = None
        if next_reset_time:
            user.next_reset_time = datetime.fromisoformat(next_reset_time)
        elif package_expire_time:
            # Calculate next reset time based on the expiration date's month and day
            expire_date = datetime.fromisoformat(package_expire_time)
            current_date = datetime.now()
            next_month = current_date.month % 12 + 1
            year_increment = 1 if next_month == 1 else 0
            try:
                # 更新 next_reset_time 的小时和分钟以匹配到期时间
                user.next_reset_time = current_date.replace(
                    year=current_date.year + year_increment, month=next_month, day=expire_date.day,
                    hour=expire_date.hour, minute=expire_date.minute
                )
            except ValueError:
                # 如果日期无效，则使用下个月的最后一天，并设置相同的小时和分钟
                last_day_of_next_month = (current_date.replace(
                    year=current_date.year + year_increment, month=next_month, day=1
                ) - timedelta(days=1)).day
                user.next_reset_time = current_date.replace(
                    year=current_date.year + year_increment, month=next_month, day=last_day_of_next_month,
                    hour=expire_date.hour, minute=expire_date.minute
                )
        else:
            user.next_reset_time = None
    else:
        user.package_id = None
        user.package_expire_time = None
        user.next_reset_time = None
    
    db.session.commit()
    
    # 检查套餐是否发生变化
    if old_package_id != user.package_id:
        xui_manager = get_xui_manager()
        if not xui_manager:
            logger.warning(f'XUI管理器未初始化，无法处理套餐节点变更')
            flash(f'用户 {username} 信息已更新，但XUI管理器未初始化！', 'warning')
        else:
            # 先从旧套餐节点删除用户
            if old_package_id:
                logger.info(f'用户 {username} 套餐变更，从旧套餐 {old_package_id} 节点删除客户端')
                if not xui_manager.delete_client_from_package_nodes(email, old_package_id):
                    logger.warning(f'从旧套餐节点删除用户 {username} 时部分失败')
            
            # 再添加到新套餐节点
            if user.package_id:
                logger.info(f'用户 {username} 套餐变更，添加到新套餐 {user.package_id} 节点')
                if not xui_manager.add_client_to_package_nodes(user):
                    logger.warning(f'添加用户 {username} 到新套餐节点时部分失败')
                    flash(f'用户 {username} 信息已更新，但添加到部分节点失败！', 'warning')
                else:
                    flash(f'用户 {username} 信息已更新！', 'success')
            else:
                flash(f'用户 {username} 信息已更新！', 'success')
    else:
        flash(f'用户 {username} 信息已更新！', 'success')
    
    logger.info(f'管理员编辑了用户: {username}')
    return redirect(url_for('admin.admin'))


@admin_bp.route('/delete_user/<int:user_id>')
@admin_required
def delete_user(user_id):
    """管理员：删除用户"""
    # 不能删除自己
    if user_id == g.user_id:
        flash('不能删除自己的账号！', 'error')
        return redirect(url_for('admin.admin'))
    
    user = db.session.get(User, user_id)
    if user:
        username = user.username
        db.session.delete(user)
        db.session.commit()
        logger.info(f'管理员删除了用户: {username}')
        flash(f'用户 {username} 已被删除！', 'success')
    else:
        flash('用户不存在！', 'error')
    
    return redirect(url_for('admin.admin'))


@admin_bp.route('/unblock_ip/<int:ip_id>')
@admin_required
def unblock_ip(ip_id):
    """管理员：解锁IP"""
    ip_record = db.session.get(IPBlock, ip_id)
    if ip_record:
        ip_address = ip_record.ip_address
        ip_record.blocked_until = None
        ip_record.failed_attempts = 0
        db.session.commit()
        logger.info(f'管理员解锁了IP: {ip_address}')
        flash(f'IP {ip_address} 已解锁！', 'success')
    else:
        flash('IP记录不存在！', 'error')
    
    return redirect(url_for('admin.admin'))


@admin_bp.route('/inbounds')
@admin_required
def inbounds():
    """管理员：入站节点信息"""
    xui_manager = get_xui_manager()
    if not xui_manager:
        flash('XUI管理器未初始化！', 'error')
        return redirect(url_for('admin.admin'))

    # 从数据库中获取所有套餐的节点信息
    packages: list[Package] = Package.query.all()
    all_nodes: dict[tuple[str, int], PackageNode] = {}
    for package in packages:
        nodes: list[PackageNode] = package.nodes  # type: ignore
        for node in nodes:
            node_key = (node.board_name, node.inbound_id)
            if node_key not in all_nodes:
                all_nodes[node_key] = node

    # 组织数据：按面板分组，并为每个入站节点添加客户端信息
    inbounds_data = []
    for node_key, node in all_nodes.items():
        server = xui_manager.servers.get(node.board_name)
        if not server:
            continue
        inbound = server.get_inbound(node.inbound_id)
        if not inbound:
            continue
        # 获取节点详细信息（包含客户端统计）
        inbound_id = inbound.get('id')

        # 获取客户端统计信息
        client_stats = inbound.get('clientStats', [])

        # 整理客户端数据
        clients_data = []
        if client_stats:
            for client in client_stats:
                email = client.get('email', '')
                up = client.get('up', 0)
                down = client.get('down', 0)
                total_traffic = up + down
                enable = client.get('enable', False)

                clients_data.append({
                    'email': email,
                    'up': up,
                    'down': down,
                    'total': total_traffic,
                    'enable': enable
                })

        inbounds_data.append({
            'board_name': node.board_name,
            'server': server.server,
            'inbound_id': inbound_id,
            'remark': inbound.get('remark', ''),
            'protocol': inbound.get('protocol', ''),
            'port': inbound.get('port', ''),
            'clients': clients_data,
            'client_count': len(clients_data)
        })

    return render_template('inbounds.html', inbounds=inbounds_data)
