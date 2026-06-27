# API Key Validator

API Key 批量验证管理工具

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

## 快速启动

### 直接运行

```bash
pip install flask requests
python app.py
```

浏览器打开 http://localhost:8899

### Docker运行

```bash
docker-compose up -d
```

## 默认端点

| 名称 | URL |
|------|-----|
| SGP OpenAI | https://token-plan-sgp.xiaomimimo.com/v1 |
| CN OpenAI | https://token-plan-cn.xiaomimimo.com/v1 |
| SGP Anthropic | https://token-plan-sgp.xiaomimimo.com/anthropic |
| CN Anthropic | https://token-plan-cn.xiaomimimo.com/anthropic |

## 文件说明

- `app.py` - Flask Web应用
- `api_validator.py` - 核心验证逻辑
- `api_keys.json` - Key数据存储（自动生成）
- `Dockerfile` - Docker镜像配置
- `docker-compose.yml` - Docker Compose配置
