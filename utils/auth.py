"""认证相关工具函数"""
import secrets
import string
import jwt
from datetime import datetime, timedelta, timezone
from extensions import db, logger
from models import IPBlock, User, JWTToken
from config import Config


def generate_random_password(length=12):
    """生成随机密码"""
    characters = string.ascii_letters + string.digits + string.punctuation
    password = ''.join(secrets.choice(characters) for _ in range(length))
    return password


def check_ip_blocked(ip_address):
    """
    检查IP是否被锁定
    
    Args:
        ip_address: IP地址
        
    Returns:
        tuple: (是否被锁定, 锁定到期时间)
    """
    ip_record = IPBlock.query.filter_by(ip_address=ip_address).first()
    if ip_record and ip_record.blocked_until:
        # 确保 blocked_until 是 offset-aware
        blocked_until_aware = ip_record.blocked_until.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) < blocked_until_aware:
            return True, blocked_until_aware
        else:
            # 解除锁定
            ip_record.blocked_until = None
            ip_record.failed_attempts = 0
            db.session.commit()
    return False, None


def record_failed_login(ip_address):
    """
    记录登录失败
    
    Args:
        ip_address: IP地址
        
    Returns:
        int: 失败次数
    """
    ip_record = IPBlock.query.filter_by(ip_address=ip_address).first()
    if not ip_record:
        ip_record = IPBlock(ip_address=ip_address, failed_attempts=0) # type: ignore
        db.session.add(ip_record)
    
    ip_record.failed_attempts += 1
    ip_record.last_attempt = datetime.utcnow()
    
    # 如果失败次数超过限制，锁定IP
    if ip_record.failed_attempts >= Config.MAX_FAILED_ATTEMPTS:
        ip_record.blocked_until = datetime.utcnow() + timedelta(minutes=Config.BLOCK_DURATION)
        logger.warning(f'IP {ip_address} 已被锁定，失败尝试次数: {ip_record.failed_attempts}')
    
    db.session.commit()
    return ip_record.failed_attempts


def reset_failed_login(ip_address):
    """
    重置登录失败记录
    
    Args:
        ip_address: IP地址
    """
    ip_record = IPBlock.query.filter_by(ip_address=ip_address).first()
    if ip_record:
        ip_record.failed_attempts = 0
        ip_record.blocked_until = None
        db.session.commit()


def generate_token(user_id, username, is_admin, ip_address=None, user_agent=None):
    """
    生成JWT token并存储到数据库
    
    Args:
        user_id: 用户ID
        username: 用户名
        is_admin: 是否为管理员
        ip_address: IP地址（可选）
        user_agent: 用户代理（可选）
        
    Returns:
        str: JWT token
    """
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=Config.JWT_ACCESS_TOKEN_EXPIRES)
    
    payload = {
        'user_id': user_id,
        'username': username,
        'is_admin': is_admin,
        'exp': expires_at,
        'iat': datetime.now(timezone.utc)
    }
    token = jwt.encode(payload, Config.JWT_SECRET_KEY, algorithm='HS256')
    
    # 将token存储到数据库
    jwt_token = JWTToken(
        user_id=user_id, # type: ignore
        token=token, # type: ignore
        expires_at=expires_at, # type: ignore
        ip_address=ip_address, # type: ignore
        user_agent=user_agent # type: ignore
    )
    db.session.add(jwt_token)
    
    # 清理该用户的过期token（可选，保持数据库整洁）
    cleanup_expired_tokens(user_id)
    
    db.session.commit()
    logger.info(f'为用户 {username} (ID: {user_id}) 生成新token')
    
    return token


def verify_token(token):
    """
    验证JWT token（包括数据库验证）
    
    Args:
        token: JWT token
        
    Returns:
        dict: 解码后的payload，如果失败返回None
    """
    try:
        # 1. 解码JWT token
        payload = jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=['HS256'])
        
        # 2. 验证用户是否存在
        user = db.session.get(User, payload['user_id'])
        if not user:
            logger.warning(f'Token验证失败：用户不存在，user_id={payload["user_id"]}')
            return None
        
        # 3. 验证token是否在数据库中存在且未被撤销
        jwt_token = JWTToken.query.filter_by(token=token).first()
        if not jwt_token:
            logger.warning(f'Token验证失败：token不在数据库中，user_id={payload["user_id"]}')
            return None
        
        if jwt_token.is_revoked:
            logger.warning(f'Token验证失败：token已被撤销，user_id={payload["user_id"]}')
            return None
        
        # 4. 验证token是否过期（数据库层面）
        jwt_token_expiry = jwt_token.expires_at.replace(tzinfo=timezone.utc)  # 确保为offset-aware
        if jwt_token_expiry < datetime.now(timezone.utc):
            logger.warning(f'Token验证失败：token已过期（数据库检查），user_id={payload["user_id"]}')
            return None
        
        return payload
        
    except jwt.ExpiredSignatureError:
        logger.warning('Token验证失败：token已过期（JWT检查）')
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f'Token验证失败：无效的token - {str(e)}')
        return None


def revoke_token(token):
    """
    撤销token（用于登出）
    
    Args:
        token: JWT token
    """
    jwt_token = JWTToken.query.filter_by(token=token).first()
    if jwt_token:
        jwt_token.is_revoked = True
        db.session.commit()
        logger.info(f'Token已撤销，user_id={jwt_token.user_id}')


def revoke_all_user_tokens(user_id):
    """
    撤销用户的所有token（用于修改密码后强制重新登录）
    
    Args:
        user_id: 用户ID
    """
    tokens = JWTToken.query.filter_by(user_id=user_id, is_revoked=False).all()
    for token in tokens:
        token.is_revoked = True
    db.session.commit()
    logger.info(f'已撤销用户 {user_id} 的所有token，共 {len(tokens)} 个')


def cleanup_expired_tokens(user_id=None):
    """
    清理过期的token
    
    Args:
        user_id: 用户ID（可选，如果提供则只清理该用户的过期token）
    """
    now = datetime.now(timezone.utc)
    
    if user_id:
        # 只清理指定用户的过期token
        expired_tokens = JWTToken.query.filter(
            JWTToken.user_id == user_id,
            JWTToken.expires_at < now
        ).all()
    else:
        # 清理所有过期token
        expired_tokens = JWTToken.query.filter(JWTToken.expires_at < now).all()
    
    for token in expired_tokens:
        db.session.delete(token)
    
    if expired_tokens:
        db.session.commit()
        logger.info(f'已清理 {len(expired_tokens)} 个过期token')
