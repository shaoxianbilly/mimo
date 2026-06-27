# API Key Validator

API Key 批量验证管理工具 - 支持Docker一键部署

## 功能

- 粘贴杂乱文本自动提取Key（支持Base64解码、中文干扰字符移除）
- 自动识别区域（新加坡/国内）
- 自动识别接口类型（OpenAI/Anthropic）
- Key状态管理（可用/限流中/不可用）
- 延迟测试
- 自动定时重测（2-5分钟随机）
- 一键复制Key/Key+URL
- 导出可用Key
- 删除/清空功能

## Docker 一键部署

### 方式一：Docker Compose（推荐）

```bash
# 克隆项目
git clone https://github.com/shaoxianbilly/mimo.git
cd mimo

# 一键启动
docker-compose up -d

# 访问
open http://localhost:8899
```

### 方式二：Docker 命令

```bash
# 构建镜像
docker build -t api-key-validator .

# 运行容器
docker run -d \
  --name api-key-validator \
  -p 8899:8899 \
  -v $(pwd)/data:/app/data \
  --restart unless-stopped \
  api-key-validator
```

### 常用命令

```bash
# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down

# 重启服务
docker-compose restart

# 更新并重启
git pull && docker-compose up -d --build
```

### 自定义端口

修改 `docker-compose.yml` 中的端口映射：

```yaml
ports:
  - "9000:8899"  # 改为9000端口
```

## 本地运行（不使用Docker）

```bash
# 安装依赖
pip install flask requests

# 启动
python app.py

# 访问
open http://localhost:8899
```

## 默认端点

| 名称 | URL |
|------|-----|
| SGP OpenAI | https://token-plan-sgp.xiaomimimo.com/v1 |
| CN OpenAI | https://token-plan-cn.xiaomimimo.com/v1 |
| SGP Anthropic | https://token-plan-sgp.xiaomimimo.com/anthropic |
| CN Anthropic | https://token-plan-cn.xiaomimimo.com/anthropic |

## 文件说明

| 文件 | 说明 |
|------|------|
| `app.py` | Flask Web应用主程序 |
| `api_validator.py` | 核心验证逻辑 |
| `api_keys.json` | Key数据存储（自动生成） |
| `Dockerfile` | Docker镜像配置 |
| `docker-compose.yml` | Docker Compose配置 |
| `requirements.txt` | Python依赖 |

## 环境要求

- Docker 20.0+
- Docker Compose 2.0+
- 或 Python 3.9+

## License

MIT
