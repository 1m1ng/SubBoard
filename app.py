from flask import Flask, render_template, request, redirect, url_for, flash, session, Response, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
import secrets
import string
import logging
from xui_client import XUIManager
from dotenv import load_dotenv
from waitress import serve
import time

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# 节点信息缓存
# 结构: {user_id: {'data': nodes_info, 'timestamp': time.time()}}
nodes_cache = {}
CACHE_DURATION = 300

# 用户模型
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # 订阅相关字段
    subscription_token = db.Column(db.String(64), unique=True, nullable=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def generate_subscription_token(self):
        """生成订阅Token"""
        self.subscription_token = secrets.token_urlsafe(32)
        return self.subscription_token

    def __repr__(self):
        return f'<User {self.username}>'

# IP锁定记录模型
class IPBlock(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(45), unique=True, nullable=False)
    failed_attempts = db.Column(db.Integer, default=0)
    blocked_until = db.Column(db.DateTime, nullable=True)
    last_attempt = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<IPBlock {self.ip_address}>'

# 服务器配置模型
class ServerConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    board_name = db.Column(db.String(50), unique=True, nullable=False)
    server = db.Column(db.String(255), nullable=False)
    port = db.Column(db.Integer, nullable=False)
    path = db.Column(db.String(255), nullable=False)
    sub_path = db.Column(db.String(255), nullable=False)  # 订阅路径
    username = db.Column(db.String(255), nullable=False)
    password = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<ServerConfig {self.board_name}>'
    
    def to_dict(self):
        """转换为字典格式"""
        return {
            'server': self.server,
            'port': self.port,
            'path': self.path,
            'sub_path': self.sub_path,
            'username': self.username,
            'password': self.password
        }

# Mihomo配置模板模型
class MihomoTemplate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    template_content = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<MihomoTemplate {self.name}>'

# 全局变量，用于缓存XUIManager实例
xui_manager = None

# 加载3XUI配置
def load_xui_config():
    """从数据库加载3XUI面板配置"""
    try:
        servers = ServerConfig.query.all()
        config = {'boards': {}}
        
        for server in servers:
            config['boards'][server.board_name] = server.to_dict()
        
        if config['boards']:
            return XUIManager(config)
        else:
            logger.warning("数据库中没有服务器配置")
            return None
    except Exception as e:
        logger.error(f"加载服务器配置失败: {str(e)}")
        return None

def get_xui_manager():
    """获取XUIManager实例，如果不存在则加载"""
    global xui_manager
    if xui_manager is None:
        xui_manager = load_xui_config()
    return xui_manager

# 添加Jinja2过滤器
@app.template_filter('timestamp_to_date')
def timestamp_to_date(timestamp):
    """将时间戳转换为日期字符串"""
    try:
        dt = datetime.fromtimestamp(int(timestamp))
        return dt.strftime('%Y年%m月%d日 %H:%M')
    except:
        return 'N/A'

# 添加模板全局函数
@app.context_processor
def utility_processor():
    """向模板添加工具函数"""
    import time
    import calendar
    
    def calculate_next_reset_date(expiry_timestamp_ms):
        """
        计算下次流量重置时间
        参数:
            expiry_timestamp_ms: 过期时间（毫秒时间戳）
        返回:
            下次重置时间的字符串
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
    
    return dict(
        current_timestamp=lambda: int(time.time()),
        calculate_days_left=lambda expiry_timestamp: max(0, int((expiry_timestamp / 1000 - time.time()) / 86400)),
        calculate_next_reset_date=calculate_next_reset_date
    )

# 辅助函数：生成随机密码
def generate_random_password(length=12):
    characters = string.ascii_letters + string.digits + string.punctuation
    password = ''.join(secrets.choice(characters) for _ in range(length))
    return password

# 辅助函数：检查IP是否被锁定
def check_ip_blocked(ip_address):
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

# 辅助函数：记录登录失败
def record_failed_login(ip_address):
    ip_record = IPBlock.query.filter_by(ip_address=ip_address).first()
    if not ip_record:
        ip_record = IPBlock(ip_address=ip_address, failed_attempts=0)
        db.session.add(ip_record)
    
    ip_record.failed_attempts += 1
    ip_record.last_attempt = datetime.utcnow()
    
    # 如果失败次数超过5次，锁定IP 30分钟
    if ip_record.failed_attempts >= 5:
        ip_record.blocked_until = datetime.utcnow() + timedelta(minutes=30)
        logger.warning(f'IP {ip_address} 已被锁定，失败尝试次数: {ip_record.failed_attempts}')
    
    db.session.commit()
    return ip_record.failed_attempts

# 辅助函数：重置登录失败记录
def reset_failed_login(ip_address):
    ip_record = IPBlock.query.filter_by(ip_address=ip_address).first()
    if ip_record:
        ip_record.failed_attempts = 0
        ip_record.blocked_until = None
        db.session.commit()

# 首页
@app.route('/')
def index():
    if 'user_id' in session:
        user = db.session.get(User, session['user_id'])
        if not user:
            flash('用户不存在！', 'error')
            return redirect(url_for('login'))

        # 生成订阅URL
        subscription_url = None
        if user.subscription_token:
            subscription_url = url_for('subscription', token=user.subscription_token, _external=True)
        elif user.email:
            # 如果还没有Token，自动生成一个
            user.generate_subscription_token()
            db.session.commit()
            subscription_url = url_for('subscription', token=user.subscription_token, _external=True)

        # 首次加载时不获取节点信息，由前端异步加载
        return render_template('index.html', user=user, nodes=None, subscription_url=subscription_url)
    return redirect(url_for('login'))

# API：获取节点信息（带缓存）
@app.route('/api/nodes')
def get_nodes():
    if 'user_id' not in session:
        return jsonify({'error': '未登录'}), 401
    
    user = db.session.get(User, session['user_id'])
    if not user:
        return jsonify({'error': '用户不存在'}), 404
    
    user_id = user.id
    current_time = time.time()
    
    # 检查是否强制刷新（通过查询参数 _= 时间戳来判断）
    force_refresh = request.args.get('_') is not None
    
    # 检查缓存是否存在且未过期（非强制刷新时）
    if not force_refresh and user_id in nodes_cache:
        cache_entry = nodes_cache[user_id]
        if current_time - cache_entry['timestamp'] < CACHE_DURATION:
            logger.info(f'使用缓存数据 - 用户: {user.username}, 缓存年龄: {int(current_time - cache_entry["timestamp"])}秒')
            return jsonify({
                'nodes': cache_entry['data'],
                'cached': True,
                'cache_age': int(current_time - cache_entry['timestamp'])
            })
    
    # 缓存不存在、已过期或强制刷新，重新获取数据
    logger.info(f'获取新数据 - 用户: {user.username}, 强制刷新: {force_refresh}')
    nodes_info = []
    manager = get_xui_manager()
    if user.email and manager:
        nodes_info = manager.get_all_traffic_info(user.email)
    
    # 更新缓存
    nodes_cache[user_id] = {
        'data': nodes_info,
        'timestamp': current_time
    }
    
    return jsonify({
        'nodes': nodes_info,
        'cached': False,
        'cache_age': 0
    })

# 订阅路由（不需要登录）
@app.route('/sub')
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
    
    manager = get_xui_manager()
    if not manager:
        return Response('Service unavailable', status=503)
    
    # 获取聚合订阅
    result = manager.get_aggregated_subscription(user.email)
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
            
            # 获取活动的模板
            template = MihomoTemplate.query.filter_by(is_active=True).first()
            if not template:
                # 如果没有活动模板，返回错误
                return Response('No active Mihomo template configured', status=500)
            
            # 转换为 Mihomo 配置
            mihomo_config = convert_to_mihomo_yaml(base64_content, template.template_content)
            
            # 返回 YAML 配置
            response = Response(mihomo_config, mimetype='text/yaml')
            response.headers['Subscription-Userinfo'] = (
                f"upload={traffic_info['upload']}; "
                f"download={traffic_info['download']}; "
                f"total={traffic_info['total']}; "
                f"expire={traffic_info['expire']}"
            )
            response.headers['Profile-Update-Interval'] = '24'
            
            logger.info(f'用户 {user.username} 获取了 Mihomo 订阅')
            return response
            
        except Exception as e:
            logger.error(f'转换 Mihomo 配置失败: {str(e)}')
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

# 登录
@app.route('/login', methods=['GET', 'POST'])
def login():
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
            return redirect(url_for('index'))
        else:
            # 登录失败，记录失败次数
            failed_count = record_failed_login(client_ip)
            remaining_attempts = 5 - failed_count
            if remaining_attempts > 0:
                flash(f'用户名或密码错误！剩余尝试次数: {remaining_attempts}', 'error')
            else:
                flash('登录失败次数过多，您的IP已被锁定30分钟。', 'error')
            logger.warning(f'登录失败，IP: {client_ip}, 用户名: {username}, 失败次数: {failed_count}')
            return redirect(url_for('login'))

    return render_template('login.html', blocked=False)

# 登出
@app.route('/logout')
def logout():
    username = session.get('username', 'Unknown')
    session.clear()
    flash('您已成功登出！', 'success')
    logger.info(f'用户 {username} 已登出')
    return redirect(url_for('login'))

# 个人资料
@app.route('/profile')
def profile():
    if 'user_id' not in session:
        flash('请先登录！', 'error')
        return redirect(url_for('login'))
    
    user = db.session.get(User, session['user_id'])
    return render_template('profile.html', user=user)

# 刷新订阅Token
@app.route('/refresh_token', methods=['POST'])
def refresh_token():
    if 'user_id' not in session:
        flash('请先登录！', 'error')
        return redirect(url_for('login'))
    
    user = db.session.get(User, session['user_id'])
    user.generate_subscription_token()
    db.session.commit()
    
    logger.info(f'用户 {user.username} 刷新了订阅Token')
    flash('订阅Token已刷新！', 'success')
    return redirect(url_for('index'))

# 修改密码页面
@app.route('/change_password_page')
def change_password_page():
    if 'user_id' not in session:
        flash('请先登录！', 'error')
        return redirect(url_for('login'))
    
    return render_template('change_password.html')

# 修改密码
@app.route('/change_password', methods=['POST'])
def change_password():
    if 'user_id' not in session:
        flash('请先登录！', 'error')
        return redirect(url_for('login'))
    
    user = db.session.get(User, session['user_id'])
    old_password = request.form.get('old_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    # 验证
    if not old_password or not new_password or not confirm_password:
        flash('所有字段都是必填的！', 'error')
        return redirect(url_for('change_password_page'))
    
    # 验证旧密码
    if not user.check_password(old_password):
        flash('旧密码不正确！', 'error')
        return redirect(url_for('change_password_page'))
    
    # 验证新密码长度
    if len(new_password) < 6:
        flash('新密码长度至少为6位！', 'error')
        return redirect(url_for('change_password_page'))
    
    # 验证两次密码是否一致
    if new_password != confirm_password:
        flash('两次输入的新密码不一致！', 'error')
        return redirect(url_for('change_password_page'))
    
    # 更新密码
    if not user:
        flash('用户不存在！', 'error')
        return redirect(url_for('change_password_page'))

    user.set_password(new_password)
    db.session.commit()
    
    logger.info(f'用户 {user.username} 修改了密码')
    flash('密码修改成功！', 'success')
    return redirect(url_for('profile'))

# 管理员页面：用户管理
@app.route('/admin')
def admin():
    if 'user_id' not in session or not session.get('is_admin'):
        flash('只有管理员可以访问此页面！', 'error')
        return redirect(url_for('index'))
    
    users = User.query.all()
    blocked_ips = IPBlock.query.filter(IPBlock.blocked_until.isnot(None)).all()
    return render_template('admin.html', users=users, blocked_ips=blocked_ips)

# 管理员：创建用户
@app.route('/admin/create_user', methods=['POST'])
def create_user():
    if 'user_id' not in session or not session.get('is_admin'):
        flash('只有管理员可以创建用户！', 'error')
        return redirect(url_for('index'))
    
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')
    is_admin = request.form.get('is_admin') == 'on'
    
    # 验证
    if not username or not email or not password:
        flash('所有字段都是必填的！', 'error')
        return redirect(url_for('admin'))
    
    if len(password) < 6:
        flash('密码长度至少为6位！', 'error')
        return redirect(url_for('admin'))
    
    # 检查用户是否已存在
    if User.query.filter_by(username=username).first():
        flash('用户名已存在！', 'error')
        return redirect(url_for('admin'))
    
    if User.query.filter_by(email=email).first():
        flash('邮箱已被注册！', 'error')
        return redirect(url_for('admin'))
    
    # 创建新用户
    user = User(username=username, email=email, is_admin=is_admin)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    
    logger.info(f'管理员创建了新用户: {username}, 管理员权限: {is_admin}')
    flash(f'用户 {username} 创建成功！', 'success')
    return redirect(url_for('admin'))

# 管理员：编辑用户
@app.route('/admin/edit_user/<int:user_id>', methods=['POST'])
def edit_user(user_id):
    if 'user_id' not in session or not session.get('is_admin'):
        flash('只有管理员可以编辑用户！', 'error')
        return redirect(url_for('index'))
    
    user = db.session.get(User, user_id)
    if not user:
        flash('用户不存在！', 'error')
        return redirect(url_for('admin'))
    
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')
    is_admin = request.form.get('is_admin') == 'on'
    
    # 验证
    if not username or not email:
        flash('用户名和邮箱不能为空！', 'error')
        return redirect(url_for('admin'))
    
    # 检查用户名是否被其他用户占用
    existing_user = User.query.filter_by(username=username).first()
    if existing_user and existing_user.id != user_id:
        flash('用户名已存在！', 'error')
        return redirect(url_for('admin'))
    
    # 检查邮箱是否被其他用户占用
    existing_email = User.query.filter_by(email=email).first()
    if existing_email and existing_email.id != user_id:
        flash('邮箱已被注册！', 'error')
        return redirect(url_for('admin'))
    
    # 更新用户信息
    user.username = username
    user.email = email
    user.is_admin = is_admin
    
    # 如果提供了新密码，则更新密码
    if password and len(password) >= 6:
        user.set_password(password)
    elif password and len(password) < 6:
        flash('密码长度至少为6位，密码未更新！', 'error')
    
    db.session.commit()
    
    logger.info(f'管理员编辑了用户: {username}')
    flash(f'用户 {username} 信息已更新！', 'success')
    return redirect(url_for('admin'))

# 管理员：删除用户
@app.route('/admin/delete_user/<int:user_id>')
def delete_user(user_id):
    if 'user_id' not in session or not session.get('is_admin'):
        flash('只有管理员可以删除用户！', 'error')
        return redirect(url_for('index'))
    
    # 不能删除自己
    if user_id == session['user_id']:
        flash('不能删除自己的账号！', 'error')
        return redirect(url_for('admin'))
    
    user = db.session.get(User, user_id)
    if user:
        username = user.username
        db.session.delete(user)
        db.session.commit()
        logger.info(f'管理员删除了用户: {username}')
        flash(f'用户 {username} 已被删除！', 'success')
    else:
        flash('用户不存在！', 'error')

# 管理员：解锁IP
@app.route('/admin/unblock_ip/<int:ip_id>')
def unblock_ip(ip_id):
    if 'user_id' not in session or not session.get('is_admin'):
        flash('只有管理员可以解锁IP！', 'error')
        return redirect(url_for('index'))

    ip_record = db.session.get(IPBlock, ip_id)
    if ip_record:
        ip_address = ip_record.ip_address
        ip_record.blocked_until = None
        ip_record.failed_attempts = 0
        db.session.commit()
        logger.info(f'管理员解锁了IP: {ip_address}')
        flash(f'IP {ip_address} 已解锁！', 'success')
    else:
        flash('IP记录不存在！', 'error')
    
    return redirect(url_for('admin'))

# 服务器管理页面
@app.route('/servers')
def servers():
    if 'user_id' not in session or not session.get('is_admin'):
        flash('只有管理员可以访问此页面！', 'error')
        return redirect(url_for('index'))
    
    # 从数据库读取服务器配置
    server_configs = ServerConfig.query.all()
    boards = {server.board_name: server.to_dict() for server in server_configs}
    
    return render_template('servers.html', boards=boards)

# 添加服务器
@app.route('/servers/add', methods=['POST'])
def add_server():
    if 'user_id' not in session or not session.get('is_admin'):
        flash('只有管理员可以添加服务器！', 'error')
        return redirect(url_for('index'))
    
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
        return redirect(url_for('servers'))
    
    try:
        port = int(port) if port else None
    except ValueError:
        flash('端口必须是数字！', 'error')
        return redirect(url_for('servers'))

    # 检查是否已存在
    if ServerConfig.query.filter_by(board_name=board_name).first():
        flash(f'服务器 {board_name} 已存在！', 'error')
        return redirect(url_for('servers'))
    
    # 添加新服务器
    new_server = ServerConfig(
        board_name=board_name,
        server=server,
        port=port,
        path=path,
        sub_path=sub_path,
        username=username,
        password=password
    )
    
    try:
        db.session.add(new_server)
        db.session.commit()
        
        # 重新加载配置
        global xui_manager
        xui_manager = load_xui_config()
        
        logger.info(f'管理员添加了服务器: {board_name}')
        flash(f'服务器 {board_name} 添加成功！', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"添加服务器失败: {str(e)}")
        flash('添加服务器失败！', 'error')
    
    return redirect(url_for('servers'))

# 编辑服务器
@app.route('/servers/edit/<board_name>', methods=['POST'])
def edit_server(board_name):
    if 'user_id' not in session or not session.get('is_admin'):
        flash('只有管理员可以编辑服务器！', 'error')
        return redirect(url_for('index'))
    
    server = request.form.get('server')
    port = request.form.get('port')
    path = request.form.get('path')
    sub_path = request.form.get('sub_path', 'sub0').strip()
    username = request.form.get('username')
    password = request.form.get('password')
    
    # 验证
    if not all([server, port, path, username]):
        flash('必填字段不能为空！', 'error')
        return redirect(url_for('servers'))
    
    try:
        port = int(port) if port else None
    except ValueError:
        flash('端口必须是数字！', 'error')
        return redirect(url_for('servers'))

    # 查找服务器配置
    server_config = ServerConfig.query.filter_by(board_name=board_name).first()
    if not server_config:
        flash(f'服务器 {board_name} 不存在！', 'error')
        return redirect(url_for('servers'))

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
        global xui_manager
        xui_manager = load_xui_config()
        
        logger.info(f'管理员编辑了服务器: {board_name}')
        flash(f'服务器 {board_name} 更新成功！', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"更新服务器失败: {str(e)}")
        flash('更新服务器失败！', 'error')
    
    return redirect(url_for('servers'))

# 删除服务器
@app.route('/servers/delete/<board_name>')
def delete_server(board_name):
    if 'user_id' not in session or not session.get('is_admin'):
        flash('只有管理员可以删除服务器！', 'error')
        return redirect(url_for('index'))
    
    # 查找服务器配置
    server_config = ServerConfig.query.filter_by(board_name=board_name).first()
    if not server_config:
        flash(f'服务器 {board_name} 不存在！', 'error')
        return redirect(url_for('servers'))

    # 删除服务器
    try:
        db.session.delete(server_config)
        db.session.commit()
        
        # 重新加载配置
        global xui_manager
        xui_manager = load_xui_config()
        
        logger.info(f'管理员删除了服务器: {board_name}')
        flash(f'服务器 {board_name} 已删除！', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"删除服务器失败: {str(e)}")
        flash('删除服务器失败！', 'error')
    
    return redirect(url_for('servers'))

# Mihomo 模板管理页面
@app.route('/mihomo_template')
def mihomo_template():
    if 'user_id' not in session or not session.get('is_admin'):
        flash('只有管理员可以访问此页面！', 'error')
        return redirect(url_for('index'))
    
    # 获取所有模板
    templates = MihomoTemplate.query.all()
    active_template = MihomoTemplate.query.filter_by(is_active=True).first()
    
    return render_template('mihomo_template.html', templates=templates, active_template=active_template)

# 保存 Mihomo 模板
@app.route('/mihomo_template/save', methods=['POST'])
def save_mihomo_template():
    if 'user_id' not in session or not session.get('is_admin'):
        flash('只有管理员可以保存模板！', 'error')
        return redirect(url_for('index'))
    
    name = request.form.get('name', '默认模板')
    template_content = request.form.get('template_content')
    set_active = request.form.get('set_active') == 'true'
    
    if not template_content:
        flash('模板内容不能为空！', 'error')
        return redirect(url_for('mihomo_template'))
    
    # 验证 YAML 格式
    try:
        import yaml
        yaml.safe_load(template_content)
    except yaml.YAMLError as e:
        flash(f'YAML 格式错误: {str(e)}', 'error')
        return redirect(url_for('mihomo_template'))
    
    try:
        # 如果设置为活动模板，先取消其他模板的活动状态
        if set_active:
            MihomoTemplate.query.update({MihomoTemplate.is_active: False})
        
        # 检查是否已存在同名模板
        template = MihomoTemplate.query.filter_by(name=name).first()
        if template:
            # 更新现有模板
            template.template_content = template_content
            template.is_active = set_active
            template.updated_at = datetime.utcnow()
        else:
            # 创建新模板
            template = MihomoTemplate(
                name=name,
                template_content=template_content,
                is_active=set_active
            )
            db.session.add(template)
        
        db.session.commit()
        logger.info(f'管理员保存了 Mihomo 模板: {name}')
        flash(f'模板 {name} 保存成功！', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"保存模板失败: {str(e)}")
        flash('保存模板失败！', 'error')
    
    return redirect(url_for('mihomo_template'))

# 删除 Mihomo 模板
@app.route('/mihomo_template/delete/<int:template_id>')
def delete_mihomo_template(template_id):
    if 'user_id' not in session or not session.get('is_admin'):
        flash('只有管理员可以删除模板！', 'error')
        return redirect(url_for('index'))
    
    template = db.session.get(MihomoTemplate, template_id)
    if not template:
        flash('模板不存在！', 'error')
        return redirect(url_for('mihomo_template'))
    
    try:
        db.session.delete(template)
        db.session.commit()
        logger.info(f'管理员删除了 Mihomo 模板: {template.name}')
        flash(f'模板 {template.name} 已删除！', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"删除模板失败: {str(e)}")
        flash('删除模板失败！', 'error')
    
    return redirect(url_for('mihomo_template'))

# 设置活动模板
@app.route('/mihomo_template/set_active/<int:template_id>')
def set_active_template(template_id):
    if 'user_id' not in session or not session.get('is_admin'):
        flash('只有管理员可以设置活动模板！', 'error')
        return redirect(url_for('index'))
    
    try:
        # 取消所有模板的活动状态
        MihomoTemplate.query.update({MihomoTemplate.is_active: False})
        
        # 设置指定模板为活动
        template = db.session.get(MihomoTemplate, template_id)
        if template:
            template.is_active = True
            db.session.commit()
            logger.info(f'管理员设置 Mihomo 模板为活动: {template.name}')
            flash(f'已将 {template.name} 设置为活动模板！', 'success')
        else:
            flash('模板不存在！', 'error')
    except Exception as e:
        db.session.rollback()
        logger.error(f"设置活动模板失败: {str(e)}")
        flash('设置活动模板失败！', 'error')
    
    return redirect(url_for('mihomo_template'))

# 验证 YAML 格式的 API
@app.route('/mihomo_template/validate', methods=['POST'])
def validate_yaml():
    if 'user_id' not in session or not session.get('is_admin'):
        return {'valid': False, 'error': '未授权'}, 403
    
    try:
        import yaml
        data = request.get_json()
        content = data.get('content', '')
        
        if not content:
            return {'valid': False, 'error': '内容为空'}
        
        # 尝试解析 YAML
        yaml.safe_load(content)
        return {'valid': True}
    except yaml.YAMLError as e:
        return {'valid': False, 'error': str(e)}
    except Exception as e:
        return {'valid': False, 'error': f'验证失败: {str(e)}'}

# 初始化数据库
def init_db():
    with app.app_context():
        db.create_all()
        
        # 检查是否已存在管理员账号
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            # 生成随机密码
            admin_password = generate_random_password(16)
            
            # 创建默认管理员账号
            admin = User(
                username='admin',
                email='admin@system.local',
                is_admin=True
            )
            admin.set_password(admin_password)
            db.session.add(admin)
            db.session.commit()
            
            # 记录到日志
            logger.info('='*60)
            logger.info('数据库初始化成功！')
            logger.info('默认管理员账号已创建：')
            logger.info(f'  用户名: admin')
            logger.info(f'  密码: {admin_password}')
            logger.info('请妥善保管此密码，建议登录后立即修改！')
            logger.info('='*60)
            

if __name__ == '__main__':
    # 检查数据库是否存在，不存在则创建
    if not os.path.exists('data.db'):
        init_db()
    else:
        # 数据库存在，但需要确保表结构是最新的
        with app.app_context():
            db.create_all()
            # 检查是否有管理员账号
            admin_count = User.query.filter_by(is_admin=True).count()
            if admin_count == 0:
                logger.warning("警告：数据库中没有管理员账号！")
                # 重新初始化数据库
                init_db()
    
    # 使用 Waitress WSGI 服务器（支持 Windows 和 Linux）
    logger.info("启动 Waitress WSGI 服务器...")
    logger.info(f"访问地址: http://{os.getenv('HOST', '0.0.0.0')}:{os.getenv('PORT', 5000)}")
    serve(app, host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", 5000)), threads=int(os.getenv("THREADS", 4)))
    