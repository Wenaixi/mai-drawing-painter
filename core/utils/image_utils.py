# -*- coding: utf-8 -*-
"""图片处理工具模块。

提供对 NapCat / OneBot 11 各种消息段（image, emoji, mface, reply）的
万能穿透提取、多图按序收集、外链异步补拉与前置等比防爆降采样能力。
"""

from __future__ import annotations

import base64
import hashlib
import io
import logging
import os
import traceback
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

import httpx
from PIL import Image

try:
    from maim_message import Seg
except ImportError:
    Seg = None

logger = logging.getLogger("plugin.mais_art_journal.image")

# 标准浏览器请求头，避免图床 403 拦截
_BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
}


class ImageProcessor:
    """万能图片处理工具类。"""

    def __init__(self, action_instance: Any) -> None:
        self.action = action_instance
        self.log_prefix = getattr(action_instance, "log_prefix", "[MaisArt]")
        self._ctx = getattr(action_instance, "ctx", None)
        self._chat_id = getattr(action_instance, "chat_id", "") or getattr(action_instance, "stream_id", "")

    # ==================== 主入口方法 ====================

    async def get_recent_image(self) -> Optional[str]:
        """向下兼容单图入口：提取第一张参考图，找不到返回 None。"""
        images = await self.get_all_recent_images()
        return images[0] if images else None

    async def get_all_recent_images(self) -> List[str]:
        """万能多图提取入口：

        1. 穿透单层被引用回复消息中的图片/表情包 (Q2->A)；
        2. 提取当前消息自带的全部图片/表情包；
        3. 智能序列合并：引用图为图1，当前图为图2、图3 (Q4->A)；
        4. 硬性截断最多保留前 3 张，并进行前置等比防爆降采样 (Q3->A)。
        """
        try:
            message = getattr(self.action, "message", None)
            if message is None:
                return []
            return await self.extract_all_images(message, chat_id=self._chat_id, ctx=self._ctx)
        except Exception as exc:
            logger.error(f"{self.log_prefix} 获取图片列表失败: {exc!r}", exc_info=True)
            return []

    async def extract_all_images(
        self,
        message: Any,
        chat_id: str = "",
        ctx: Any = None,
    ) -> List[str]:
        """全链路静态/实例方法：从任意 message 结构提取有序图片列表。"""
        if not message:
            return []

        target_images: List[str] = []
        current_images: List[str] = []

        # 1. 单层被引用消息穿透检测 (Q2->A)
        target_msg_id = self._extract_reply_target_id(message)
        if target_msg_id and ctx and hasattr(ctx, "message") and hasattr(ctx.message, "get_by_id"):
            try:
                logger.info(f"{self.log_prefix} 检测到引用消息 target_id={target_msg_id}，拉取被引用消息...")
                import asyncio
                target_msg = await asyncio.wait_for(
                    ctx.message.get_by_id(
                        message_id=target_msg_id,
                        chat_id=chat_id or "",
                        include_binary_data=True,
                    ),
                    timeout=5.0,
                )
                if isinstance(target_msg, dict):
                    target_images = await self._collect_images_from_msg(target_msg, ctx=ctx)
                    logger.info(f"{self.log_prefix} 从被引用消息中成功解析 {len(target_images)} 张图片")
            except Exception as exc:
                logger.debug(f"{self.log_prefix} 回拉被引用消息取图跳过: {exc}")

        # 2. 提取当前消息自身包含的所有图片/表情
        current_images = await self._collect_images_from_msg(message, ctx=ctx)

        # 3. 智能序列合并 (Q4->A)：引用图排在前面(图1)，当前消息图排在后面(图2, 图3)
        combined = target_images + current_images
        if not combined:
            return []

        # 4. 去重并保留出现顺序
        seen_hashes = set()
        deduped: List[str] = []
        for b64 in combined:
            if not b64 or not isinstance(b64, str):
                continue
            h = hashlib.md5(b64.encode("utf-8")).hexdigest()
            if h not in seen_hashes:
                seen_hashes.add(h)
                deduped.append(b64)

        # 5. 上限硬性截断最多保留前 3 张
        capped = deduped[:3]

        # 6. 前置等比防爆降采样 (Q3->A)
        processed: List[str] = []
        for idx, b64 in enumerate(capped):
            downsampled = self._downsample_image_if_needed(b64)
            processed.append(downsampled)
            logger.info(f"{self.log_prefix} 图{idx+1} 提取就绪 (有效 Base64 长度: {len(downsampled)})")

        return processed

    # ==================== 递归消息段扫描 ====================

    async def _collect_images_from_msg(self, message: Any, ctx: Any = None) -> List[str]:
        """从单条消息字典或组件对象中，全量收集图片/表情的 Base64 列表。"""
        collected: List[str] = []

        # 处理字典形态 (SDK 2.x raw_message / components)
        if isinstance(message, dict):
            raw = message.get("raw_message") or message.get("message") or message.get("components")
            if isinstance(raw, list):
                for seg in raw:
                    if not isinstance(seg, dict):
                        continue
                    b64 = await self._resolve_segment_to_b64(seg, ctx=ctx)
                    if b64:
                        collected.append(b64)
            elif isinstance(raw, dict):
                b64 = await self._resolve_segment_to_b64(raw, ctx=ctx)
                if b64:
                    collected.append(b64)

        # 处理组件对象形态 (SessionMessage.raw_message.components)
        elif hasattr(message, "raw_message"):
            components = getattr(message.raw_message, "components", None)
            if isinstance(components, (list, tuple)):
                for comp in components:
                    cls_name = type(comp).__name__
                    if cls_name in ("ImageComponent", "EmojiComponent"):
                        binary = getattr(comp, "binary_data", None)
                        if isinstance(binary, (bytes, bytearray)) and binary:
                            collected.append(base64.b64encode(bytes(binary)).decode("utf-8"))
                        content = getattr(comp, "content", None)
                        if isinstance(content, str) and content.startswith("data:image/"):
                            collected.append(content.split(";base64,", 1)[-1])

        # 处理老 Seg 树形态
        if Seg is not None and hasattr(message, "message_segment"):
            seg = getattr(message, "message_segment", None)
            if seg is not None:
                collected.extend(self.find_and_return_emoji_in_message(seg))

        return collected

    def _extract_bface_info(self, seg: dict) -> Tuple[str, str]:
        """从 bface 原创大表情段中提取 package_id 与 id 特征。"""
        data = seg.get("data") if isinstance(seg.get("data"), dict) else {}
        pkg_id = str(data.get("package_id") or seg.get("package_id") or "")
        face_id = str(data.get("id") or data.get("p_id") or seg.get("id") or "")
        return pkg_id, face_id

    async def _resolve_segment_to_b64(self, seg: dict, ctx: Any = None) -> Optional[str]:
        """将单个消息段解析为纯 Base64 字符串（全面兼容 image, emoji, mface, bface, dict）。"""
        stype = str(seg.get("type") or "").lower()
        data = seg.get("data") if isinstance(seg.get("data"), dict) else {}

        # 宿主 DictComponent 包装层穿透
        if stype == "dict":
            inner_type = str(data.get("type") or "").lower()
            if inner_type in ("image", "emoji", "mface", "bface", "face"):
                stype = inner_type
                data = data.get("data") if isinstance(data.get("data"), dict) else data

        # 仅处理视觉图像类段落
        if stype not in ("image", "emoji", "mface", "bface"):
            return None

        # 1. 优先读取已存在的二进制 Base64
        b64 = seg.get("binary_data_base64") or data.get("binary_data_base64")
        if isinstance(b64, str) and b64:
            return b64

        # 2. 检查外链 URL（NapCat 商城表情、外链图片）异步安全补拉
        url = seg.get("url") or data.get("url")
        if isinstance(url, str) and url.startswith(("http://", "https://")):
            downloaded = await self._async_download_to_b64(url)
            if downloaded:
                return downloaded

        # 3. 检查 file 字段
        file_val = seg.get("file") or data.get("file")
        if isinstance(file_val, str) and file_val:
            if file_val.startswith(("http://", "https://")):
                downloaded = await self._async_download_to_b64(file_val)
                if downloaded:
                    return downloaded
            if file_val.startswith("base64://"):
                return file_val.removeprefix("base64://")
            if os.path.exists(file_val):
                try:
                    with open(file_val, "rb") as fp:
                        return base64.b64encode(fp.read()).decode("utf-8")
                except Exception:
                    pass

        # 4. 如果是 bface 原创大表情，尝试提取 package_id 与 id，并通过腾讯 CDN 动态直链补拉
        if stype == "bface":
            pkg_id, face_id = self._extract_bface_info(seg)
            if pkg_id and face_id:
                cdn_url = f"https://gxh.vip.qq.com/club/item/parcel/item/{pkg_id[:2]}/{pkg_id}/126x126/{face_id}.png"
                downloaded = await self._async_download_to_b64(cdn_url)
                if downloaded:
                    logger.info(f"{self.log_prefix} bface 原创大表情 CDN 自动补拉成功 (pkg={pkg_id}, id={face_id})")
                    return downloaded
                logger.info(f"{self.log_prefix} 识别到原创大表情 bface (pkg={pkg_id}, id={face_id})，未附带直接下载直链")

        return None

    def _extract_reply_target_id(self, message: Any) -> Optional[str]:
        """提取当前消息中的被引用消息 ID（单层引用）。"""
        if not isinstance(message, dict):
            return None

        # 顶层快捷字段
        reply_to = message.get("reply_to")
        if isinstance(reply_to, (str, int)) and str(reply_to).strip():
            return str(reply_to).strip()

        # 扫描 raw_message 中的 reply 段
        raw = message.get("raw_message") or message.get("message") or []
        if isinstance(raw, list):
            for seg in raw:
                if not isinstance(seg, dict):
                    continue
                if str(seg.get("type") or "").lower() == "reply":
                    data = seg.get("data") if isinstance(seg.get("data"), dict) else {}
                    tid = data.get("target_message_id") or data.get("id") or seg.get("id")
                    if tid and str(tid).strip():
                        return str(tid).strip()
        return None

    async def _async_download_to_b64(self, url: str) -> Optional[str]:
        """异步下载图片外链并转换为 Base64（带标准浏览器头与 8s 超时）。"""
        try:
            async with httpx.AsyncClient(trust_env=False, timeout=8.0) as client:
                resp = await client.get(url, headers=_BROWSER_HEADERS)
                if resp.status_code == 200 and resp.content:
                    return base64.b64encode(resp.content).decode("utf-8")
        except Exception as exc:
            logger.debug(f"{self.log_prefix} 外链图片下载略过: {exc}")
        return None

    # ==================== 前置防爆等比降采样 (Q3->A) ====================

    def _downsample_image_if_needed(self, b64_str: str) -> str:
        """长边 > 1200px 或体积 > 1.5MB 时，按等比缩放至最大边 1200px 质量 85 压缩。"""
        if not b64_str:
            return b64_str

        try:
            raw_bytes = base64.b64decode(b64_str)
            # 惰性读取头部元数据（微秒级开销），精确判断真实分辨率
            im = Image.open(io.BytesIO(raw_bytes))
            w, h = im.size
            needs_resize = max(w, h) > 1200
            needs_compress = len(raw_bytes) > 1.5 * 1024 * 1024

            if not needs_resize and not needs_compress:
                return b64_str

            if needs_resize:
                scale = 1200.0 / max(w, h)
                new_w, new_h = max(1, int(w * scale)), max(1, int(h * scale))
                im = im.resize((new_w, new_h), Image.Resampling.LANCZOS)
                logger.info(f"{self.log_prefix} 图片尺寸防爆降采样: ({w}x{h}) -> ({new_w}x{new_h})")

            buf = io.BytesIO()
            if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in getattr(im, "info", {})):
                # 合成白底后转 RGB JPEG，消除无损 PNG 体积膨胀，将单张体积严格压制在 300KB 内
                bg = Image.new("RGB", im.size, (255, 255, 255))
                alpha_mask = im.convert("RGBA").split()[-1]
                bg.paste(im, mask=alpha_mask)
                bg.save(buf, format="JPEG", quality=85, optimize=True)
            else:
                if im.mode != "RGB":
                    im = im.convert("RGB")
                im.save(buf, format="JPEG", quality=85, optimize=True)

            compressed_bytes = buf.getvalue()
            logger.info(f"{self.log_prefix} 图片体积优化: {len(raw_bytes)} bytes -> {len(compressed_bytes)} bytes")
            return base64.b64encode(compressed_bytes).decode("utf-8")
        except Exception as exc:
            logger.debug(f"{self.log_prefix} 等比降采样略过: {exc}")
            return b64_str

    # ==================== 兼容旧 API ====================

    def find_and_return_emoji_in_message(self, message_segments) -> List[str]:
        """老 Seg 树兼容。"""
        emoji_base64_list: List[str] = []
        if Seg is not None and isinstance(message_segments, Seg):
            if message_segments.type in ("emoji", "image") and isinstance(message_segments.data, str):
                emoji_base64_list.append(message_segments.data)
            elif message_segments.type == "seglist":
                emoji_base64_list.extend(self.find_and_return_emoji_in_message(message_segments.data))
            return emoji_base64_list

        if isinstance(message_segments, (list, tuple)):
            for seg in message_segments:
                if Seg is not None and isinstance(seg, Seg):
                    if seg.type in ("emoji", "image") and isinstance(seg.data, str):
                        emoji_base64_list.append(seg.data)
                    elif seg.type == "seglist":
                        emoji_base64_list.extend(self.find_and_return_emoji_in_message(seg.data))
        return emoji_base64_list

    def download_and_encode_base64(self, image_url: str, proxy_url: str = None) -> Tuple[bool, str]:
        """下载图片或处理 Base64 数据 URL（保持公共方法兼容）。"""
        try:
            if image_url.startswith("data:image/"):
                if ";base64," in image_url:
                    return True, image_url.split(";base64,", 1)[1]
                return False, "Base64 数据 URL 格式不正确"
            if proxy_url:
                import requests
                resp = requests.get(image_url, timeout=180, proxies={"http": proxy_url, "https": proxy_url}, headers=_BROWSER_HEADERS)
                if resp.status_code == 200:
                    return True, base64.b64encode(resp.content).decode("utf-8")
                return False, f"下载失败: {resp.status_code}"
            req = urllib.request.Request(image_url, headers=_BROWSER_HEADERS)
            with urllib.request.urlopen(req, timeout=180) as response:
                if response.status == 200:
                    return True, base64.b64encode(response.read()).decode("utf-8")
                return False, f"下载失败: {response.status}"
        except Exception as e:
            return False, str(e)[:50]

    def process_api_response(self, result: Any) -> Optional[str]:
        """统一处理 API 响应，提取图片数据。"""
        try:
            if isinstance(result, str):
                return result
            if isinstance(result, dict):
                for key in ["url", "image", "b64_json", "data"]:
                    if key in result and result[key]:
                        return result[key]
                if "output" in result and isinstance(result["output"], dict):
                    out = result["output"]
                    for key in ["image_url", "images"]:
                        if key in out:
                            data = out[key]
                            return data[0] if isinstance(data, list) and data else data
            return None
        except Exception:
            return None
