import os

from rapidocr_onnxruntime import RapidOCR

# 自动下载模型，CPU 推理
engine = RapidOCR(
    det_model_path=None,  # 自动下载轻量模型
    rec_model_path=None,
    cls_model_path=None,
    thread_num=4 # 根据 CPU 核心数调整
)


root_path = "./temp_images/"
for i in os.listdir(root_path):
    img_path = os.path.join(root_path, i)
    result, elapse = engine(img_path)
    print(img_path)
    for box, text, score in result:
        print(f"{text} (置信度: {score:.2f})")
