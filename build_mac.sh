#!/bin/bash
# Mac .app 构建脚本 (Electron版本)

echo "================================"
echo "  构建 API Key 管理器.app"
echo "================================"

# 检查Node.js环境
if ! command -v node &> /dev/null; then
    echo "错误: 未找到Node.js，请先安装: brew install node"
    exit 1
fi

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到python3"
    exit 1
fi

# 安装Python依赖
echo "安装Python依赖..."
pip3 install flask requests

# 安装Electron依赖
echo "安装Electron依赖..."
cd electron
npm install

# 构建.app
echo "构建中..."
npm run build:mac

# 检查结果
if [ -d "../dist-electron/mac" ]; then
    echo ""
    echo "================================"
    echo "  构建成功!"
    echo "================================"
    echo ""
    echo "应用位置: dist-electron/mac/"
    echo ""
    echo "安装到应用程序:"
    echo "  cp -r 'dist-electron/mac/API Key 管理器.app' /Applications/"
    echo ""
else
    echo "构建失败，请检查错误信息"
    exit 1
fi
