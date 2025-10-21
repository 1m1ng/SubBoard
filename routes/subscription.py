"""订阅路由"""
from flask import Blueprint, request, Response
from extensions import logger
from models import User
from utils.xui import get_xui_manager
from datetime import datetime

subscription_bp = Blueprint('subscription', __name__)


@subscription_bp.route('/sub')
def subscription():
    """订阅接口，通过Token验证，支持根据UA返回不同格式"""
    token = request.args.get('token')
    
    if not token:
        return Response('Missing token', status=400)
    
    # 通过Token查找用户
    user = User.query.filter_by(subscription_token=token).first()
    if not user:
        return Response('Invalid token', status=403)
    
    if not user.email:
        return Response('No email configured', status=400)
    
    # 检查用户是否有套餐
    if not user.package_id:
        return Response('No package assigned', status=403)
    
    # 检查套餐是否过期（允许无限期套餐）
    if user.package_expire_time is not None and user.package_expire_time <= datetime.now():
        return Response('Package expired', status=403)
    
    manager = get_xui_manager()
    if not manager:
        return Response('Service unavailable', status=503)
    
    # 获取聚合订阅（使用email作为标识，并传递user对象以获取套餐信息）
    result = manager.get_aggregated_subscription(user.email, user=user)
    if not result:
        return Response('No subscription data found', status=404)
    
    base64_content, traffic_info = result
    
    # 获取 User-Agent
    user_agent = request.headers.get('User-Agent', '').lower()
    
    # 检查是否为 Clash/Mihomo 客户端
    is_mihomo = 'clash' in user_agent or 'mihomo' in user_agent
    
    if is_mihomo:
        # 返回 Mihomo YAML 格式
        try:
            from subscription_converter import convert_to_mihomo_yaml
            from models import MihomoTemplate
            
            # 获取活动的模板
            template = MihomoTemplate.query.filter_by(is_active=True).first()
            if not template:
                # 如果没有活动模板，返回错误
                logger.error(f'用户 {user.username} 请求 Mihomo 订阅但没有配置活动模板')
                return Response('No active Mihomo template configured. Please contact administrator.', status=500)
            
            logger.info(f'用户 {user.username} 使用模板 {template.name} 转换 Mihomo 配置')
            
            # 转换为 Mihomo 配置
            mihomo_config = convert_to_mihomo_yaml(base64_content, template.template_content)
            
            if not mihomo_config:
                logger.error(f'用户 {user.username} Mihomo 配置转换结果为空')
                return Response('Failed to convert subscription: empty result', status=500)
            
            # 返回 YAML 配置
            response = Response(mihomo_config, mimetype='text/yaml; charset=utf-8')
            response.headers['Subscription-Userinfo'] = (
                f"upload={traffic_info['upload']}; "
                f"download={traffic_info['download']}; "
                f"total={traffic_info['total']}; "
                f"expire={traffic_info['expire']}"
            )
            response.headers['Profile-Update-Interval'] = '24'
            response.headers['Content-Disposition'] = 'attachment; filename=config.yaml'
            
            logger.info(f'用户 {user.username} 成功获取了 Mihomo 订阅')
            return response
            
        except Exception as e:
            logger.error(f'用户 {user.username} 转换 Mihomo 配置失败: {str(e)}', exc_info=True)
            return Response(f'Failed to convert subscription: {str(e)}', status=500)
    
    else:
        # 返回标准 Base64 订阅
        userinfo = (
            f"upload={traffic_info['upload']}; "
            f"download={traffic_info['download']}; "
            f"total={traffic_info['total']}; "
            f"expire={traffic_info['expire']}"
        )
        
        response = Response(base64_content, mimetype='text/plain')
        response.headers['Subscription-Userinfo'] = userinfo
        
        logger.info(f'用户 {user.username} 获取了订阅')
        return response
