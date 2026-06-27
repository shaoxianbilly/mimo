#!/bin/bash
# 构建脚本 (Mac + Windows)

echo "================================"
echo "  构建 API Key 管理器"
echo "================================"

# 检查Node.js
if ! command -v node &> /dev/null; then
    echo "错误: 未找到Node.js，请先安装: brew install node"
    exit 1
fi

# 安装依赖
echo "安装依赖..."
cd electron
npm install

# 构建Mac版本
echo "构建Mac版本..."
npm run build:mac

# 构建Windows版本 (需要Wine或在Windows上构建)
echo "构建Windows版本..."
npm run build:win

echo ""
echo "================================"
echo "  构建完成!"
echo "================================"
echo ""
echo "Mac:   dist-electron/mac/"
echo "Win:   dist-electron/win/"
echo ""
