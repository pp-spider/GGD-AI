from PIL import Image, ImageDraw, ImageFont

# 创建 256x256 的图标
sizes = [16, 32, 48, 64, 128, 256]
images = []

for size in sizes:
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # 绘制一个简单的渐变蓝色方块
    for i in range(size):
        color = (0, 120 + int(60 * i / size), 212, 255)
        draw.rectangle([0, i, size, i+1], fill=color)
    # 添加文字 GGD
    if size >= 32:
        try:
            font = ImageFont.truetype('arial.ttf', size//3)
        except:
            font = ImageFont.load_default()
        text = 'GGD'
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x = (size - text_width) // 2
        y = (size - text_height) // 2
        draw.text((x, y), text, fill='white', font=font)
    images.append(img)

# 保存为 ICO
images[0].save('D:/PythonProjects/GGD-AI/src-tauri/icons/icon1.ico',
               format='ICO', sizes=[(s, s) for s in sizes])
print('icon1.ico created successfully')

# 同时创建 PNG 图标
for size in [32, 128]:
    idx = sizes.index(size)
    images[idx].save(f'D:/PythonProjects/GGD-AI/src-tauri/icons/{size}x{size}.png')
    print(f'{size}x{size}.png created')

# 创建 128x128@2x.png (256x256)
images[-1].save('D:/PythonProjects/GGD-AI/src-tauri/icons/128x128@2x.png')
print('128x128@2x.png created')