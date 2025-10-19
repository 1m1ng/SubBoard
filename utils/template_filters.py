"""模板过滤器和上下文处理器"""
from datetime import datetime
import time
import calendar


def timestamp_to_date(timestamp):
    """将时间戳转换为日期字符串"""
    try:
        dt = datetime.fromtimestamp(int(timestamp))
        return dt.strftime('%Y年%m月%d日 %H:%M')
    except:
        return 'N/A'


def calculate_next_reset_date(expiry_timestamp_ms):
    """
    计算下次流量重置时间
    
    Args:
        expiry_timestamp_ms: 过期时间（毫秒时间戳）
        
    Returns:
        str: 下次重置时间的字符串
    """
    try:
        # 转换为秒级时间戳
        expiry_timestamp = expiry_timestamp_ms / 1000
        expiry_date = datetime.fromtimestamp(expiry_timestamp)
        reset_day = expiry_date.day  # 每月重置的日期
        
        now = datetime.now()
        
        # 计算下次重置时间：当前月份的重置日期
        # 获取当前月的最大天数
        max_day_in_month = calendar.monthrange(now.year, now.month)[1]
        actual_reset_day = min(reset_day, max_day_in_month)
        
        next_reset = datetime(now.year, now.month, actual_reset_day, 0, 0, 0)
        
        # 如果本月的重置日期已过，则计算下个月的重置日期
        if next_reset <= now:
            # 计算下个月
            next_month = now.month + 1
            next_year = now.year
            if next_month > 12:
                next_month = 1
                next_year += 1
            
            max_day_in_next_month = calendar.monthrange(next_year, next_month)[1]
            actual_reset_day = min(reset_day, max_day_in_next_month)
            next_reset = datetime(next_year, next_month, actual_reset_day, 0, 0, 0)
        
        # 确保不超过过期时间
        if next_reset > expiry_date:
            return '已过期'
        
        return next_reset.strftime('%Y年%m月%d日')
    except:
        return 'N/A'


def calculate_days_left(expiry_timestamp):
    """计算剩余天数"""
    return max(0, int((expiry_timestamp / 1000 - time.time()) / 86400))


def register_template_filters(app):
    """注册模板过滤器和上下文处理器"""
    # 注册过滤器
    app.template_filter('timestamp_to_date')(timestamp_to_date)
    
    # 注册上下文处理器
    @app.context_processor
    def utility_processor():
        return dict(
            current_timestamp=lambda: int(time.time()),
            calculate_days_left=calculate_days_left,
            calculate_next_reset_date=calculate_next_reset_date
        )
