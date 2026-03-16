import cv2
import numpy as np
import os


def extract_player_num(image_path):
    # 读取图像（灰度模式）
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    file_name = os.path.basename(image_path)
    if img is None:
        print("图像读取失败")
        return None
    _, binary_otsu = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    t_w, t_h = img.shape
    total_square = t_w * t_h
    # 找白色连通域（卡片）
    num_labels, _, stats, _ = cv2.connectedComponentsWithStats(binary_otsu)
    cards = []

    # 模板匹配字符
    templates = {
        '01': cv2.imread(f'{template_path}/01.png', 0),
        '02': cv2.imread(f'{template_path}/02.png', 0),
        '06': cv2.imread(f'{template_path}/06.png', 0),
        '10': cv2.imread(f'{template_path}/10.png', 0),
        '11': cv2.imread(f'{template_path}/11.png', 0),
        '12': cv2.imread(f'{template_path}/12.png', 0),
        '13': cv2.imread(f'{template_path}/13.png', 0),
    }

    for i in range(1, num_labels):
        x, y, w, h, area = stats[i]
        square = w * h
        white_ratio = area / square
        # 卡片占整张图的大概0.0184，白色占比卡片的0.7以上，卡片长宽比2-3

        if total_square * 0.01 < square < total_square * 0.02 and white_ratio > 0.7 and 2.0 < w / h < 3.0:
            cards.append(img[y:y + h, x:x + w])
            cv2.imwrite(f'./temp_images/{file_name.split(".")[0]}_card_{len(cards)}.png', img[y:y + h, x:x + w])
            cv2.imwrite(f'./temp_images/{file_name.split(".")[0]}_card_{len(cards)}_.png', img[y:int(y + h*0.3), x:int(x + w*0.15)])

            for digit, template in templates.items():
                # 模板匹配
                res = cv2.matchTemplate(img[y:int(y + h*0.3), x:int(x + w*0.15)], template, cv2.TM_CCOEFF_NORMED)
                threshold = 0.8
                loc = np.where(res >= threshold)
                if len(loc[0]) > 0:
                    return digit
    return None



template_path = './template_imgs'
for ii in os.listdir('./test_imgs'):
    num = extract_player_num(f'./test_imgs/{ii}')
    print(f'./test_imgs/{ii}：{num}')