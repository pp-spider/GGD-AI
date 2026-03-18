#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 玩家信息提取模块

使用 Moonshot AI API 从游戏截图中提取玩家ID和名称
"""

import os
import base64
import json
import re
from typing import List, Dict, Optional
import numpy as np
import cv2
from openai import OpenAI

# 从环境变量读取配置
API_KEY = os.environ.get("QWEN_API_KEY")
API_BASE = os.environ.get("QWEN_BASE_URL")
MODEL = os.environ.get("QWEN_MODEL")

SYSTEM_PROMPT = """
你是游戏玩家ID提取器，从鹅鸭杀游戏截图中提取左侧玩家列表的ID和名称。
最终返回的结果格式必须遵循：
```json
[
    {"id": "01", "name": "玩家名称1"},
    {"id": "02", "name": "玩家名称2"}
]
```
只返回JSON数组，不要其他解释。
"""


def encode_image_to_base64(image_array: np.ndarray, max_size: tuple = (1920, 1080)) -> str:
    """将numpy图像数组转为base64编码的data URL，超过指定尺寸则压缩"""
    h, w = image_array.shape[:2]
    max_w, max_h = max_size

    # 如果图像超过最大尺寸，进行等比例压缩
    if w > max_w or h > max_h:
        scale_w = max_w / w
        scale_h = max_h / h
        scale = min(scale_w, scale_h)  # 取较小比例确保不超出边界
        new_w = int(w * scale)
        new_h = int(h * scale)
        image_array = cv2.resize(image_array, (new_w, new_h), interpolation=cv2.INTER_AREA)
        print(f"[ImageEncode] 图像已压缩: {w}x{h} -> {new_w}x{new_h}")

    # 转换为JPEG格式（更小体积）或PNG格式
    # 使用JPEG格式压缩率更高，质量90%平衡清晰度和大小
    encode_params = [cv2.IMWRITE_JPEG_QUALITY, 90]
    _, buffer = cv2.imencode('.jpg', image_array, encode_params)
    base64_str = base64.b64encode(buffer).decode('utf-8')
    return f"data:image/jpeg;base64,{base64_str}"


def extract_player_info(image_array: np.ndarray, timeout: float = 15.0) -> List[Dict[str, str]]:
    """
    使用AI从游戏截图中提取玩家ID和名称

    Args:
        image_array: 截图图像数组 (BGR格式)
        timeout: API调用超时时间（秒），默认15秒

    Returns:
        List[Dict]: 玩家列表 [{"id": "01", "name": "小明"}, ...]
    """
    if not API_KEY:
        print("[Extractor] 警告: 未设置API_KEY环境变量")
        return []

    import time
    start_time = time.time()

    try:
        print(f"[Extractor] 初始化客户端...")
        client = OpenAI(api_key=API_KEY, base_url=API_BASE, timeout=timeout)

        print(f"[Extractor] 编码图像...")
        image_url = encode_image_to_base64(image_array)
        print(f"[Extractor] 图像大小: {len(image_url)} 字符")

        print(f"[Extractor] 调用 API (模型: {MODEL}, 超时: {timeout}s)...")
        api_start = time.time()

        completion = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": image_url}},
                        {"type": "text", "text": "请提取图片左侧玩家展示区每个玩家的ID和名称。"}
                    ]
                }
            ]
        )

        api_time = time.time() - api_start
        print(f"[Extractor] API调用完成，耗时: {api_time:.2f}s")

        response_text = completion.choices[0].message.content
        result = parse_model_response(response_text)

        total_time = time.time() - start_time
        print(f"[Extractor] 提取完成，共 {len(result)} 位玩家，总耗时: {total_time:.2f}s")
        return result

    except Exception as e:
        total_time = time.time() - start_time
        print(f"[Extractor] 提取失败 (耗时: {total_time:.2f}s): {e}")
        return []


def parse_model_response(text: str) -> List[Dict[str, str]]:
    """解析返回的markdown JSON"""
    # 提取 ```json ... ``` 中的内容
    pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
    match = re.search(pattern, text)

    try:
        if match:
            json_str = match.group(1)
        else:
            json_str = text

        data = json.loads(json_str)
        if isinstance(data, list):
            return [{"id": str(p.get("id", "")), "name": str(p.get("name", ""))}
                    for p in data if p.get("id")]
        return []
    except json.JSONDecodeError as e:
        print(f"[Extractor] JSON解析失败: {e}")
        return []


def verify_id_match(template_id: str, ai_id: str) -> bool:
    """验证模板匹配ID和 ID是否一致"""
    # 去除前导零比较
    t_num = template_id.lstrip('0') or '0'
    k_num = ai_id.lstrip('0') or '0'
    return t_num == k_num


def verify_and_merge_ids(template_id: Optional[str], ai_results: List[Dict]) -> Optional[Dict[str, str]]:
    """
    校验模板匹配的ID与结果，返回匹配的玩家信息

    Args:
        template_id: 模板匹配提取的玩家ID (如 "01", "02")
        ai_results: 提取的玩家列表

    Returns:
        Dict[str, str] or None: 匹配的玩家信息 {"id": "01", "name": "小明"}
    """
    if not template_id or not ai_results:
        return None

    for player in ai_results:
        if verify_id_match(template_id, player.get("id", "")):
            return player

    return None


if __name__ == "__main__":
    # 测试代码
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from screen_monitor import ScreenCapture
    from window_selector import select_window

    print("请选择游戏窗口...")
    hwnd, title = select_window()

    if hwnd:
        print(f"已选择窗口: {title}")
        capture = ScreenCapture(hwnd)
        img = capture.capture()

        if img is not None:
            print("正在使用AI提取玩家信息...")
            players = extract_player_info(img)
            print(f"提取到 {len(players)} 位玩家:")
            for p in players:
                print(f"  ID: {p['id']}, 名称: {p['name']}")
        else:
            print("截图失败")

        capture.release()
    else:
        print("未选择窗口")
