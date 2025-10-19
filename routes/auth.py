"""认证相关路由"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from datetime import datetime
from extensions import db, logger
from models import User
from utils import check_ip_blocked, record_failed_login, reset_failed_login
from config import Config

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """用户登录"""
    client_ip = request.remote_addr
    
    # 检查IP是否被锁定
    is_blocked, blocked_until = check_ip_blocked(client_ip)
    if is_blocked:
        remaining_time = (blocked_until - datetime.utcnow()).total_seconds() / 60
        flash(f'您的IP已被锁定，请在 {int(remaining_time)} 分钟后重试。', 'error')
        logger.warning(f'被锁定的IP尝试登录: {client_ip}')
        return render_template('login.html', blocked=True)
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # 尝试通过用户名或邮箱查找用户
        user = User.query.filter(
            (User.username == username) | (User.email == username)
        ).first()

        if user and user.check_password(password):
            # 登录成功，重置失败记录
            reset_failed_login(client_ip)
            session['user_id'] = user.id
            session['username'] = user.username
            session['is_admin'] = user.is_admin
            flash(f'欢迎回来，{user.username}！', 'success')
            logger.info(f'用户 {user.username} 登录成功，IP: {client_ip}')
            return redirect(url_for('main.index'))
        else:
            # 登录失败，记录失败次数
            failed_count = record_failed_login(client_ip)
            remaining_attempts = Config.MAX_FAILED_ATTEMPTS - failed_count
            if remaining_attempts > 0:
                flash(f'用户名或密码错误！剩余尝试次数: {remaining_attempts}', 'error')
            else:
                flash('登录失败次数过多，您的IP已被锁定30分钟。', 'error')
            logger.warning(f'登录失败，IP: {client_ip}, 用户名: {username}, 失败次数: {failed_count}')
            return redirect(url_for('auth.login'))

    return render_template('login.html', blocked=False)


@auth_bp.route('/logout')
def logout():
    """用户登出"""
    username = session.get('username', 'Unknown')
    session.clear()
    flash('您已成功登出！', 'success')
    logger.info(f'用户 {username} 已登出')
    return redirect(url_for('auth.login'))


@auth_bp.route('/profile')
def profile():
    """个人资料页面"""
    if 'user_id' not in session:
        flash('请先登录！', 'error')
        return redirect(url_for('auth.login'))
    
    user = db.session.get(User, session['user_id'])
    return render_template('profile.html', user=user)


@auth_bp.route('/change_password_page')
def change_password_page():
    """修改密码页面"""
    if 'user_id' not in session:
        flash('请先登录！', 'error')
        return redirect(url_for('auth.login'))
    
    return render_template('change_password.html')


@auth_bp.route('/change_password', methods=['POST'])
def change_password():
    """修改密码"""
    if 'user_id' not in session:
        flash('请先登录！', 'error')
        return redirect(url_for('auth.login'))
    
    user = db.session.get(User, session['user_id'])
    old_password = request.form.get('old_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    # 验证
    if not old_password or not new_password or not confirm_password:
        flash('所有字段都是必填的！', 'error')
        return redirect(url_for('auth.change_password_page'))
    
    # 验证旧密码
    if not user.check_password(old_password):
        flash('旧密码不正确！', 'error')
        return redirect(url_for('auth.change_password_page'))
    
    # 验证新密码长度
    if len(new_password) < 6:
        flash('新密码长度至少为6位！', 'error')
        return redirect(url_for('auth.change_password_page'))
    
    # 验证两次密码是否一致
    if new_password != confirm_password:
        flash('两次输入的新密码不一致！', 'error')
        return redirect(url_for('auth.change_password_page'))
    
    # 更新密码
    if not user:
        flash('用户不存在！', 'error')
        return redirect(url_for('auth.change_password_page'))

    user.set_password(new_password)
    db.session.commit()
    
    logger.info(f'用户 {user.username} 修改了密码')
    flash('密码修改成功！', 'success')
    return redirect(url_for('auth.profile'))
