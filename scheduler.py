"""
定时任务调度器
负责每分钟执行流量监控、套餐过期检测和流量重置任务
"""
import json
import logging
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask
from extensions import db
from models import User, Package, PackageNode, UserTraffic, UserNodeStatus
from utils.xui import get_xui_manager

logger = logging.getLogger(__name__)

class TrafficScheduler:
    """流量监控调度器"""
    
    def __init__(self, app: Flask):
        self.app = app
        self.scheduler = BackgroundScheduler()
        
    def start(self):
        """启动调度器"""
        # 每分钟刷新一次入站列表缓存
        self.scheduler.add_job(
            func=self._refresh_inbounds_cache,
            trigger='interval',
            minutes=1,
            id='refresh_inbounds_cache',
            name='刷新入站列表缓存',
            replace_existing=True
        )
        
        # 每分钟执行一次流量监控任务
        self.scheduler.add_job(
            func=self._run_traffic_monitoring,
            trigger='interval',
            minutes=1,
            id='traffic_monitoring',
            name='流量监控任务',
            replace_existing=True
        )
        
        # 每小时清理一次过期的JWT token
        self.scheduler.add_job(
            func=self._cleanup_expired_tokens,
            trigger='interval',
            hours=1,
            id='cleanup_expired_tokens',
            name='清理过期JWT令牌',
            replace_existing=True
        )
        
        self.scheduler.start()
        logger.info("流量监控调度器已启动，将每分钟执行一次任务")
        
        # 启动后立即执行一次缓存刷新和流量监控
        logger.info("立即执行首次缓存刷新和流量监控...")
        try:
            self._refresh_inbounds_cache()
            self._run_traffic_monitoring()
            logger.info("首次执行完成")
        except Exception as e:
            logger.error(f"首次执行任务时发生错误: {str(e)}", exc_info=True)
    
    def stop(self):
        """停止调度器"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("流量监控调度器已停止")
    
    def _refresh_inbounds_cache(self):
        """定时刷新所有面板的入站列表缓存"""
        with self.app.app_context():
            try:
                logger.info("开始刷新入站列表缓存...")
                
                xui_manager = get_xui_manager()
                if not xui_manager:
                    logger.warning("XUI管理器未初始化，跳过缓存刷新")
                    return
                
                # 获取所有面板的入站列表（会自动更新缓存）
                all_inbounds = xui_manager.get_all_inbounds()
                
                if all_inbounds:
                    from utils.cache import inbounds_cache
                    # 保存聚合后的数据到缓存
                    inbounds_cache.set_aggregated(all_inbounds)
                    logger.info(f"已刷新入站列表缓存，共 {len(all_inbounds)} 个节点")
                else:
                    logger.warning("未获取到任何入站列表")
                
            except Exception as e:
                logger.error(f"刷新入站列表缓存时发生错误: {str(e)}", exc_info=True)
    
    def _run_traffic_monitoring(self):
        """执行流量监控任务（在应用上下文中运行）"""
        with self.app.app_context():
            try:
                logger.info("开始执行流量监控任务...")
                
                # 任务1: 计算所有用户的已使用流量
                self._calculate_user_traffic()
                
                # 任务2: 检测用户流量是否超标以及套餐是否过期
                self._check_traffic_and_expiry()
                
                # 任务3: 检测用户是否需要重置流量
                self._check_traffic_reset()
                
                logger.info("流量监控任务执行完成")
                
            except Exception as e:
                logger.error(f"执行流量监控任务时发生错误: {str(e)}", exc_info=True)
    
    def _calculate_user_traffic(self):
        """计算所有拥有套餐的用户的已使用流量"""
        try:
            # 查询所有拥有套餐且套餐未过期的用户
            users_with_packages = User.query.filter(
                User.package_id.isnot(None),
                ((User.package_expire_time == None) | (User.package_expire_time > datetime.now()))
            ).all()
            
            logger.info(f"找到 {len(users_with_packages)} 个需要计算流量的用户")
            
            xui_manager = get_xui_manager()
            
            for user in users_with_packages:
                try:
                    # 获取用户套餐信息
                    package = Package.query.get(user.package_id)
                    if not package:
                        logger.warning(f"用户 {user.email} 的套餐不存在")
                        continue
                    
                    # 获取套餐关联的节点及流量倍率
                    package_nodes = PackageNode.query.filter_by(package_id=package.id).all()
                    if not package_nodes:
                        logger.warning(f"套餐 {package.name} 没有关联任何节点")
                        continue
                    
                    # 获取用户在所有节点的流量数据
                    traffic_data = xui_manager.get_client_traffic(user.email) # type: ignore
                    if not traffic_data:
                        logger.debug(f"用户 {user.email} 没有流量数据")
                        continue
                    
                    # 计算总流量: sum([(up + down) * rate])
                    total_traffic = 0
                    for traffic in traffic_data:
                        board_name = traffic.get('board_name')
                        node_name = traffic.get('nodeName')
                        upload = traffic.get('up', 0)
                        download = traffic.get('down', 0)
                        
                        # 查找该节点的流量倍率
                        package_node = next(
                            (pn for pn in package_nodes 
                             if pn.board_name == board_name and pn.node_name == node_name),
                            None
                        )
                        
                        if package_node:
                            rate = package_node.traffic_rate
                            node_traffic = (upload + download) * rate
                            total_traffic += node_traffic
                            logger.debug(
                                f"用户 {user.email} 节点 {board_name}/{node_name}: "
                                f"上传={upload}, 下载={download}, 倍率={rate}, "
                                f"计费流量={node_traffic}"
                            )
                        else:
                            logger.debug(
                                f"用户 {user.email} 在节点 {board_name}/{node_name} "
                                f"的流量未计入（该节点不在套餐中）"
                            )
                    
                    # 转换为 GB
                    total_traffic_gb = total_traffic / (1024 ** 3)
                    
                    # 更新或创建 UserTraffic 记录
                    user_traffic = UserTraffic.query.filter_by(user_id=user.id).first()
                    if user_traffic:
                        user_traffic.used_traffic = total_traffic_gb
                        user_traffic.updated_at = datetime.now()
                    else:
                        user_traffic = UserTraffic(user_id=user.id, used_traffic=total_traffic_gb) # type: ignore
                        db.session.add(user_traffic)
                    
                    # 同步更新 User 表的 used_traffic 字段
                    user.used_traffic = total_traffic_gb
                    
                    # 转换套餐总流量为 GB（数据库存储的是字节）
                    total_traffic_limit_gb = package.total_traffic / (1024 ** 3)
                    
                    logger.info(
                        f"用户 {user.email} 已使用流量: {total_traffic_gb:.2f} GB / "
                        f"{total_traffic_limit_gb:.2f} GB"
                    )
                    
                except Exception as e:
                    logger.error(f"计算用户 {user.email} 流量时出错: {str(e)}", exc_info=True)
            
            db.session.commit()
            logger.info("流量计算任务完成")
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"计算用户流量时发生错误: {str(e)}", exc_info=True)
    
    def _check_traffic_and_expiry(self):
        """检测用户流量是否超标以及套餐是否过期"""
        try:
            # 查询所有拥有套餐的用户
            users_with_packages = User.query.filter(
                User.package_id.isnot(None)
            ).all()
            
            logger.info(f"检查 {len(users_with_packages)} 个用户的流量和过期状态")
            
            xui_manager = get_xui_manager()
            now = datetime.now()
            
            for user in users_with_packages:
                try:
                    package = Package.query.get(user.package_id)
                    if not package:
                        continue
                    
                    should_disable = False
                    disable_reason = None
                    
                    # 检查套餐是否过期
                    if user.package_expire_time is not None and user.package_expire_time <= now:
                        should_disable = True
                        disable_reason = 'package_expired'
                        logger.info(f"用户 {user.email} 套餐已过期")
                    
                    # 检查流量是否超标（将套餐总流量从字节转换为 GB）
                    elif user.used_traffic:
                        total_traffic_limit_gb = package.total_traffic / (1024 ** 3)
                        if user.used_traffic >= total_traffic_limit_gb:
                            should_disable = True
                            disable_reason = 'traffic_exceeded'
                            logger.info(
                                f"用户 {user.email} 流量超标: "
                                f"{user.used_traffic:.2f} GB >= {total_traffic_limit_gb:.2f} GB"
                            )
                    
                    # 查询当前用户状态
                    user_status = UserNodeStatus.query.filter_by(user_id=user.id).first()
                    
                    if should_disable:
                        # 需要禁用用户
                        if not user_status or not user_status.is_disabled:
                            # 用户当前未被禁用，执行禁用操作
                            success = self._disable_user_on_all_nodes(user.email, xui_manager)
                            
                            if success:
                                # 更新或创建用户状态记录
                                if user_status:
                                    user_status.is_disabled = True
                                    user_status.disable_reason = disable_reason
                                    user_status.disabled_at = now
                                else:
                                    user_status = UserNodeStatus(user_id=user.id, is_disabled=True, disable_reason=disable_reason)  # type: ignore
                                    db.session.add(user_status)
                                
                                logger.info(f"已禁用用户 {user.email}，原因: {disable_reason}")
                    else:
                        # 用户正常，如果之前被禁用则启用
                        if user_status and user_status.is_disabled:
                            success = self._enable_user_on_all_nodes(user.email, xui_manager)
                            
                            if success:
                                user_status.is_disabled = False
                                user_status.disable_reason = None
                                user_status.disabled_at = None
                                logger.info(f"已启用用户 {user.email}")
                
                except Exception as e:
                    logger.error(f"检查用户 {user.email} 状态时出错: {str(e)}", exc_info=True)
            
            db.session.commit()
            logger.info("流量和过期检查任务完成")
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"检查流量和过期状态时发生错误: {str(e)}", exc_info=True)
    
    def _check_traffic_reset(self):
        """检测用户是否需要重置流量"""
        try:
            now = datetime.now()
            
            # 查询所有需要重置流量的用户
            users_to_reset = User.query.filter(
                User.package_id.isnot(None),
                User.next_reset_time.isnot(None),
                User.next_reset_time <= now
            ).all()
            
            if not users_to_reset:
                logger.debug("没有需要重置流量的用户")
                return
            
            logger.info(f"找到 {len(users_to_reset)} 个需要重置流量的用户")
            
            xui_manager = get_xui_manager()
            
            for user in users_to_reset:
                try:
                    package = Package.query.get(user.package_id)
                    if not package:
                        continue
                    
                    # 获取套餐关联的所有节点
                    package_nodes = PackageNode.query.filter_by(package_id=package.id).all()
                    
                    # 重置每个节点上的流量
                    reset_success = True
                    for package_node in package_nodes:
                        success = xui_manager.reset_client_traffic(     # type: ignore
                            package_node.board_name,  # 指定面板
                            package_node.inbound_id,
                            user.email
                        )
                        if not success:
                            reset_success = False
                            logger.error(
                                f"重置用户 {user.email} 在面板 {package_node.board_name} "
                                f"节点 {package_node.inbound_id} 的流量失败"
                            )
                    
                    if reset_success:
                        # 重置用户的已使用流量
                        user.used_traffic = 0
                        
                        # 更新 UserTraffic 记录
                        user_traffic = UserTraffic.query.filter_by(user_id=user.id).first()
                        if user_traffic:
                            user_traffic.used_traffic = 0
                            user_traffic.updated_at = now
                        
                        # 计算下一次重置时间（下个月的同一天）
                        user.next_reset_time = now + relativedelta(months=1)
                        
                        # 如果用户之前被禁用（因流量超标），现在启用
                        user_status = UserNodeStatus.query.filter_by(user_id=user.id).first()
                        if user_status and user_status.is_disabled and \
                           user_status.disable_reason == 'traffic_exceeded':
                            self._enable_user_on_all_nodes(user.email, xui_manager)
                            user_status.is_disabled = False
                            user_status.disable_reason = None
                            user_status.disabled_at = None
                        
                        logger.info(
                            f"已重置用户 {user.email} 的流量，"
                            f"下次重置时间: {user.next_reset_time}"
                        )
                
                except Exception as e:
                    logger.error(f"重置用户 {user.email} 流量时出错: {str(e)}", exc_info=True)
            
            db.session.commit()
            logger.info("流量重置任务完成")
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"检查流量重置时发生错误: {str(e)}", exc_info=True)
    
    def _disable_user_on_all_nodes(self, email: str, xui_manager) -> bool:
        """在所有节点上禁用用户"""
        try:
            # 获取用户在所有节点的客户端信息
            all_clients = xui_manager.get_all_clients_by_email(email)
            
            if not all_clients:
                logger.warning(f"未找到用户 {email} 的任何客户端")
                return False
            
            all_success = True
            for client_info in all_clients:
                board_name = client_info['board_name']
                inbound_id = client_info['inbound_id']
                client = client_info['client']
                
                # 修改 enable 状态
                client['enable'] = False
                
                # 调用 API 更新（指定面板）
                success = xui_manager.update_client(
                    board_name,  # 面板名称
                    client['id'],  # client UUID
                    inbound_id,
                    client  # 直接传递客户端配置对象
                )
                
                if not success:
                    all_success = False
                    logger.error(f"禁用用户 {email} 在面板 {board_name} 节点 {inbound_id} 失败")
            
            return all_success
            
        except Exception as e:
            logger.error(f"禁用用户 {email} 时出错: {str(e)}", exc_info=True)
            return False
    
    def _enable_user_on_all_nodes(self, email: str, xui_manager) -> bool:
        """在所有节点上启用用户"""
        try:
            # 获取用户在所有节点的客户端信息
            all_clients = xui_manager.get_all_clients_by_email(email)
            
            if not all_clients:
                logger.warning(f"未找到用户 {email} 的任何客户端")
                return False
            
            all_success = True
            for client_info in all_clients:
                board_name = client_info['board_name']
                inbound_id = client_info['inbound_id']
                client = client_info['client']
                
                # 修改 enable 状态
                client['enable'] = True
                
                # 调用 API 更新（指定面板）
                success = xui_manager.update_client(
                    board_name,  # 面板名称
                    client['id'],  # client UUID
                    inbound_id,
                    client  # 直接传递客户端配置对象
                )
                
                if not success:
                    all_success = False
                    logger.error(f"启用用户 {email} 在面板 {board_name} 节点 {inbound_id} 失败")
            
            return all_success
            
        except Exception as e:
            logger.error(f"启用用户 {email} 时出错: {str(e)}", exc_info=True)
            return False
    
    def _cleanup_expired_tokens(self):
        """定期清理过期的JWT token"""
        with self.app.app_context():
            try:
                logger.info("开始清理过期的JWT令牌...")
                from utils import cleanup_expired_tokens
                cleanup_expired_tokens()
                logger.info("过期JWT令牌清理完成")
            except Exception as e:
                logger.error(f"清理过期JWT令牌时发生错误: {str(e)}", exc_info=True)


# 全局调度器实例
_scheduler = None

def init_scheduler(app: Flask):
    """初始化调度器"""
    global _scheduler
    if _scheduler is None:
        _scheduler = TrafficScheduler(app)
        _scheduler.start()

def get_scheduler() -> TrafficScheduler:
    """获取调度器实例"""
    if _scheduler is None:
        raise RuntimeError("Scheduler has not been initialized.")
    return _scheduler
