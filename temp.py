import cv2
import os


def extract_player_cards(image_path):
    img = cv2.imread(image_path)
    file_name = os.path.basename(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)

    t_w, t_h, _ = img.shape
    total_square = t_w * t_h
    # 找白色连通域（卡片）
    num_labels, _, stats, _ = cv2.connectedComponentsWithStats(binary)
    cards = []

    for i in range(1, num_labels):
        x, y, w, h, area = stats[i]
        square = w * h
        white_ratio = area / square
        # 卡片占整张图的大概0.0184，白色占比卡片的0.7以上，卡片长宽比2-3
        if white_ratio > 0.7 and 2.0 < w / h < 3.0:
            cards.append(img[y:y + h, x:x + w])
            cv2.imwrite(f'./temp_images/{file_name.split(".")[0]}_card_{len(cards)}.png', img[y:y + h, x:x + w])

    return cards


# 使用
cards = extract_player_cards('./temp_binary_otsu.jpg')
print(f"提取了 {len(cards)} 张卡片")