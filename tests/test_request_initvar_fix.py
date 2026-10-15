# -*- coding: utf-8 -*-
"""针对第二轮审查确凿缺陷：GenerationRequest 消除猴子补丁胶水层的测试套件。"""
import os
import sys
import pytest

art_dir = os.path.abspath("Maibot-new/plugins/1021143806_mais_art_journal")
sys.path.insert(0, art_dir)

from tests import conftest
conftest._ensure_maibot_sdk_stub()

import core.pipeline.request as req_module
from core.pipeline.request import GenerationRequest

def test_no_monkey_patch_in_init():
    """验证 GenerationRequest.__init__ 为纯正 dataclass 生成方法，彻底不存在 _compat_req_init 猴子补丁。"""
    init_name = getattr(GenerationRequest.__init__, "__name__", "")
    assert init_name != "_compat_req_init", "GenerationRequest.__init__ 依然被 _compat_req_init 猴子补丁劫持！"
    assert not hasattr(req_module, "_compat_req_init"), "模块中仍残留 _compat_req_init 胶水函数！"
