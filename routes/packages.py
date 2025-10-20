"""套餐管理路由"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from extensions import db, logger
from models import Package, PackageNode, ServerConfig
from utils.decorators import admin_required
from utils.xui import get_xui_manager

packages_bp = Blueprint('packages', __name__, url_prefix='/packages')


@packages_bp.route('/')
@admin_required
def packages():
    """套餐管理页面"""
    packages_list = Package.query.all()
    servers = ServerConfig.query.all()
    
    # 将套餐转换为字典格式，包含节点信息
    packages_data = []
    for pkg in packages_list:
        pkg_dict = {
            'id': pkg.id,
            'name': pkg.name,
            'total_traffic': pkg.total_traffic,
            'created_at': pkg.created_at,
            'nodes': [node.to_dict() for node in pkg.nodes],
            'users_count': len(pkg.users) if pkg.users else 0  # users 已经是列表，不需要 .all()
        }
        packages_data.append(pkg_dict)
    
    return render_template('packages.html', packages=packages_data, servers=servers)


@packages_bp.route('/get_nodes/<board_name>')
@admin_required
def get_nodes(board_name):
    """获取指定服务器的节点列表"""
    try:
        # 从xui_manager获取节点信息
        xui_manager = get_xui_manager()
        if not xui_manager:
            return jsonify({'success': False, 'message': 'XUI管理器未初始化'})
        
        inbounds = xui_manager.get_all_inbounds()
        if inbounds is None:
            return jsonify({'success': False, 'message': '无法获取节点列表'})
        
        # 提取并过滤指定服务器的节点
        nodes = []
        for inbound in inbounds:
            # 只选择属于指定服务器的节点
            if inbound.get('board_name') == board_name:
                node_name = inbound.get('remark', inbound.get('tag', ''))
                if node_name:
                    nodes.append({
                        'id': inbound.get('id'),
                        'name': node_name
                    })
        
        logger.info(f"获取服务器 {board_name} 的节点列表，共 {len(nodes)} 个节点")
        return jsonify({'success': True, 'nodes': nodes})
    except Exception as e:
        logger.error(f"获取节点列表失败: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})


@packages_bp.route('/create', methods=['POST'])
@admin_required
def create_package():
    """创建套餐"""
    name = request.form.get('name')
    total_traffic = request.form.get('total_traffic')
    
    # 验证
    if not name or not total_traffic:
        flash('套餐名称和总流量不能为空！', 'error')
        return redirect(url_for('packages.packages'))
    
    try:
        total_traffic = int(total_traffic)
        if total_traffic <= 0:
            flash('总流量必须大于0！', 'error')
            return redirect(url_for('packages.packages'))
    except ValueError:
        flash('总流量必须是数字！', 'error')
        return redirect(url_for('packages.packages'))
    
    # 检查套餐名是否已存在
    if Package.query.filter_by(name=name).first():
        flash('套餐名称已存在！', 'error')
        return redirect(url_for('packages.packages'))
    
    # 创建套餐
    package = Package(name=name, total_traffic=total_traffic * 1024 * 1024 * 1024)  # type: ignore
    
    try:
        db.session.add(package)
        db.session.flush()  # 获取package.id
        
        # 处理节点选择
        selected_nodes = request.form.getlist('nodes[]')
        for node_data in selected_nodes:
            # 格式: board_name|inbound_id|node_name
            parts = node_data.split('|')
            if len(parts) != 3:
                logger.warning(f"节点数据格式错误: {node_data}")
                continue
            
            board_name, inbound_id_str, node_name = parts
            try:
                inbound_id = int(inbound_id_str)
            except ValueError:
                logger.warning(f"inbound_id 格式错误: {inbound_id_str}")
                continue
            
            traffic_rate = request.form.get(f'rate_{board_name}_{node_name}', 1.0)
            try:
                traffic_rate = float(traffic_rate)
            except ValueError:
                traffic_rate = 1.0
            
            package_node = PackageNode(
                package_id=package.id,  # type: ignore
                board_name=board_name,  # type: ignore
                inbound_id=inbound_id,  # type: ignore
                node_name=node_name,  # type: ignore
                traffic_rate=traffic_rate  # type: ignore
            )
            db.session.add(package_node)
        
        db.session.commit()
        logger.info(f'管理员创建了套餐: {name}')
        flash(f'套餐 {name} 创建成功！', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"创建套餐失败: {str(e)}")
        flash(f'创建套餐失败: {str(e)}', 'error')
    
    return redirect(url_for('packages.packages'))


@packages_bp.route('/edit/<int:package_id>', methods=['POST'])
@admin_required
def edit_package(package_id):
    """编辑套餐"""
    package = db.session.get(Package, package_id)
    if not package:
        flash('套餐不存在！', 'error')
        return redirect(url_for('packages.packages'))
    
    name = request.form.get('name')
    total_traffic = request.form.get('total_traffic')
    
    # 验证
    if not name or not total_traffic:
        flash('套餐名称和总流量不能为空！', 'error')
        return redirect(url_for('packages.packages'))
    
    try:
        total_traffic = int(total_traffic)
        if total_traffic <= 0:
            flash('总流量必须大于0！', 'error')
            return redirect(url_for('packages.packages'))
    except ValueError:
        flash('总流量必须是数字！', 'error')
        return redirect(url_for('packages.packages'))
    
    # 检查套餐名是否被其他套餐占用
    existing = Package.query.filter_by(name=name).first()
    if existing and existing.id != package_id:
        flash('套餐名称已存在！', 'error')
        return redirect(url_for('packages.packages'))
    
    # 更新套餐
    package.name = name
    package.total_traffic = total_traffic * 1024 * 1024 * 1024  # 转换为字节
    
    try:
        # 删除旧的节点关联
        PackageNode.query.filter_by(package_id=package_id).delete()
        
        # 添加新的节点关联
        selected_nodes = request.form.getlist('nodes[]')
        for node_data in selected_nodes:
            # 格式: board_name|inbound_id|node_name
            parts = node_data.split('|')
            if len(parts) != 3:
                logger.warning(f"节点数据格式错误: {node_data}")
                continue
            
            board_name, inbound_id_str, node_name = parts
            try:
                inbound_id = int(inbound_id_str)
            except ValueError:
                logger.warning(f"inbound_id 格式错误: {inbound_id_str}")
                continue
            
            traffic_rate = request.form.get(f'rate_{board_name}_{node_name}', 1.0)
            try:
                traffic_rate = float(traffic_rate)
            except ValueError:
                traffic_rate = 1.0

            package_node = PackageNode(
                package_id=package.id,      # type: ignore
                board_name=board_name,      # type: ignore
                inbound_id=inbound_id,      # type: ignore
                node_name=node_name,        # type: ignore
                traffic_rate=traffic_rate   # type: ignore
            )
            db.session.add(package_node)
        
        db.session.commit()
        logger.info(f'管理员编辑了套餐: {name}')
        flash(f'套餐 {name} 已更新！', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"编辑套餐失败: {str(e)}")
        flash(f'编辑套餐失败: {str(e)}', 'error')
    
    return redirect(url_for('packages.packages'))


@packages_bp.route('/delete/<int:package_id>')
@admin_required
def delete_package(package_id):
    """删除套餐"""
    package = db.session.get(Package, package_id)
    if package:
        # 检查是否有用户正在使用此套餐
        if package.users:
            flash(f'套餐 {package.name} 正在被 {len(package.users)} 个用户使用，无法删除！', 'error') # type: ignore
            return redirect(url_for('packages.packages'))
        
        name = package.name
        db.session.delete(package)
        db.session.commit()
        logger.info(f'管理员删除了套餐: {name}')
        flash(f'套餐 {name} 已被删除！', 'success')
    else:
        flash('套餐不存在！', 'error')
    
    return redirect(url_for('packages.packages'))
