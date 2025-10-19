"""认证相关工具函数"""
import secrets
import string
from datetime import datetime, timedelta
from extensions import db, logger
from models import IPBlock
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
        if datetime.utcnow() < ip_record.blocked_until:
            return True, ip_record.blocked_until
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
        ip_record = IPBlock(ip_address=ip_address, failed_attempts=0)
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
