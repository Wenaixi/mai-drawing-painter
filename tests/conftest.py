"""测试公共 fixture。

本机没有 maibot_sdk（只在 Docker core 容器里有），对需要它的 import 做最小 stub，
让 cache_manager / recall_utils / auto_selfie_task / factories 可在本机 pytest。
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

# 插件根进 path
PLUGIN_DIR = Path(__file__).resolve().parent.parent
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))


def _ensure_maibot_sdk_stub() -> None:
    if "maibot_sdk" in sys.modules:
        return

    try:
        import maibot_sdk  # noqa: F401
        return
    except ImportError:
        pass

    # 最小 stub：models.py 用 Field / PluginConfigBase；其余 TYPE_CHECKING 用不到运行时
    try:
        from pydantic import BaseModel, Field as PydanticField
    except ImportError:
        return  # 连 pydantic 都没有就放弃 stub

    sdk = types.ModuleType("maibot_sdk")
    sdk.Field = PydanticField  # type: ignore[attr-defined]

    class PluginConfigBase(BaseModel):
        model_config = {"extra": "ignore"}

    sdk.PluginConfigBase = PluginConfigBase  # type: ignore[attr-defined]
    sdk.MaiBotPlugin = object  # type: ignore[attr-defined]

    def Tool(*args, **metadata):
        def decorator(func):
            func.__maibot_component__ = types.SimpleNamespace(metadata=metadata)
            return func
        return decorator

    sdk.Tool = Tool  # type: ignore[attr-defined]
    sdk.API = Tool  # type: ignore[attr-defined]
    sdk.Command = Tool  # type: ignore[attr-defined]

    ctx_mod = types.ModuleType("maibot_sdk.context")
    ctx_mod.PluginContext = object  # type: ignore[attr-defined]

    sys.modules["maibot_sdk"] = sdk
    sys.modules["maibot_sdk.context"] = ctx_mod


def _ensure_maim_message_stub() -> None:
    if "maim_message" in sys.modules:
        return
    try:
        import maim_message  # noqa: F401
        return
    except ImportError:
        pass
    mm = types.ModuleType("maim_message")
    mm.Seg = object  # type: ignore[attr-defined]
    sys.modules["maim_message"] = mm


_ensure_maibot_sdk_stub()
_ensure_maim_message_stub()
