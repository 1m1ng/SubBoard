# SubBoard - 订阅节点管理面板

一个基于 Flask 的订阅节点管理面板，用于管理和分发 3XUI 节点订阅。

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0-green.svg)](https://flask.palletsprojects.com/)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## ✨ 功能特性

### 🎯 核心功能
- ✨ **多面板支持** - 同时管理多个 3XUI 面板的节点
- 📊 **流量统计** - 实时查看每个节点的流量使用情况  
- ⏰ **到期提醒** - 显示节点到期时间和流量重置时间
- 🔗 **统一订阅** - 生成单一订阅链接聚合所有节点
- 🔐 **Token 认证** - 安全的订阅 Token 机制
- 🎨 **Mihomo 模板** - 支持自定义 YAML 配置模板
- 🔄 **智能转换** - 根据 User-Agent 自动返回 Base64 或 Mihomo 格式
- 🛣️ **订阅路径配置** - 支持为不同面板配置不同的订阅路径（sub0, sub1 等）

### 👥 用户管理
- ✅ **管理员系统**：首次启动自动创建管理员账号
- ✅ **用户认证**：安全的密码验证和会话管理
- ✅ **邮箱登录**：支持使用邮箱或用户名登录
- ✅ **密码加密**：使用 Werkzeug 进行密码哈希
- ✅ **IP 锁定**：登录失败 5 次后锁定 IP 30 分钟
- ✅ **用户管理**：创建、编辑、删除用户
- ✅ **IP 解锁**：管理员可手动解锁被锁定的 IP
- ✅ **密码修改**：用户可以修改自己的密码

### 🏢 服务器管理
- 🖥️ **多服务器配置**：管理多个 3XUI 面板
- ⚙️ **动态配置**：通过 Web 界面添加/编辑/删除服务器
- 🔧 **订阅路径**：每个服务器可独立配置订阅路径前缀
- 💾 **数据库存储**：所有配置保存在数据库中

### 🛠️ 技术特性
- ✅ **生产级 WSGI**：使用 Waitress 服务器（支持 Windows 和 Linux）
- ✅ **SQLite 数据库**：轻量级本地数据库
- ✅ **环境变量**：支持 .env 文件配置
- ✅ **Docker 支持**：提供完整的 Docker 部署方案
- ✅ **美观界面**：现代化设计，响应式布局
- ✅ **日志记录**：记录所有重要操作

## 🚀 快速开始

### 方式一：Docker 部署（推荐）

最简单快捷的部署方式：

```docker-compose.yaml
services:
  subboard:
    image: huiji2333/subboard:latest
    container_name: subboard
    restart: unless-stopped
    ports:
      - "5000:5000"
    environment:
      # 应用配置（请修改为随机密钥）
      - SECRET_KEY=${SECRET_KEY:-your-secret-key-here-change-in-production}
      # 服务器配置
      - HOST=0.0.0.0
      - PORT=5000
      - THREADS=4
    volumes:
      # 持久化数据库
      - ./instance:/app/instance
    networks:
      - subboard-network
    healthcheck:
      test: ["CMD", "python", "-c", "import requests; requests.get('http://localhost:5000', timeout=5)"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s

networks:
  subboard-network:
    driver: bridge
```

```bash
# 部署
docker-compose up -d

# 查看管理员密码
docker-compose logs | grep "管理员密码"
```

访问地址：http://localhost:5000

### 方式二：传统部署

#### 1. 安装依赖

```bash
# 创建虚拟环境（推荐）
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# 或
.venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

#### 2. 配置环境变量

```bash
# 复制配置文件
cp .env.example .env

# 编辑配置（必须修改 SECRET_KEY）
nano .env
```

生成随机密钥：
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

#### 3. 运行应用

```bash
python app.py
```

首次运行会自动创建数据库和管理员账户，请查看控制台输出获取管理员密码。

#### 4. 访问面板

在浏览器中访问: http://localhost:5000

### 首次登录

系统会自动创建默认管理员账号：
- **用户名**: `admin`
- **邮箱**: `admin@system.local`
- **密码**: 随机生成（在控制台和日志中显示）

⚠️ **重要**：首次登录后请立即修改密码！

## 📋 配置说明

### 环境变量

创建 `.env` 文件配置应用：

```env
# 应用密钥（必须修改！）
SECRET_KEY=your-secret-key-here-change-in-production

# 服务器配置（可选）
HOST=0.0.0.0
PORT=5000
THREADS=4
```

### 服务器管理

通过 Web 界面管理 3XUI 服务器：

1. 登录管理员账号
2. 点击顶部"服务器管理"
3. 添加 3XUI 面板信息：
   - **服务器标识**：唯一标识符（如 server1）
   - **服务器地址**：面板域名或 IP
   - **端口**：面板端口（通常是 443）
   - **路径**：面板路径（如 1234567890abcdefg）
   - **订阅路径**：订阅前缀（如 sub0）
   - **用户名**：面板登录用户名
   - **密码**：面板登录密码


## 📁 目录结构

```
SubBoard/
├── app.py                      # 主应用文件
├── xui_client.py              # 3XUI API 客户端
├── subscription_converter.py  # 订阅转换器
├── requirements.txt           # 项目依赖
├── .env                       # 环境变量配置（需创建）
├── .env.example               # 环境变量示例
├── Dockerfile                 # Docker 镜像构建文件
├── docker-compose.yml         # Docker Compose 配置
├── .dockerignore              # Docker 忽略文件
├── README.md                  # 项目说明（本文件）
├── instance/                  # 数据库目录（自动创建）
│   └── subboard.db           # SQLite 数据库
├── logs/                      # 日志目录（自动创建）
│   └── app.log               # 应用日志
├── templates/                 # HTML 模板
│   ├── base.html             # 基础模板
│   ├── index.html            # 首页（节点展示）
│   ├── login.html            # 登录页面
│   ├── profile.html          # 个人资料页面
│   ├── change_password.html  # 修改密码页面
│   ├── admin.html            # 用户管理页面
│   ├── servers.html          # 服务器管理页面
│   └── mihomo_template.html  # Mihomo 模板管理
└── static/                    # 静态文件
    └── style.css             # 样式文件
```

## 📖 使用说明

### 1. 配置服务器（管理员）

首次使用需要配置 3XUI 服务器：

1. 使用管理员账号登录
2. 点击顶部导航栏的"服务器管理"
3. 填写服务器信息并保存
4. 可以添加多个服务器

### 2. 配置订阅（用户）

1. 登录系统
2. 进入"个人资料"页面
3. 在"订阅配置"区域输入您在 3XUI 面板中使用的邮箱
4. 点击"保存"，系统会自动生成订阅 Token

### 3. 查看节点信息

配置邮箱后，回到首页即可看到：
- 所有节点列表（带国旗标识）
- 每个节点的流量使用情况（进度条显示）
- 上传/下载流量统计
- 节点到期时间
- 流量重置时间

### 4. 使用订阅链接

在"个人资料"页面：
1. 找到订阅链接
2. 点击"复制"按钮
3. 在代理软件中添加订阅：
   - **Clash/Mihomo**：自动识别并返回 YAML 格式
   - **V2rayN/V2rayNG**：自动返回 Base64 格式
   - **其他客户端**：根据 User-Agent 智能判断

### 5. 管理员功能

#### 用户管理
- **创建用户**：添加新用户，可设置管理员权限
- **编辑用户**：修改用户信息、重置密码
- **删除用户**：删除不需要的用户（不能删除自己）
- **解锁 IP**：查看并解锁被锁定的 IP 地址

#### 服务器管理
- **添加服务器**：配置新的 3XUI 面板
- **编辑服务器**：修改服务器配置（包括订阅路径）
- **删除服务器**：移除不再使用的服务器

#### Mihomo 模板管理
- **创建模板**：添加自定义 YAML 配置模板
- **编辑模板**：修改现有模板
- **激活模板**：设置默认使用的模板
- **删除模板**：移除不需要的模板

## 安全特性

### IP锁定机制
- 登录失败5次后，IP地址将被锁定30分钟
- 锁定期间无法尝试登录
- 管理员可在管理面板手动解锁IP

### 密码安全
- 所有密码使用 Werkzeug 进行哈希加密
- 密码最低长度要求6位
- 建议使用强密码

### 日志记录
所有重要操作都会记录在 `app.log` 文件中，包括：
- 用户登录/登出
- 登录失败记录
- IP锁定/解锁
- 用户创建/删除
- 管理员操作

## 🔒 安全建议

### 生产环境部署

⚠️ **必须操作**：

1. **修改 SECRET_KEY**
   ```bash
   # 生成强随机密钥
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

2. **使用 HTTPS**
   - 配置 Nginx/Caddy 反向代理
   - 使用 Let's Encrypt 免费证书

3. **定期备份**
   ```bash
   # 备份数据库
   cp instance/subboard.db backups/subboard-$(date +%Y%m%d).db
   ```

4. **修改默认密码**
   - 首次登录后立即修改管理员密码
   - 定期更新密码

5. **限制访问**
   - 使用防火墙限制访问 IP
   - 配置 Nginx 访问控制

## 🔌 订阅 API

### 接口地址

```
GET /sub?token={your_token}
```

### 智能格式识别

根据客户端 User-Agent 自动返回对应格式：

| 客户端 | User-Agent 关键词 | 返回格式 |
|--------|------------------|----------|
| Clash / Mihomo | `clash`, `mihomo` | YAML 配置 |
| V2rayN / V2rayNG | `v2ray` | Base64 编码 |
| 其他客户端 | - | Base64 编码 |

### 返回内容

**Base64 格式：**
- **Content-Type**: `text/plain`
- **Body**: Base64 编码的节点列表（每行一个节点）

**Mihomo YAML 格式：**
- **Content-Type**: `application/x-yaml`
- **Body**: YAML 格式的 Clash/Mihomo 配置

**通用响应头：**
- `Subscription-Userinfo`: 流量统计信息
  - `upload`: 总上传流量（字节）
  - `download`: 总下载流量（字节）
  - `total`: 总流量限额（字节）
  - `expire`: 过期时间戳（秒）
- `Profile-Update-Interval`: 更新间隔（小时）

## 🔄 重置管理员密码

如果忘记了管理员密码：

**传统部署：**
```bash
# 删除数据库
rm instance/subboard.db

# 重启应用
python app.py

# 查看新生成的管理员密码
```

**Docker 部署：**
```bash
# 停止服务
docker-compose down

# 删除数据卷
rm -rf instance/subboard.db

# 重启服务
docker-compose up -d

# 查看管理员密码
docker-compose logs | grep "管理员密码"
```

## 📄 许可证

本项目采用 MIT 许可证。详见 [LICENSE](LICENSE) 文件。

## ⚠️ 免责声明

本项目仅供学习和个人使用。请确保遵守当地法律法规，合理合法使用本工具。

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📧 联系方式

如有问题或建议，请提交 Issue。

---

**⭐ 如果这个项目对您有帮助，请给个 Star！**

