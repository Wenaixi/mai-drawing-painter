# -*- coding: utf-8 -*-
"""针对代码审查真实缺陷 S3（Data Clumps 属性重构）、S5（无用参数清理）与 R6（bface 协议容错）的测试套件。"""
import os
import sys
import pytest

art_dir = os.path.abspath("Maibot-new/plugins/1021143806_mais_art_journal")
sys.path.insert(0, art_dir)

from tests import conftest
conftest._ensure_maibot_sdk_stub()

from core.pipeline.request import GenerationRequest
from core.api_clients.base_client import BaseApiClient
from core.api_clients.openai_client import OpenAIClient
from core.utils.image_utils import ImageProcessor

def test_request_property_eliminates_data_clumps():
    """验证 GenerationRequest 以 input_images_base64 为单一本源，且 input_image_base64 作为 property 兼容。"""
    # 纯属性测试：检查 input_image_base64 是否已重构为 property 而非普通字段
    assert isinstance(getattr(GenerationRequest, "input_image_base64", None), property), "input_image_base64 应重构为 property 访问器以消除数据泥团"

def test_bface_package_id_fallback():
    """验证遇到缺少 url/file 但带有 package_id 的 bface 段时，具备明确的字段探测与安全容错。"""
    processor = ImageProcessor(action_instance=None)
    bface_seg = {
        "type": "bface",
        "data": {
            "package_id": "12345",
            "id": "abcde",
        }
    }
    # 模拟解析：即便无下载直链，也能提取特征或安全降级，不发生崩溃或不可预期行为
    res = processor._extract_bface_info(bface_seg)
    assert res == ("12345", "abcde"), f"bface 特征提取不符: {res}"
