from PIL import Image

def check_ico_file(file_path):
    try:
        img = Image.open(file_path)
        if img.format != "ICO":
            print("❌ 错误：文件不是标准ICO格式（实际是PNG或其他格式）")
        else:
            print("✅ 文件是标准ICO格式")
            print(img.width)
            print("包含的尺寸:", [f"{w}x{h}" for (w, h) in img.size])
    except Exception as e:
        print(f"❌ 文件损坏或无法读取: {str(e)}")

check_ico_file("favicon.ico")