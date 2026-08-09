# 麦麦绘卷（1021143806_mais_art_journal）

源: GitHub 用户 `1021143806/mais_art_journal`  
插件 ID: `1021143806.mais_art_journal` 版本 v4.2.0  
路径: `/root/MaiBot/data/MaiMBot/plugins/1021143806_mais_art_journal/`

## 主人改过的关键文件

- `config.toml`：`[[models.items]]` 加 `model1` 指向 NewAPI `https://api.wenxi.dev/v1`，`format=openai`，`model=gpt-image-2`，`api_key=Bearer sk-...`（主人 newapi_channel_conn）。
- `images/reference.jpg`（同内容 `reference.jfif`，约 310KB，1843x2693 JPEG）—— 人设参考图。
- `[selfie]`：`enabled=true`、`reference_image_path = "images/reference.jpg"`、`prompt_prefix` 留空。

## 配置要点

- 默认 / 命令 / 自拍模型均指向 `model1`；`fixed_size_enabled=false`，`default_size="auto"` —— plugin 端短路 LLM Size Selector，把 `size=auto` 直发 NewAPI / gpt-image-2，让上游按 prompt 自由出图。`auto` 还走 `validate_image_size` 白名单（2026-08-09）。
- MaiTrace 跨插件 `generate_image` 超时 `timeout_ms=600000`（10 分钟，对齐 OpenAI 客户端 600s）。
- 自拍 / MaiTrace 配图在 `selfie_mode` 下读此图走图生图（仅在 `support_img2img=true` 的模型上生效）。
- Size Selector system prompt：`Output "auto" if unclear`（替代旧版的 `Default to 1024x1024 if unclear`），引导 LLM 偏好 auto 而非方图回退。

## 接入 & 依赖

- MaiTrace 通过 `services/persona.py` 的 `_resolve_art_plugin_dir` 查找本插件目录解析 reference image（已修过兼容 bug，原只认 `mais_art_journal`，会丢 MaiTrace 的参考图）。

## 关键日志

- `麦麦绘卷已加载 (v4.2.0)`。
- 对外 API：`1021143806.mais_art_journal.generate_image`。

## 用法

- 群/私聊 `/dr 一只猫`，或 `/dr list` 看模型。

## 注意

- 不要再给绘卷建同名软链，会触发"重复插件 ID"注册失败。

## 历史脚注

- 2026-07-28: 从服务器同步到本地仓库（baseline head=`23e67ae`）；补充 `.gitignore` 主人段与本 CLAUDE.md。
- 2026-08-01: TDD 修 6 项 HIGH 审查问题（commit `2686a54`）
  - `cache_manager._get_max_size` fallback 与 schema 统一 3；key 用 md5 防截断冲突
  - `recall_utils._pending_recalls` WeakSet 保活 create_task
  - `auto_selfie_task` AsyncClient 复用 + `trust_env=False`；参考图 mtime 缓存
  - `factories._load_selfie_reference_image` 模块级 mtime 缓存
  - 测试：`tests/test_review_fixes.py` 10 项；`tests/conftest.py` 本地 stub maibot_sdk
  - 不改 `config.toml`（toml 里 `cache_max_size=10` 仍生效；schema 默认 3 只影响缺配置时）

