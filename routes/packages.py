"""套餐管理路由"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from extensions import db, logger
from models import Package, PackageNode, ServerConfig
from utils.decorators import admin_required
from utils.xui import get_xui_manager
from utils.cache import inbounds_cache

packages_bp = Blueprint('packages', __name__, url_prefix='/packages')


@packages_bp.route('/')
@admin_required
def packages():
    """套餐管理页面"""
    packages_list = Package.query.all()
    servers = ServerConfig.query.all()
    
    # 获取所有节点信息用于更新节点名称
    xui_manager = get_xui_manager()
    inbounds_map = {}  # {(board_name, inbound_id): inbound_data}
    if xui_manager:
        all_inbounds = xui_manager.get_all_inbounds()
        if all_inbounds:
            for inbound in all_inbounds:
                board_name = inbound.get('board_name')
                inbound_id = inbound.get('id')
                if board_name and inbound_id is not None:
                    inbounds_map[(board_name, inbound_id)] = inbound
    
    # 将套餐转换为字典格式，包含节点信息
    packages_data = []
    for pkg in packages_list:
        # 更新节点名称为当前最新的名称
        nodes_data = []
        for node in pkg.nodes:
            node_dict = node.to_dict()
            # 尝试从最新的inbounds数据中获取当前名称
            inbound_key = (node.board_name, node.inbound_id)
            if inbound_key in inbounds_map:
                inbound = inbounds_map[inbound_key]
                # 更新为最新的节点名称
                current_name = inbound.get('remark') or inbound.get('tag') or f"节点-{node.inbound_id}"
                node_dict['node_name'] = current_name
                logger.debug(f"节点 {node.board_name}/{node.inbound_id} 名称: {node.node_name} -> {current_name}")
            else:
                # 如果找不到对应的inbound，使用数据库中保存的名称，但标记为可能已失效
                logger.warning(f"找不到节点 {node.board_name}/{node.inbound_id}，可能已被删除")
            nodes_data.append(node_dict)
        
        pkg_dict = {
            'id': pkg.id,
            'name': pkg.name,
            'total_traffic': pkg.total_traffic,
            'created_at': pkg.created_at,
            'nodes': nodes_data,
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
                inbound_id = inbound.get('id')
                # 优先使用 remark，如果没有则使用 tag，确保有节点名称显示
                node_name = inbound.get('remark') or inbound.get('tag') or f"节点-{inbound_id}"
                if inbound_id is not None:
                    nodes.append({
                        'id': inbound_id,  # 这是唯一稳定的标识符
                        'name': node_name  # 这只是用于显示的名称
                    })
        
        logger.info(f"获取服务器 {board_name} 的节点列表，共 {len(nodes)} 个节点")
        return jsonify({'success': True, 'nodes': nodes})
    except Exception as e:
        logger.error(f"获取节点列表失败: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})


@packages_bp.route('/refresh_nodes', methods=['POST'])
@admin_required
def refresh_nodes():
    """刷新所有服务器的节点列表（清除缓存并重新获取）"""
    try:
        # 清除缓存
        inbounds_cache.clear()
        logger.info('已清除入站列表缓存')
        
        # 重新获取节点信息
        xui_manager = get_xui_manager()
        if not xui_manager:
            return jsonify({'success': False, 'message': 'XUI管理器未初始化'})
        
        # 强制重新从服务器获取数据
        all_inbounds = xui_manager.get_all_inbounds()
        if all_inbounds is None:
            return jsonify({'success': False, 'message': '无法获取节点列表'})
        
        # 更新缓存
        inbounds_cache.set_aggregated(all_inbounds)
        logger.info(f'已刷新入站列表缓存，共 {len(all_inbounds)} 个节点')
        
        return jsonify({
            'success': True, 
            'message': f'刷新成功，共获取 {len(all_inbounds)} 个节点',
            'total_nodes': len(all_inbounds)
        })
    except Exception as e:
        logger.error(f"刷新节点列表失败: {str(e)}")
        return jsonify({'success': False, 'message': f'刷新失败: {str(e)}'})


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
        
        # 刷新入站列表缓存
        logger.info(f'套餐创建后刷新缓存')
        xui_manager = get_xui_manager()
        if xui_manager:
            all_inbounds = xui_manager.get_all_inbounds()
            if all_inbounds:
                inbounds_cache.set_aggregated(all_inbounds)
                logger.info(f'已刷新入站列表缓存，共 {len(all_inbounds)} 个节点')
        
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
        # 获取旧的节点列表（用于比较变化）
        old_nodes_list = PackageNode.query.filter_by(package_id=package_id).all()
        old_nodes = {(node.board_name, node.inbound_id): node for node in old_nodes_list}
        
        # 解析新的节点列表
        selected_nodes = request.form.getlist('nodes[]')
        new_nodes = {}
        new_nodes_list = []
        
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
            
            # 保存新节点的键和数据
            node_key = (board_name, inbound_id)
            new_nodes[node_key] = {
                'board_name': board_name,
                'inbound_id': inbound_id,
                'node_name': node_name,
                'traffic_rate': traffic_rate
            }
            new_nodes_list.append(node_key)
        
        # 比较节点变化
        old_node_keys = set(old_nodes.keys())
        new_node_keys = set(new_nodes.keys())
        
        # 找出删除的节点和新增的节点
        removed_nodes = old_node_keys - new_node_keys
        added_nodes = new_node_keys - old_node_keys
        
        # 获取套餐内所有用户的邮箱列表
        from models import User
        package_users = User.query.filter_by(package_id=package_id).all()
        user_emails = [user.email for user in package_users]
        
        # 如果有节点变化且有用户，处理客户端的增删
        if (removed_nodes or added_nodes) and user_emails:
            xui_manager = get_xui_manager()
            if xui_manager:
                # 处理删除的节点：从这些节点中删除所有用户的客户端
                for node_key in removed_nodes:
                    board_name, inbound_id = node_key
                    logger.info(f"从节点 {board_name}/{inbound_id} 删除 {len(user_emails)} 个客户端")
                    xui_manager.delete_clients_from_node(board_name, inbound_id, user_emails)
                
                # 处理新增的节点：向这些节点添加所有用户的客户端
                for node_key in added_nodes:
                    board_name, inbound_id = node_key
                    logger.info(f"向节点 {board_name}/{inbound_id} 添加 {len(user_emails)} 个客户端")
                    xui_manager.add_clients_to_node(board_name, inbound_id, user_emails)
            else:
                logger.warning("XUI管理器未初始化，无法同步客户端变化")
        
        # 删除旧的节点关联
        PackageNode.query.filter_by(package_id=package_id).delete()
        
        # 添加新的节点关联
        for node_key in new_nodes_list:
            node_data = new_nodes[node_key]
            package_node = PackageNode(
                package_id=package.id,      # type: ignore
                board_name=node_data['board_name'],      # type: ignore
                inbound_id=node_data['inbound_id'],      # type: ignore
                node_name=node_data['node_name'],        # type: ignore
                traffic_rate=node_data['traffic_rate']   # type: ignore
            )
            db.session.add(package_node)
        
        db.session.commit()
        
        # 刷新入站列表缓存
        logger.info(f'套餐编辑后刷新缓存')
        xui_manager = get_xui_manager()
        if xui_manager:
            all_inbounds = xui_manager.get_all_inbounds()
            if all_inbounds:
                inbounds_cache.set_aggregated(all_inbounds)
                logger.info(f'已刷新入站列表缓存，共 {len(all_inbounds)} 个节点')
        
        logger.info(f'管理员编辑了套餐: {name}，节点变化：删除 {len(removed_nodes)} 个，新增 {len(added_nodes)} 个')
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
    if not package:
        flash('套餐不存在！', 'error')
        return redirect(url_for('packages.packages'))
    
    from models import User
    
    # 获取使用此套餐的所有用户
    package_users = User.query.filter_by(package_id=package_id).all()
    
    # 获取套餐的所有节点
    package_nodes = PackageNode.query.filter_by(package_id=package_id).all()
    
    name = package.name
    
    try:
        # 如果有用户正在使用此套餐，先删除这些用户在所有节点的客户端
        if package_users and package_nodes:
            xui_manager = get_xui_manager()
            if xui_manager:
                user_emails = [user.email for user in package_users]
                logger.info(f"删除套餐 {name}，开始清理 {len(user_emails)} 个用户在 {len(package_nodes)} 个节点的客户端")
                
                # 遍历所有节点，删除所有用户的客户端
                for node in package_nodes:
                    board_name = node.board_name
                    inbound_id = node.inbound_id
                    logger.info(f"从节点 {board_name}/{inbound_id} 删除 {len(user_emails)} 个客户端")
                    xui_manager.delete_clients_from_node(board_name, inbound_id, user_emails)
                
                logger.info(f"套餐 {name} 的客户端清理完成")
            else:
                logger.warning("XUI管理器未初始化，无法清理客户端")
        
        # 将所有用户的套餐ID设置为NULL
        if package_users:
            for user in package_users:
                user.package_id = None
                user.package_expire_time = None
                user.next_reset_time = None
            db.session.flush()
            logger.info(f"已将 {len(package_users)} 个用户从套餐 {name} 中移除")
        
        # 删除套餐（级联删除会自动删除 PackageNode）
        db.session.delete(package)
        db.session.commit()
        
        # 刷新入站列表缓存
        logger.info(f'套餐删除后刷新缓存')
        xui_manager = get_xui_manager()
        if xui_manager:
            all_inbounds = xui_manager.get_all_inbounds()
            if all_inbounds:
                inbounds_cache.set_aggregated(all_inbounds)
                logger.info(f'已刷新入站列表缓存，共 {len(all_inbounds)} 个节点')
        
        logger.info(f'管理员删除了套餐: {name}，包含 {len(package_nodes)} 个节点')
        flash(f'套餐 {name} 已被删除！', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"删除套餐失败: {str(e)}")
        flash(f'删除套餐失败: {str(e)}', 'error')
    
    return redirect(url_for('packages.packages'))
