"""
定时任务调度器
负责每分钟执行流量监控、套餐过期检测和流量重置任务
"""
import logging
from datetime import datetime
from dateutil.relativedelta import relativedelta
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask
from utils.extensions import db
from models import User, Package, PackageNode, UserNodeStatus
from service.xui_manager import get_xui_manager

logger = logging.getLogger(__name__)

class TrafficScheduler:
    """流量监控调度器"""
    
    def __init__(self, app: Flask):
        self.app = app
        self.scheduler = BackgroundScheduler()
        
    def start(self):
        """启动调度器"""
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
        
        # 启动后立即执行一次流量监控
        logger.info("立即执行首次流量监控...")
        try:
            self._run_traffic_monitoring()
            logger.info("首次执行完成")
        except Exception as e:
            logger.error(f"首次执行任务时发生错误: {str(e)}", exc_info=True)
    
    def stop(self):
        """停止调度器"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("流量监控调度器已停止")
    
    def _run_traffic_monitoring(self):
        """执行流量监控任务（在应用上下文中运行）"""
        with self.app.app_context():
            try:
                logger.debug("开始执行流量监控任务...")
                
                # 任务2: 检测用户流量是否超标以及套餐是否过期
                self._check_traffic_and_expiry()
                
                # 任务3: 检测用户是否需要重置流量
                self._check_traffic_reset()
                
                logger.debug("流量监控任务执行完成")
                
            except Exception as e:
                logger.error(f"执行流量监控任务时发生错误: {str(e)}", exc_info=True)
    
    def _check_traffic_and_expiry(self):
        """检测用户流量是否超标以及套餐是否过期"""
        try:
            # 查询所有拥有套餐的用户
            users_with_packages: list[User] = User.query.filter(
                User.package_id.isnot(None)
            ).all()
            
            logger.debug(f"检查 {len(users_with_packages)} 个用户的流量和过期状态")
            
            xui_manager = get_xui_manager()
            if not xui_manager:
                logger.error("XUI 管理器未初始化，无法检查流量和过期状态")
                return
            
            now = datetime.now()
            
            for user in users_with_packages:
                try:
                    package: Package = Package.query.get(user.package_id) # type: ignore
                    if not package:
                        continue
                    
                    should_disable = False
                    disable_reason = None
                    
                    used_traffic = xui_manager.get_used_traffic(user).get('total', 0) # type: ignore
                    
                    # 检查套餐是否过期
                    if user.package_expire_time is not None and user.package_expire_time <= now:
                        should_disable = True
                        disable_reason = 'package_expired'
                        logger.debug(f"用户 {user.email} 套餐已过期")
                    
                    # 检查流量是否超标
                    elif used_traffic:
                        if used_traffic >= package.total_traffic:
                            should_disable = True
                            disable_reason = 'traffic_exceeded'
                            logger.debug(
                                f"用户 {user.email} 流量超标: "
                                f"{used_traffic:.2f} bytes >= {package.total_traffic:.2f} bytes"
                            )
                    
                    # 查询当前用户状态
                    user_status: UserNodeStatus = UserNodeStatus.query.filter_by(user_id=user.id).first() # type: ignore
                    
                    if should_disable:
                        # 需要禁用用户
                        if not user_status or not user_status.is_disabled:
                            # 用户当前未被禁用，执行禁用操作
                            success = xui_manager.disable_client_from_package_nodes(user)
                            
                            if success:
                                # 更新或创建用户状态记录
                                if user_status:
                                    user_status.is_disabled = True
                                    user_status.disable_reason = disable_reason
                                    user_status.disabled_at = now
                                else:
                                    user_status = UserNodeStatus(user_id=user.id, is_disabled=True, disable_reason=disable_reason) # type: ignore
                                    db.session.add(user_status)
                                
                                logger.info(f"已禁用用户 {user.email}，原因: {disable_reason}")
                    else:
                        # 用户正常，如果之前被禁用则启用
                        if user_status and user_status.is_disabled:
                            success = xui_manager.enable_client_from_package_nodes(user)
                            
                            if success:
                                user_status.is_disabled = False
                                user_status.disable_reason = None
                                user_status.disabled_at = None
                                logger.info(f"已启用用户 {user.email}")
                
                except Exception as e:
                    logger.error(f"检查用户 {user.email} 状态时出错: {str(e)}", exc_info=True)
            
            db.session.commit()
            logger.debug("流量和过期检查任务完成")
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"检查流量和过期状态时发生错误: {str(e)}", exc_info=True)
    
    def _check_traffic_reset(self):
        """检测用户是否需要重置流量"""
        try:
            now = datetime.now()
            
            # 查询所有需要重置流量的用户
            users_to_reset: list[User] = User.query.filter(
                User.package_id.isnot(None),
                User.next_reset_time.isnot(None),
                User.next_reset_time <= now
            ).all()
            
            if not users_to_reset:
                logger.debug("没有需要重置流量的用户")
                return
            
            logger.info(f"找到 {len(users_to_reset)} 个需要重置流量的用户")
            
            xui_manager = get_xui_manager()
            if not xui_manager:
                logger.error("XUI 管理器未初始化，无法重置流量")
                return
            
            for user in users_to_reset:
                try:
                    package = Package.query.get(user.package_id)
                    if not package:
                        continue
                    
                    # 获取套餐关联的所有节点
                    package_nodes: list[PackageNode] = PackageNode.query.filter_by(package_id=package.id).all()
                    
                    # 重置每个节点上的流量
                    reset_success = True
                    for package_node in package_nodes:
                        server = xui_manager.servers.get(package_node.board_name)
                        if not server:
                            logger.error(f"节点服务器未找到 - 节点: {package_node.board_name}")
                            reset_success = False
                            continue
                        success = server.reset_client_traffic(
                            package_node.inbound_id,
                            user.email
                        )
                        if not success:
                            logger.error(
                                f"重置用户 {user.email} 在节点 {package_node.board_name} "
                                f"入站 {package_node.inbound_id} 的流量失败"
                            )
                            reset_success = False
                    
                    if reset_success:                        
                        # 计算下一次重置时间（下个月的同一天）
                        user.next_reset_time = now + relativedelta(months=1)
                        
                        # 如果用户之前被禁用（因流量超标），现在启用
                        user_status: UserNodeStatus = UserNodeStatus.query.filter_by(user_id=user.id).first() # type: ignore
                        if user_status and user_status.is_disabled and \
                           user_status.disable_reason == 'traffic_exceeded':
                            success = xui_manager.enable_client_from_package_nodes(user)
                            
                            if success:
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
            logger.debug("流量重置任务完成")
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"检查流量重置时发生错误: {str(e)}", exc_info=True)
    
    def _cleanup_expired_tokens(self):
        """定期清理过期的JWT token"""
        with self.app.app_context():
            try:
                logger.debug("开始清理过期的JWT令牌...")
                from utils import cleanup_expired_tokens
                cleanup_expired_tokens()
                logger.debug("过期JWT令牌清理完成")
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
