#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GGD-AI Python后端服务入口

启动FastAPI服务，提供HTTP API和WebSocket接口
"""

import uvicorn
import sys
import os

# 确保可以导入src目录中的模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api_server import app, manager, controller


def main():
    """主函数"""
    print("=" * 60)
    print("GGD-AI Python后端服务")
    print("=" * 60)
    print("API文档: http://127.0.0.1:9876/docs")
    print("WebSocket: ws://127.0.0.1:9876/ws")
    print("=" * 60)
    print()

    # 启动uvicorn服务器
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=9876,
        log_level="info"
    )


if __name__ == "__main__":
    main()
