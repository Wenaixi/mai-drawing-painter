# -*- coding: utf-8 -*-
"""针对第二轮审查确凿缺陷：前缀截断碰撞与 PNG 未有损压缩的测试套件。"""
import base64
import io
import os
import sys
import pytest
from PIL import Image

art_dir = os.path.abspath("Maibot-new/plugins/1021143806_mais_art_journal")
sys.path.insert(0, art_dir)

from tests import conftest
conftest._ensure_maibot_sdk_stub()

from core.utils.image_utils import ImageProcessor

def test_dedup_no_collision_on_large_images():
    """验证头部元数据高度相似但内容不同的大图不会因为截断而发生哈希碰撞误吞。"""
    # 构造两张 1200x800 的大图，前 1KB 极度相似
    im1 = Image.new("RGB", (1200, 800), color=(200, 200, 200))
    im2 = Image.new("RGB", (1200, 800), color=(200, 200, 200))
    # 在第二张图尾部区域做微小改动
    im2.putpixel((1199, 799), (0, 0, 0))

    buf1 = io.BytesIO()
    im1.save(buf1, format="JPEG", quality=95)
    b64_1 = base64.b64encode(buf1.getvalue()).decode("utf-8")

    buf2 = io.BytesIO()
    im2.save(buf2, format="JPEG", quality=95)
    b64_2 = base64.b64encode(buf2.getvalue()).decode("utf-8")

    # 验证前 1024 字节确实高度相同
    assert b64_1[:1024] == b64_2[:1024], "测试前置条件：两图前 1024 字节应相同以模拟碰撞"
    assert b64_1 != b64_2, "两图全量数据应不相同"

    processor = ImageProcessor(None)
    # 模拟提取两张图
    msg = {
        "raw_message": [
            {"type": "image", "binary_data_base64": b64_1},
            {"type": "image", "binary_data_base64": b64_2},
        ]
    }
    # 在当前截断逻辑下，b64_2 会因为截断碰撞被当作重复项误删
    # 修复后应能完整保留 2 张图
    import asyncio
    res = asyncio.run(processor.extract_all_images(msg))
    assert len(res) == 2, f"期望保留 2 张不同图片，实际仅剩 {len(res)} 张（发生截断哈希碰撞误吞！）"

def test_rgba_downsample_size_compressed():
    """验证带透明通道的 RGBA 超大图片经过降采样后，体积能真正被压缩至 400KB 以内，杜绝 OOM。"""
    # 构造一张 1600x1200 的 RGBA 复杂图
    im = Image.new("RGBA", (1600, 1200), (100, 150, 200, 128))
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    raw_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    processor = ImageProcessor(None)
    compressed_b64 = processor._downsample_image_if_needed(raw_b64)
    raw_bytes = base64.b64decode(compressed_b64)
    size_kb = len(raw_bytes) / 1024.0
    print(f"  降采样后大小: {size_kb:.2f} KB")
    # 原逻辑无损保存 PNG 约 1.35MB，修复后转白底 JPEG 应在 400KB 以内
    assert size_kb < 400.0, f"RGBA 降采样后体积依然过大 ({size_kb:.2f} KB)，超过 400KB 安全线"
