# -*- coding: utf-8 -*-
"""绘卷万能图片提取器单元测试套件。

覆盖：
1. 单条消息多图按序提取
2. 引用回复单层穿透 (Q2->A)
3. 引用图与自带图智能合并 (Q4->A)
4. 商城表情 mface 与 DictComponent 包装识别
5. 上限最多 3 张截断
6. 前置等比防爆降采样 (Q3->A: 2400x1600 -> 1200x800)
7. get_recent_image() 向下兼容性
"""

import asyncio
import base64
import io
import os
import sys
from PIL import Image

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

art_dir = os.path.abspath("Maibot-new/plugins/1021143806_mais_art_journal")
sys.path.insert(0, art_dir)

from tests import conftest
conftest._ensure_maibot_sdk_stub()

from core.utils.image_utils import ImageProcessor

# 辅助函数：生成纯色测试图片 Base64
def create_test_image_b64(width: int, height: int, color: str = "red") -> str:
    im = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    im.save(buf, format="JPEG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")

print("==================================================")
print("[START] 绘卷万能图片提取器本地单元测试")
print("==================================================")

# 预生成小图与超大图
img_red = create_test_image_b64(200, 200, "red")
img_green = create_test_image_b64(200, 200, "green")
img_blue = create_test_image_b64(200, 200, "blue")
img_yellow = create_test_image_b64(200, 200, "yellow")
img_huge = create_test_image_b64(2400, 1600, "purple") # 超大图用于防爆测试

class MockMessageContext:
    def __init__(self, target_db):
        self.target_db = target_db
    async def get_by_id(self, message_id, chat_id="", include_binary_data=True):
        return self.target_db.get(message_id)

class MockCtx:
    def __init__(self, target_db):
        self.message = MockMessageContext(target_db)

class DummyAction:
    def __init__(self, message, ctx=None):
        self.message = message
        self.ctx = ctx
        self.log_prefix = "[Test]"
        self.chat_id = "test_chat"

