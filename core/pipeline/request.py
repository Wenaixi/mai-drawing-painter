"""贯穿图片生成流水线的请求对象。

每次生图调用（Tool / Command 风格 / Command 自然语言 / 自动自拍 / 独立接口）
都会构造一个 GenerationRequest，沿着 Pipeline 的 14 个 Step 流转，
中间状态共享在同一对象上，行为开关控制每个 Step 是否短路。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional


SourceLiteral = Literal[
    "tool",          # @Tool draw_picture 智能生图
    "cmd_style",     # /dv <风格名>
    "cmd_natural",   # /dv <自然语言描述>
    "auto_selfie",   # 自动自拍后台任务
    "standalone",    # generate_image_standalone 外部调用
]

SelfieStyleLiteral = Literal["standard", "mirror", "photo"]


@dataclass
class GenerationRequest:
    """图片生成请求（贯穿流水线）"""

    # ==================== 输入参数 ====================
    description: str = ""
    model_id: str = ""
    size: str = ""
    strength: Optional[float] = None
    input_images_base64: List[str] = field(default_factory=list)
    extra_negative_prompt: Optional[str] = None

    # 视角与视觉意象 (1A + 3A)
    viewpoint: Literal["selfie", "pov"] = "selfie"
    visual_scene: str = ""

    # 自拍相关
    is_selfie: bool = False
    selfie_style: SelfieStyleLiteral = "standard"
    free_hand_action: str = ""
    activity_scene: Optional[Dict[str, Any]] = None

    # ==================== 行为开关（各 Step 自查短路） ====================
    send_image: bool = True
    update_cache: bool = True
    schedule_recall: bool = True
    debug_info: bool = True
    silent_img2img_fallback: bool = False
    """图生图回退时是否静默：True=不发"将为您生成新图片"消息（自拍参考图回退用）"""

    # ==================== 上下文 ====================
    stream_id: str = ""
    chat_id: str = ""
    log_prefix: str = "[MaisArt]"
    command_message: Any = None
    source: SourceLiteral = "tool"

    # ==================== 中间状态（Step 间共享） ====================
    resolved_model_config: Optional[Dict[str, Any]] = None
    api_format: str = ""
    selfie_negative_prompt: Optional[str] = None
    llm_chosen_size: Optional[str] = None
    final_size: str = ""
    raw_api_result: Any = None
    parsed_image_data: Optional[str] = None
    resolved_image_data: Optional[str] = None
    send_timestamp: float = 0.0
    cache_hit: bool = False

    # ==================== 输出 ====================
    success: bool = False
    error: Optional[str] = None
    user_message: Optional[str] = None
    """成功/失败时同步发送给用户的消息文案（已发送或将由 pipeline 发送）"""

    # ==================== 调试 / 额外字段 ====================
    extras: Dict[str, Any] = field(default_factory=dict)

    @property
    def input_image_base64(self) -> Optional[str]:
        """向下兼容单图属性：返回多图列表中第一张图。"""
        return self.input_images_base64[0] if self.input_images_base64 else None

    @input_image_base64.setter
    def input_image_base64(self, val: Optional[str]) -> None:
        """向下兼容单图设值：同步更新多图列表。"""
        if val:
            self.input_images_base64 = [val]
        else:
            self.input_images_base64 = []

    @property
    def is_img2img(self) -> bool:
        """是否图生图请求：多图列表非空即是。"""
        return bool(self.input_images_base64)

    @is_img2img.setter
    def is_img2img(self, val: bool) -> None:
        """允许外部设置或兼容历史调用。"""
        pass


# 模块级兼容补丁：允许历史调用方以 input_image_base64 关键字参数构造
_orig_req_init = GenerationRequest.__init__


def _compat_req_init(self, *args, **kwargs):
    legacy_single = kwargs.pop("input_image_base64", None)
    if "input_images_base64" not in kwargs:
        if legacy_single:
            kwargs["input_images_base64"] = [legacy_single]
        else:
            kwargs["input_images_base64"] = []
    elif legacy_single and not kwargs["input_images_base64"]:
        kwargs["input_images_base64"] = [legacy_single]
    _orig_req_init(self, *args, **kwargs)


GenerationRequest.__init__ = _compat_req_init
