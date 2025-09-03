from PIL import Image

from PIL import Image, ImageOps
import os


def convert_to_ico(input_path, output_path, sizes=None, optimize=True):
    """
    将图片转换为标准Windows ICO格式

    参数:
        input_path (str): 输入图片路径（支持PNG/JPG等）
        output_path (str): 输出ICO文件路径
        sizes (list): 包含的尺寸列表，默认[16, 32, 48, 256]
        optimize (bool): 是否优化文件大小

    返回:
        bool: 转换是否成功
    """
    # 默认包含所有标准尺寸
    if sizes is None:
        sizes = [16, 32, 48, 256]

    try:
        # 打开源图片并转换为RGBA模式（支持透明通道）
        with Image.open(input_path) as img:
            # 自动修正方向（解决手机照片旋转问题）
            img = ImageOps.exif_transpose(img)

            # 转换为RGBA模式（如果原图是P模式会丢失透明度）
            if img.mode != 'RGBA':
                img = img.convert('RGBA')

            # 生成所有尺寸版本
            icons = []
            for size in sizes:
                # 高质量缩放到目标尺寸
                resized = img.resize((size, size), Image.Resampling.LANCZOS)
                icons.append(resized)

            # 保存为ICO格式（自动包含所有尺寸）
            icons[0].save(
                output_path,
                format='ICO',
                append_images=icons[1:],
                optimize=optimize,
                quality=95,
                bits=32  # 强制32位色深（带Alpha通道）
            )

        print(f"✅ 转换成功: {os.path.basename(input_path)} -> {os.path.basename(output_path)}")
        print(f"   包含尺寸: {sizes}")
        return True

    except Exception as e:
        print(f"❌ 转换失败: {str(e)}")
        return False


# 使用示例
if __name__ == '__main__':
    # 示例转换（PNG/JPG -> ICO）
    convert_to_ico('angry.gif', 'favicon.ico')