- 2026-08-09: 出图比例放权上游（"1:1 复盘"）

  - **根因**：主人发现所有图仍是 1:1。第一次只把 `fixed_size_enabled=true → false`，但 plugin 走 LLM Size Selector 兜底，prompt 模糊时 LLM 永远选 `1024x1024`（system prompt 写死 "Default to 1024x1024 if unclear"），`default_size` 实质不生效。日志实证：

    ```
    [plugin.mais_art_journal.size] [炼天 的 私聊] 使用 LLM 选择尺寸...
    [plugin.mais_art_journal.size] [炼天 的 私聊] LLM 选择尺寸: 1024x1024 (模型: maibot)
    ```

  - **新策略**：`default_size="auto"` + plugin 端短路 + system prompt 改默认 auto —— 由上游 gpt-image-2 自己读 prompt 决定比例。

  - **NewAPI size=auto 实证**（curl 直打）：

    | prompt | 实测像素 |
    |---|---|
    | puppy + wide cinematic 16:9 | **(1672, 941)** 横图 |
    | girl + vertical portrait full body | **(1024, 1536)** 竖图 |
    | cute cat icon + square avatar | **(1254, 1254)** 方图 |
    | 1024x1024 显式 | (1024, 1024) |
    | 1536x1024 显式 | (1536, 1024) |

    NewAPI 完全透传 `size=auto` 到 gpt-image-2，并按 prompt 自由出图。

  - **三个 commit**（本地 + 服务器 scp 同步）：

    | SHA | 内容 |
    |---|---|
    | `00f20e1` | `fix(art): 放开图片固定尺寸，让 LLM 按内容选宽高比`（仅 fixed_size_enabled=true→false） |
    | `4536958` | `feat(art): 支持 size=auto (NewAPI gpt-image-2 透传+上游自选)` —— 加 `validate_image_size("auto")` 白名单 + `default_size="auto"` |
    | `2e1f462` | `feat(art): default_size=auto 短路 + Size Selector 默认回 auto` —— `get_image_size_async` 开头加短路（`if default_size == "auto": return auto`），让 plugin 真正跳过 LLM 直接发 auto；并改 `SIZE_SELECTOR_SYSTEM_PROMPT` 的 `Default to 1024x1024 if unclear` → `Output "auto" if unclear` |

  - **服务器侧同期变更**（plugin conf 是 bind mount，不能整体 scp 覆盖，按行 sed）：

    ```bash
    # 备份 + 改 fixed_size_enabled
    sed -i 's/^fixed_size_enabled = true/fixed_size_enabled = false/' /root/MaiBot/data/MaiMBot/plugins/1021143806_mais_art_journal/config.toml
    # 备份 + 改 default_size
    sed -i 's/^default_size = .*/default_size = "auto"/' /root/MaiBot/data/MaiMBot/plugins/1021143806_mais_art_journal/config.toml
    # scp 代码（保留 server config.toml）
    scp core/utils/size_utils.py root@43.128.132.248:/root/MaiBot/data/MaiMBot/plugins/1021143806_mais_art_journal/core/utils/
    docker compose restart core
    ```

    服务器端最终配置：`fixed_size_enabled=false`、`default_size="auto"`，plugin 17:08:26 重载成功。

  - **预期间日志新模式**：

    ```
    [plugin.mais_art_journal.size] [主人] default_size=auto，跳过 LLM 尺寸选择，交上游自选
    [plugin.mais_art_journal.api] (OpenAI) 发起图片请求: gpt-image-2 ... size=auto ...
    [plugin.mais_art_journal.api] (OpenAI) 响应: 200 (实际像素非方图)
    ```

  - **下一步路线（视觉专业）**：主人若还要"图生图保留原比例"严格沿用 input_image 维度，单独再开 patch（`get_image_size_for_input_image` 读 base64 维度）—— 不在本轮 scope。

- 2026-08-09: 多参考图能力图谱（仅调研，未实现）
  - 主人问"多张参考图同时参与"的能力，分析过 `zmq175/mais_art_journal` fork（逗号分隔、随机选一张）、AstrBot 圈 `Railgun19457`（`reference_images` 数组 + 队列 + 分批发送）、`muyouzhi6/astrbot_plugin_gitee_aiimg`（批量出图 + LLM 规划多提示词）、`GALIAIS`（输入图 hash 去重）等。
  - API 层统一规范：**gpt-image-2 端 `/v1/images/edits` 用 `image[]` 字段重复最多 16 张**，prompt 模板 `"Image 1 / Image 2 / Image 3"` 显式引用；**Gemini 3 image 用 `contents=[text, img1, img2, ...]` 多模态数组**最多 14 张；**FLUX.2 用 `input_images[]` 数组**，最多 8 张；Midjourney 用 `--sref url1::w url2::w`。
  - 本轮**不实现**，仅有方案图谱。如要实现：plugin 端改 `factories.py` `_load_selfie_reference_image` → 返回 `list[str]`；`call_api.py` → 传 list；`openai_client.py` `payload["image"] = [list]`；`gemini_client.py` `contents = [...]`。
