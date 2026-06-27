#!/bin/bash
# Mac .app 构建脚本

echo "================================"
echo "  构建 API Key Validator.app"
echo "================================"

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到python3"
    exit 1
fi

# 安装依赖
echo "安装依赖..."
pip3 install -r requirements.txt
pip3 install pyinstaller

# 清理旧构建
echo "清理旧构建..."
rm -rf build dist

# 构建.app
echo "构建中..."
pyinstaller \
    --name "API Key Validator" \
    --windowed \
    --onefile \
    --add-data "api_validator.py:." \
    --icon NONE \
    app.py

# 检查结果
if [ -d "dist/API Key Validator.app" ]; then
    echo ""
    echo "================================"
    echo "  构建成功!"
    echo "================================"
    echo ""
    echo "应用位置: dist/API Key Validator.app"
    echo ""
    echo "移动到应用程序:"
    echo "  cp -r 'dist/API Key Validator.app' /Applications/"
    echo ""
    echo "或直接运行:"
    echo "  open 'dist/API Key Validator.app'"
    echo ""
else
    echo "构建失败，请检查错误信息"
    exit 1
fi
