"""Review fixes 回归测试（TDD RED→GREEN）

HIGH 6 项：
1. cache_manager cache 默认值与 schema 统一为 3
2. recall_utils schedule_auto_recall 的 create_task 必须有强引用
3. auto_selfie_task httpx.AsyncClient 复用
4. cache_manager cache key 截断冲突 → md5
5. auto_selfie_task 参考图 mtime 缓存
6. factories 参考图 mtime 缓存

MEDIUM：
- AsyncClient trust_env=False
"""
from __future__ import annotations

import asyncio
import base64
import os
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

PLUGIN_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(PLUGIN_DIR))


# ==================== HIGH 1: cache 默认值一致性 ====================

class _MockAction:
    """get_config 透传 default（模拟配置缺失）"""

    def __init__(self):
        self.log_prefix = "[test]"

    def get_config(self, key, default=None):
        return default


def test_cache_max_size_default_matches_schema():
    """HIGH 1: _get_max_size 与 BasicSection.cache_max_size 默认统一为 3"""
    from core.config.models import BasicSection
    from core.utils.cache_manager import CacheManager

    assert BasicSection().cache_max_size == 3, (
        f"schema 默认应为 3，实际 {BasicSection().cache_max_size}"
    )
    cm = CacheManager(_MockAction())
    assert cm._get_max_size() == 3, (
        f"_get_max_size() 应为 3，实际 {cm._get_max_size()}"
    )


def test_draw_picture_declares_long_rpc_timeout():
    """生图通常超过宿主默认 60 秒，Tool 必须声明 10 分钟 RPC 超时。"""
    import importlib

    package_parent = str(PLUGIN_DIR.parent)
    if package_parent not in sys.path:
        sys.path.insert(0, package_parent)
    module = importlib.import_module(f"{PLUGIN_DIR.name}.plugin")
    info = getattr(module.MaisArtPlugin.handle_draw_picture, "__maibot_component__")
    assert info.metadata["timeout_ms"] == 120_000


# ==================== HIGH 4: cache key 不再截断冲突 ====================

def test_cache_key_no_truncation_collision():
    """HIGH 4: 前缀相同、后缀不同的 description 必须产生不同 key"""
    from core.utils.cache_manager import CacheManager

    # 旧实现 description[:100] 会把这两条压成同一个 key
    desc1 = "a" * 100 + "1"
    desc2 = "a" * 100 + "2"
    k1 = CacheManager._get_cache_key(desc1, "model1", "1024x1024")
    k2 = CacheManager._get_cache_key(desc2, "model1", "1024x1024")
    assert k1 != k2, f"截断碰撞：{k1!r} == {k2!r}"


def test_cache_key_deterministic_and_bounded():
    """HIGH 4: 同 description 同 key；超长 description 被哈希压缩"""
    from core.utils.cache_manager import CacheManager

    long_desc = "x" * 5000
    k1 = CacheManager._get_cache_key(long_desc, "m", "1024x1024")
    k2 = CacheManager._get_cache_key(long_desc, "m", "1024x1024")
    assert k1 == k2
    assert len(k1) < 200, f"超长 desc 应被哈希，实际长度 {len(k1)}"


# ==================== HIGH 2: create_task 强引用 ====================

def test_pending_recalls_weakset_exists():
    """HIGH 2: 模块级 _pending_recalls 必须是 weakref.WeakSet"""
    import weakref
    from core.utils import recall_utils

    assert hasattr(recall_utils, "_pending_recalls")
    assert isinstance(recall_utils._pending_recalls, weakref.WeakSet)


@pytest.mark.asyncio
async def test_schedule_auto_recall_tracks_task_in_weakset():
    """HIGH 2: schedule_auto_recall 后 task 必须进 _pending_recalls"""
    from core.utils import recall_utils

    initial = len(recall_utils._pending_recalls)

    # ctx=None 时 inner task 会在 sleep 后炸，但 create_task 已完成
    await recall_utils.schedule_auto_recall(
        ctx=None,
        chat_id="chat_test",
        delay_seconds=0,
        log_prefix="[test]",
        send_timestamp=0.0,
    )

    assert len(recall_utils._pending_recalls) > initial, (
        "_pending_recalls 没有记录新 task（强引用丢失）"
    )

    # 等 inner task 跑完（sleep 1.0 + 异常被吞）
    await asyncio.sleep(1.5)
    assert len(recall_utils._pending_recalls) == initial, (
        "task 结束后未从 _pending_recalls 移除"
    )


# ==================== HIGH 3: AsyncClient 复用 ====================

class _MockSelfieCfg:
    quiet_hours_start = ""
    quiet_hours_end = ""
    interval_minutes = 120
    default_style = "standard"
    prompt_prefix = ""
    negative_prompt = ""
    reference_image_path = ""
    caption_enabled = False
    selfie_model = "model1"


class _MockBasicCfg:
    llm_task_name = "utils"


class _MockCfg:
    selfie = _MockSelfieCfg()
    basic = _MockBasicCfg()


class _MockPlugin:
    config = _MockCfg()
    ctx = None
    plugin_dir = "."


