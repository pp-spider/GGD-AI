import os
import base64
import json
import re

from openai import OpenAI

client = OpenAI(
    api_key = "sk-",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
)

# 在这里，你需要将 kimi.png 文件替换为你想让 Kimi 识别的图片的地址
image_path = "./test_imgs/temp1.png"

with open(image_path, "rb") as f:
    image_data = f.read()

# 我们使用标准库 base64.b64encode 函数将图片编码成 base64 格式的 image_url
image_url = f"data:image/{os.path.splitext(image_path)[1]};base64,{base64.b64encode(image_data).decode('utf-8')}"

system_prompt = """
你是游戏玩家ID提取器，最终返回的结果格式必须遵循：
```json
[
    {"id": "01", "name": "1号玩家"},
    {"id": "02", "name": "小明"},
    {"id": "02", "name": "刑天"}
]
```
"""

completion = client.chat.completions.create(
    model="qwen3-vl-plus",
    messages=[
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            # 注意这里，content 由原来的 str 类型变更为一个 list，这个 list 中包含多个部分的内容，图片（image_url）是一个部分（part），
            # 文字（text）是一个部分（part）
            "content": [
                {
                    "type": "image_url",  # <-- 使用 image_url 类型来上传图片，内容为使用 base64 编码过的图片内容
                    "image_url": {
                        "url": image_url,
                    },
                },
                {
                    "type": "text",
                    "text": "请提取图片左侧玩家展示区每个玩家的名称id。",  # <-- 使用 text 类型来提供文字指令，例如“描述图片内容”
                },
            ],
        },
    ],
)

j_text = completion.choices[0].message.content

def extract_json_from_markdown(text):
    """从 Markdown 代码块中提取 JSON"""
    pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
    match = re.search(pattern, text)
    if match:
        return json.loads(match.group(1))
    return json.loads(text)  # 如果没有标记，直接解析

data = extract_json_from_markdown(j_text)
print(data)