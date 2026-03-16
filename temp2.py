import cv2
import numpy as np
import os
import json
from datetime import datetime


class GameCardExtractor:
    """
    游戏玩家卡片自动提取器
    适用于鹅鸭杀/狼人杀等游戏的二值化界面截图
    """

    def __init__(self, min_area=8000, max_area=30000, min_aspect=2.0, max_aspect=3.0):
        self.min_area = min_area
        self.max_area = max_area
        self.min_aspect = min_aspect
        self.max_aspect = max_aspect

    def extract(self, image_path, output_dir='./extracted_cards'):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 开始处理: {image_path}")

        # 读取图像
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"无法读取图像: {image_path}")

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape
        os.makedirs(output_dir, exist_ok=True)

        # 二值化并去噪
        _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
        kernel = np.ones((2, 2), np.uint8)
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)

        # 连通域分析
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(binary, connectivity=8)

        cards = []
        debug_img = img.copy()
        total_area = h * w

        print(f"扫描 {num_labels - 1} 个区域中...")

        for i in range(1, num_labels):
            x, y, bw, bh, area = stats[i]
            aspect = bw / float(bh) if bh > 0 else 0

            # 智能过滤条件
            if not (self.min_area < area < self.max_area):
                continue
            if not (self.min_aspect < aspect < self.max_aspect):
                continue
            if area > total_area * 0.5:  # 排除全图背景
                continue

            # 验证内容（检查文字占比）
            roi = binary[y:y + bh, x:x + bw]
            black_ratio = np.sum(roi == 0) / area
            if not (0.05 < black_ratio < 0.6):
                continue

            # 提取并记录
            card_img = img[y:y + bh, x:x + bw]
            cards.append({
                'idx': len(cards),
                'bbox': (int(x), int(y), int(bw), int(bh)),
                'img': card_img
            })

            # 绘制调试图像
            cv2.rectangle(debug_img, (x, y), (x + bw, y + bh), (0, 255, 0), 2)
            cv2.putText(debug_img, f"#{len(cards) - 1}", (x, y - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

        # 按位置排序（从上到下，从左到右）
        cards.sort(key=lambda c: (c['bbox'][1], c['bbox'][0]))

        # 保存结果
        for card in cards:
            filename = f"card_{card['idx']:02d}_{card['bbox'][0]}_{card['bbox'][1]}.png"
            path = os.path.join(output_dir, filename)
            cv2.imwrite(path, card['img'])
            card['path'] = path

        cv2.imwrite(os.path.join(output_dir, "_debug.png"), debug_img)

        # 保存元数据
        meta = {
            'timestamp': datetime.now().isoformat(),
            'image_size': [w, h],
            'count': len(cards),
            'cards': [{'idx': c['idx'], 'bbox': c['bbox'], 'path': c['path']} for c in cards]
        }
        with open(os.path.join(output_dir, "_info.json"), 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        print(f"✓ 成功提取 {len(cards)} 张卡片，保存至: {output_dir}/")
        return cards, debug_img


# ==================== 使用示例 ====================
if __name__ == "__main__":
    # 创建提取器（如果检测不全，调整以下参数）
    extractor = GameCardExtractor(
        min_area=8000,  # 最小面积（过滤小噪点）
        max_area=30000,  # 最大面积（过滤背景）
        min_aspect=2.0,  # 最小长宽比（卡片是横向矩形）
        max_aspect=3.0  # 最大长宽比
    )

    # 执行提取
    cards, debug_img = extractor.extract(
        image_path='temp_binary_otsu.jpg',  # 修改为你的图片路径
        output_dir='./player_cards'  # 输出目录
    )

    # 打印结果
    print("\n提取详情:")
    for c in cards:
        print(f"  [{c['idx']}] 位置:{c['bbox']} → {c['path']}")