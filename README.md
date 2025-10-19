# SubBoard - 订阅节点管理面板

一个基于 Flask 的订阅节点管理面板，用于管理和分发 3XUI 节点订阅。

[![Docker Build](https://github.com/1m1ng/SubBoard/actions/workflows/docker-build.yml/badge.svg)](https://github.com/1m1ng/SubBoard/actions/workflows/docker-build.yml)
[![Code Quality](https://github.com/1m1ng/SubBoard/actions/workflows/code-quality.yml/badge.svg)](https://github.com/1m1ng/SubBoard/actions/workflows/code-quality.yml)
[![Docker Pulls](https://img.shields.io/docker/pulls/huiji2333/subboard)](https://hub.docker.com/r/huiji2333/subboard)
[![Docker Image Size](https://img.shields.io/docker/image-size/huiji2333/subboard/latest)](https://hub.docker.com/r/huiji2333/subboard)
[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0-green.svg)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/github/license/1m1ng/SubBoard)](LICENSE)

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

```docker-compose
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
      # 时区配置
      - TZ=Asia/Shanghai
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