async def run_tests():
    # ----------------------------------------------------
    # 用例 1：单条消息多图按序收集
    # ----------------------------------------------------
    print("\n[Test 1] 单条消息多图按序提取测试")
    msg1 = {
        "raw_message": [
            {"type": "text", "data": {"text": "/dr 把图1放到图2"}},
            {"type": "image", "binary_data_base64": img_red},
            {"type": "image", "binary_data_base64": img_green},
        ]
    }
    processor = ImageProcessor(DummyAction(msg1))
    imgs = await processor.get_all_recent_images()
    assert len(imgs) == 2, f"期望提取 2 张图片，实际提取 {len(imgs)}"
    assert imgs[0] == img_red, "图1顺序不匹配"
    assert imgs[1] == img_green, "图2顺序不匹配"
    # 验证向下兼容
    assert await processor.get_recent_image() == img_red, "get_recent_image 兼容失败"
    print("  [PASS] 成功按顺序提取图1与图2，向下兼容性良好")

    # ----------------------------------------------------
    # 用例 2：单层引用回复穿透与 QQ 商城表情 mface 识别 (Q2->A)
    # ----------------------------------------------------
    print("\n[Test 2] 引用回复穿透与商城表情 mface 识别测试")
    target_store_sticker_msg = {
        "message_id": "msg_target_123",
        "raw_message": [
            {
                "type": "mface", # QQ 商城表情
                "binary_data_base64": img_yellow,
                "data": {"emoji_id": "999", "summary": "[商城表情]"},
            }
        ],
    }
    current_reply_msg = {
        "raw_message": [
            {"type": "reply", "data": {"target_message_id": "msg_target_123"}},
            {"type": "text", "data": {"text": "/dr 画成水彩风"}},
        ]
    }
    mock_ctx = MockCtx({"msg_target_123": target_store_sticker_msg})
    processor2 = ImageProcessor(DummyAction(current_reply_msg, ctx=mock_ctx))
    imgs2 = await processor2.get_all_recent_images()
    assert len(imgs2) == 1, f"期望从被引用表情包穿透提取 1 张图，实际 {len(imgs2)}"
    assert imgs2[0] == img_yellow, "穿透提取的表情包数据不符"
    print("  [PASS] 成功穿透单层 reply 回复并识别被引用的 mface 表情包")

    # ----------------------------------------------------
    # 用例 3：引用图为图1 + 当前自带图为图2 智能合并序列 (Q4->A)
    # ----------------------------------------------------
    print("\n[Test 3] 智能合并序列测试 (引用图=图1, 自带图=图2)")
    current_multi_and_reply = {
        "raw_message": [
            {"type": "reply", "data": {"target_message_id": "msg_target_123"}}, # 里面是 yellow
            {"type": "text", "data": {"text": "/dr 把图1放到图2"}},
            {"type": "image", "binary_data_base64": img_blue}, # 本消息自带 blue
        ]
    }
    processor3 = ImageProcessor(DummyAction(current_multi_and_reply, ctx=mock_ctx))
    imgs3 = await processor3.get_all_recent_images()
    assert len(imgs3) == 2, f"期望合并为 2 张图，实际 {len(imgs3)}"
    assert imgs3[0] == img_yellow, "合并序列中被引用的图应为图1"
    assert imgs3[1] == img_blue, "合并序列中自带的图应为图2"
    print("  [PASS] 序列合并成功：引用图自动定为图1，自带图自动排为图2")

    # ----------------------------------------------------
    # 用例 4：上限最多截断保留 3 张
    # ----------------------------------------------------
    print("\n[Test 4] 上限硬性截断测试 (最多 3 张)")
    msg_many = {
        "raw_message": [
            {"type": "image", "binary_data_base64": img_red},
            {"type": "image", "binary_data_base64": img_green},
            {"type": "image", "binary_data_base64": img_blue},
            {"type": "image", "binary_data_base64": img_yellow}, # 第4张应被截断
        ]
    }
    processor4 = ImageProcessor(DummyAction(msg_many))
    imgs4 = await processor4.get_all_recent_images()
    assert len(imgs4) == 3, f"期望上限截断为 3 张，实际 {len(imgs4)}"
    assert imgs4[2] == img_blue, "第 3 张图不符"
    print("  [PASS] 超过 3 张的图片被安全截断，防止滥用")

    # ----------------------------------------------------
    # 用例 5：前置等比防爆降采样 (Q3->A: 2400x1600 -> 1200x800)
    # ----------------------------------------------------
    print("\n[Test 5] 前置防爆等比降采样测试")
    downsampled = processor._downsample_image_if_needed(img_huge)
    im_down = Image.open(io.BytesIO(base64.b64decode(downsampled)))
    assert max(im_down.size) <= 1200, f"降采样后长边应不超过1200: 实际 {im_down.size}"
    assert im_down.size == (1200, 800), f"2400x1600 等比缩放期望为 1200x800，实际 {im_down.size}"
    print(f"  [PASS] 2400x1600 超大图成功等比降采样为 {im_down.size}，内存护城河有效")

    # ----------------------------------------------------
    # 用例 6：宿主 DictComponent 包装层穿透测试
    # ----------------------------------------------------
    print("\n[Test 6] 宿主 DictComponent 包装层穿透测试")
    msg_dict_wrap = {
        "raw_message": [
            {
                "type": "dict",
                "data": {
                    "type": "mface",
                    "binary_data_base64": img_green,
                },
            },
        ]
    }
    processor6 = ImageProcessor(DummyAction(msg_dict_wrap))
    imgs6 = await processor6.get_all_recent_images()
    assert len(imgs6) == 1 and imgs6[0] == img_green, "DictComponent 包装穿透解析失败"
    print("  [PASS] 成功穿透宿主 DictComponent 包装层提取表情包")

    print("\n==================================================")
    print("[DONE] 绘卷万能图片提取器全部 6 大核心用例 100% 满分通过！")
    print("==================================================")

asyncio.run(run_tests())
