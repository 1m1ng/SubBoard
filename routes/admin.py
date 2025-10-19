"""管理员路由"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from extensions import db, logger
from models import User, IPBlock
from utils import generate_random_password

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.route('/')
def admin():
    """管理员页面：用户管理"""
    if 'user_id' not in session or not session.get('is_admin'):
        flash('只有管理员可以访问此页面！', 'error')
        return redirect(url_for('main.index'))
    
    users = User.query.all()
    blocked_ips = IPBlock.query.filter(IPBlock.blocked_until.isnot(None)).all()
    return render_template('admin.html', users=users, blocked_ips=blocked_ips)


@admin_bp.route('/create_user', methods=['POST'])
def create_user():
    """管理员：创建用户"""
    if 'user_id' not in session or not session.get('is_admin'):
        flash('只有管理员可以创建用户！', 'error')
        return redirect(url_for('main.index'))
    
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')
    is_admin = request.form.get('is_admin') == 'on'
    
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
    user = User(username=username, email=email, is_admin=is_admin)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    
    logger.info(f'管理员创建了新用户: {username}, 管理员权限: {is_admin}')
    flash(f'用户 {username} 创建成功！', 'success')
    return redirect(url_for('admin.admin'))


@admin_bp.route('/edit_user/<int:user_id>', methods=['POST'])
def edit_user(user_id):
    """管理员：编辑用户"""
    if 'user_id' not in session or not session.get('is_admin'):
        flash('只有管理员可以编辑用户！', 'error')
        return redirect(url_for('main.index'))
    
    user = db.session.get(User, user_id)
    if not user:
        flash('用户不存在！', 'error')
        return redirect(url_for('admin.admin'))
    
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')
    is_admin = request.form.get('is_admin') == 'on'
    
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
    
    db.session.commit()
    
    logger.info(f'管理员编辑了用户: {username}')
    flash(f'用户 {username} 信息已更新！', 'success')
    return redirect(url_for('admin.admin'))


@admin_bp.route('/delete_user/<int:user_id>')
def delete_user(user_id):
    """管理员：删除用户"""
    if 'user_id' not in session or not session.get('is_admin'):
        flash('只有管理员可以删除用户！', 'error')
        return redirect(url_for('main.index'))
    
    # 不能删除自己
    if user_id == session['user_id']:
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
def unblock_ip(ip_id):
    """管理员：解锁IP"""
    if 'user_id' not in session or not session.get('is_admin'):
        flash('只有管理员可以解锁IP！', 'error')
        return redirect(url_for('main.index'))

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
