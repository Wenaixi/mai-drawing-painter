# -*- coding: utf-8 -*-
"""群友命令正则映射与 OpenAI 多图 API 客户端打通测试套件。

覆盖：
1. 群友口语图号精准映射为 Image 1 / Image 2 / Image 3 (Q1->B)
2. GenerationRequest 多图与单图双向自同步契约
3. OpenAiClient 多图 Payload (images: [...]) 构造与 /images/edits 路由
4. OpenAiClient 单图编辑向后兼容性 (image: data_uri)
"""

import base64
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

art_dir = os.path.abspath("Maibot-new/plugins/1021143806_mais_art_journal")
sys.path.insert(0, art_dir)

from tests import conftest
conftest._ensure_maibot_sdk_stub()

from core.commands.generate import _map_image_references
from core.pipeline.request import GenerationRequest
from core.api_clients.openai_client import OpenAIClient

print("==================================================")
print("[START] 绘卷多图命令映射与 OpenAI 客户端打通测试")
print("==================================================")

# ----------------------------------------------------
# 用例 1：中文口语图号正则映射 (Q1->B)
# ----------------------------------------------------
print("\n[Test 1] 中文口语图号正则精准映射测试")
cases = [
    ("把图1的人换成图2的衣服", "把Image 1的人换成Image 2的衣服"),
    ("图一和图二融合，参考图三的风格", "Image 1和Image 2融合，参考Image 3的风格"),
    ("第一张图作为主角，第二张图作为背景", "Image 1作为主角，Image 2作为背景"),
    ("第一幅图调色，第三幅图构图", "Image 1调色，Image 3构图"),
    ("单纯画一只小猫，不涉及图号", "单纯画一只小猫，不涉及图号"),
]
for user_input, expected in cases:
    mapped = _map_image_references(user_input)
    assert mapped == expected, f"映射不符: '{user_input}' -> '{mapped}' (期望: '{expected}')"
print("  [PASS] 5组中文口语表达全部 100% 精准对齐为 Image 1 / Image 2 / Image 3")

# ----------------------------------------------------
# 用例 2：GenerationRequest 多图列表与单图双向自同步
# ----------------------------------------------------
print("\n[Test 2] GenerationRequest 数据类多图双向同步契约测试")
fake_b64_1 = "AAA111"
fake_b64_2 = "BBB222"
req_multi = GenerationRequest(
    description="测试多图",
    input_images_base64=[fake_b64_1, fake_b64_2],
)
assert req_multi.input_image_base64 == fake_b64_1, "多图列表中首图未自动同步给 input_image_base64"
assert req_multi.is_img2img is True, "多图请求未能自动标记为 is_img2img"

req_single = GenerationRequest(
    description="测试单图",
    input_image_base64=fake_b64_1,
)
assert req_single.input_images_base64 == [fake_b64_1], "单图输入未能自动包装进 input_images_base64"
assert req_single.is_img2img is True, "单图请求未能自动标记为 is_img2img"
print("  [PASS] 多图与单图字段双向自动同步，历史兼容性 100% 成立")

# ----------------------------------------------------
# 用例 3：OpenAiClient 多图 Payload 与端点路由测试
# ----------------------------------------------------
print("\n[Test 3] OpenAiClient 官方多图编辑规范 Payload 构造测试")
class MockClientContext:
    log_prefix = "[MockClient]"
    def get_config(self, key, default=None):
        return default

client = OpenAIClient(MockClientContext())
model_cfg = {
    "model": "gpt-image-2",
    "base_url": "https://api.openai.com/v1",
}

# 模拟多图调用
captured_payload = None
captured_endpoint = None

import json, urllib.request

class DummyResponse:
    status = 200
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
    def read(self):
        return b'{"data": [{"b64_json": "SUCCESS_RESULT"}]}'

class DummyOpener:
    def open(self, req, timeout=None):
        global captured_endpoint, captured_payload
        captured_endpoint = req.full_url
        if req.data:
            try:
                captured_payload = json.loads(req.data.decode("utf-8"))
            except Exception:
                captured_payload = req.data
        return DummyResponse()

urllib.request.build_opener = lambda *args, **kwargs: DummyOpener()

success, res = client._make_request(
    prompt="把 Image 1 的人换成 Image 2 的衣服",
    model_config=model_cfg,
    size="1024x1024",
    input_images_base64=[fake_b64_1, fake_b64_2],
)

assert success is True, "多图生图执行未成功"
assert captured_endpoint == "https://api.openai.com/v1/images/edits", f"端点路由错误: {captured_endpoint}"
assert "images" in captured_payload, "Payload 中缺少官方多图字段 images"
assert len(captured_payload["images"]) == 2, f"Payload images 数量不符: {len(captured_payload['images'])}"
assert "image_url" in captured_payload["images"][0], "images 列表内元素缺少 image_url 结构"
print("  [PASS] 成功命中 /images/edits 并组装符合 OpenAI 规范的 images 数组")

# ----------------------------------------------------
# 用例 4：OpenAiClient 单图向后兼容性测试
# ----------------------------------------------------
print("\n[Test 4] OpenAiClient 单图编辑向后兼容性测试")
success_single, res_single = client._make_request(
    prompt="画得写实一点",
    model_config=model_cfg,
    size="1024x1024",
    input_image_base64=fake_b64_1,
)
assert success_single is True, "单图生图执行未成功"
assert captured_endpoint == "https://api.openai.com/v1/images/edits", f"单图端点路由错误: {captured_endpoint}"
assert "image" in captured_payload, "单图 Payload 中缺少 image 字段"
assert "images" not in captured_payload, "单图模式不应注入 images 数组"
print("  [PASS] 单图模式保持原汁原味单一 image 字段，向下兼容 100% 成立")

print("\n==================================================")
print("[DONE] 阶段二多图命令映射与 API 客户端全部用例 100% 满分通过！")
print("==================================================")