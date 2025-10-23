"""服务器管理路由"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from datetime import datetime
from utils.extensions import db, logger
from models import ServerConfig, PackageNode
from service.xui_manager import reload_xui_manager
from utils.decorators import admin_required

servers_bp = Blueprint('servers', __name__, url_prefix='/servers')


@servers_bp.route('/')
@admin_required
def servers():
    """服务器管理页面"""
    # 从数据库读取服务器配置
    server_configs = ServerConfig.query.all()
    boards = {server.board_name: server.to_dict() for server in server_configs}
    
    return render_template('servers.html', boards=boards)


@servers_bp.route('/add', methods=['POST'])
@admin_required
def add_server():
    """添加服务器"""
    
    board_name = request.form.get('board_name')
    server = request.form.get('server')
    port = request.form.get('port')
    path = request.form.get('path')
    sub_path = request.form.get('sub_path', 'sub0').strip()
    username = request.form.get('username')
    password = request.form.get('password')
    
    # 验证
    if not all([board_name, server, port, path, username, password]):
        flash('所有字段都是必填的！', 'error')
        return redirect(url_for('servers.servers'))
    
    try:
        port = int(port) if port else None
    except ValueError:
        flash('端口必须是数字！', 'error')
        return redirect(url_for('servers.servers'))

    # 检查是否已存在
    if ServerConfig.query.filter_by(board_name=board_name).first():
        flash(f'服务器 {board_name} 已存在！', 'error')
        return redirect(url_for('servers.servers'))
    
    # 添加新服务器
    new_server = ServerConfig(board_name=board_name, server=server, port=port, path=path, sub_path=sub_path, username=username, password=password)  # type: ignore
    
    try:
        db.session.add(new_server)
        db.session.commit()
        
        # 重新加载配置
        reload_xui_manager()
        
        logger.info(f'管理员添加了服务器: {board_name}')
        flash(f'服务器 {board_name} 添加成功！', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"添加服务器失败: {str(e)}")
        flash('添加服务器失败！', 'error')
    
    return redirect(url_for('servers.servers'))


@servers_bp.route('/edit/<board_name>', methods=['POST'])
@admin_required
def edit_server(board_name):
    """编辑服务器"""
    server = request.form.get('server')
    port = request.form.get('port')
    path = request.form.get('path')
    sub_path = request.form.get('sub_path', 'sub0').strip()
    username = request.form.get('username')
    password = request.form.get('password')
    
    # 验证
    if not all([server, port, path, username]):
        flash('必填字段不能为空！', 'error')
        return redirect(url_for('servers.servers'))
    
    try:
        port = int(port) if port else None
    except ValueError:
        flash('端口必须是数字！', 'error')
        return redirect(url_for('servers.servers'))

    # 查找服务器配置
    server_config = ServerConfig.query.filter_by(board_name=board_name).first()
    if not server_config:
        flash(f'服务器 {board_name} 不存在！', 'error')
        return redirect(url_for('servers.servers'))

    # 更新服务器配置
    server_config.server = server
    server_config.port = port
    server_config.path = path
    server_config.sub_path = sub_path
    server_config.username = username
    if password:  # 只有提供了新密码才更新
        server_config.password = password
    server_config.updated_at = datetime.utcnow()
    
    try:
        db.session.commit()
        
        # 重新加载配置
        reload_xui_manager()
        
        logger.info(f'管理员编辑了服务器: {board_name}')
        flash(f'服务器 {board_name} 更新成功！', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"更新服务器失败: {str(e)}")
        flash('更新服务器失败！', 'error')
    
    return redirect(url_for('servers.servers'))


@servers_bp.route('/delete/<board_name>')
@admin_required
def delete_server(board_name):
    """删除服务器"""
    # 查找服务器配置
    server_config = ServerConfig.query.filter_by(board_name=board_name).first()
    if not server_config:
        flash(f'服务器 {board_name} 不存在！', 'error')
        return redirect(url_for('servers.servers'))

    # 检查是否有套餐使用了该服务器的入站节点
    if PackageNode.query.filter_by(board_name=board_name).first():
        flash(f'服务器 {board_name} 有关联的套餐节点，无法删除！', 'error')
        return redirect(url_for('servers.servers'))

    # 删除服务器
    try:
        db.session.delete(server_config)
        db.session.commit()
        
        # 重新加载配置
        reload_xui_manager()
        
        logger.info(f'管理员删除了服务器: {board_name}')
        flash(f'服务器 {board_name} 已删除！', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"删除服务器失败: {str(e)}")
        flash('删除服务器失败！', 'error')
    
    return redirect(url_for('servers.servers'))
