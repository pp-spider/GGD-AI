from PIL import Image

# 打开PNG图片
img = Image.open('src-tauri/icons/128x128@2x.png')

# 确保是RGBA模式
if img.mode != 'RGBA':
    img = img.convert('RGBA')

# 保存为ICO格式，包含多种尺寸
img.save('src-tauri/icons/icon.ico', format='ICO',
         sizes=[(256, 256), (128, 128), (64, 64), (32, 32), (16, 16)])

print('ICO file generated successfully!')