@pytest.mark.asyncio
async def test_auto_selfie_async_client_reused(monkeypatch):
    """HIGH 3: 多次 _normalize_to_base64 只构造一次 httpx.AsyncClient"""
    import httpx
    from core.selfie import auto_selfie_task as mod

    init_count = {"n": 0}
    real_init = httpx.AsyncClient.__init__
    captured_kwargs = {}

    def counting_init(self, *a, **kw):
        init_count["n"] += 1
        captured_kwargs.update(kw)
        real_init(self, *a, **kw)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", counting_init)

    class _MockResp:
        content = b"\x89PNG\r\n\x1a\n"

        def raise_for_status(self):
            pass

    async def fake_get(self, url, **kw):
        return _MockResp()

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    async def noop_loop(self):
        await asyncio.sleep(0)

    monkeypatch.setattr(mod.AutoSelfieTask, "_selfie_loop", noop_loop)

    task = mod.AutoSelfieTask(_MockPlugin())
    await task.start()
    assert init_count["n"] == 1, f"start() 应建 1 个 client，实际 {init_count['n']}"
    # MEDIUM: trust_env=False
    assert captured_kwargs.get("trust_env") is False, (
        f"AsyncClient 应 trust_env=False，实际 kwargs={captured_kwargs}"
    )

    r1 = await task._normalize_to_base64("http://example.com/a.png")
    r2 = await task._normalize_to_base64("http://example.com/b.png")
    assert r1 is not None and r2 is not None
    assert init_count["n"] == 1, (
        f"两次 _normalize 不应再 new client，实际新建了 {init_count['n'] - 1} 次"
    )

    await task.stop()


# ==================== HIGH 5: auto_selfie 参考图缓存 ====================

def test_auto_selfie_reference_image_cached(tmp_path, monkeypatch):
    """HIGH 5: 同 mtime 下多次 _load_reference_image 只读一次文件"""
    from core.selfie import auto_selfie_task as mod

    img = tmp_path / "ref.jpg"
    img.write_bytes(b"first-payload")

    class _SelfieCfg:
        reference_image_path = str(img)
        quiet_hours_start = ""
        quiet_hours_end = ""
        interval_minutes = 120
        default_style = "standard"
        prompt_prefix = ""
        negative_prompt = ""

    class _Cfg:
        selfie = _SelfieCfg()
        basic = _MockBasicCfg()

    class _Plugin:
        config = _Cfg()
        plugin_dir = str(tmp_path)

    task = mod.AutoSelfieTask(_Plugin())

    read_count = {"n": 0}
    builtin_open = open

    def counting_open(path, *a, **kw):
        if str(path) == str(img):
            read_count["n"] += 1
        return builtin_open(path, *a, **kw)

    monkeypatch.setattr("builtins.open", counting_open)

    r1 = task._load_reference_image()
    r2 = task._load_reference_image()
    r3 = task._load_reference_image()

    assert r1 == r2 == r3
    assert r1 is not None
    assert read_count["n"] == 1, f"应只读 1 次，实际 {read_count['n']} 次"


def test_auto_selfie_reference_image_reload_on_mtime_change(tmp_path):
    """HIGH 5: mtime 变化时重读"""
    from core.selfie import auto_selfie_task as mod

    img = tmp_path / "ref.jpg"
    img.write_bytes(b"first")

    class _SelfieCfg:
        reference_image_path = str(img)
        quiet_hours_start = ""
        quiet_hours_end = ""
        interval_minutes = 120
        default_style = "standard"
        prompt_prefix = ""
        negative_prompt = ""

    class _Cfg:
        selfie = _SelfieCfg()
        basic = _MockBasicCfg()

    class _Plugin:
        config = _Cfg()
        plugin_dir = str(tmp_path)

    task = mod.AutoSelfieTask(_Plugin())
    r1 = task._load_reference_image()

    time.sleep(0.05)
    img.write_bytes(b"second-different")
    new_mtime = time.time() + 2
    os.utime(str(img), (new_mtime, new_mtime))

    r2 = task._load_reference_image()
    assert r1 != r2, "mtime 变化必须重读"


# ==================== HIGH 6: factories 参考图缓存 ====================

def test_factories_reference_image_cached(tmp_path, monkeypatch):
    """HIGH 6: _load_selfie_reference_image 同 mtime 只读一次"""
    from core.pipeline import factories

    img = tmp_path / "ref.jpg"
    img.write_bytes(b"first-payload")

    class _SelfieCfg:
        reference_image_path = str(img)

    class _Cfg:
        selfie = _SelfieCfg()

    class _Plugin:
        config = _Cfg()
        plugin_dir = str(tmp_path)

    read_count = {"n": 0}
    builtin_open = open

    def counting_open(path, *a, **kw):
        if str(path) == str(img):
            read_count["n"] += 1
        return builtin_open(path, *a, **kw)

    monkeypatch.setattr("builtins.open", counting_open)

    p = _Plugin()
    r1 = factories._load_selfie_reference_image(p, "[t]")
    r2 = factories._load_selfie_reference_image(p, "[t]")
    r3 = factories._load_selfie_reference_image(p, "[t]")

    assert r1 == r2 == r3
    assert r1 is not None
    assert read_count["n"] == 1, f"应只读 1 次，实际 {read_count['n']} 次"


def test_factories_reference_image_reload_on_mtime_change(tmp_path):
    """HIGH 6: mtime 变化时 factories 重读"""
    from core.pipeline import factories

    img = tmp_path / "ref.jpg"
    img.write_bytes(b"first")

    class _SelfieCfg:
        reference_image_path = str(img)

    class _Cfg:
        selfie = _SelfieCfg()

    class _Plugin:
        config = _Cfg()
        plugin_dir = str(tmp_path)

    p = _Plugin()
    r1 = factories._load_selfie_reference_image(p, "[t]")

    time.sleep(0.05)
    img.write_bytes(b"second-different")
    new_mtime = time.time() + 2
    os.utime(str(img), (new_mtime, new_mtime))

    r2 = factories._load_selfie_reference_image(p, "[t]")
    assert r1 != r2, "mtime 变化必须重读"
