# 麦麦绘卷（1021143806_mais_art_journal）

源: GitHub 用户 `1021143806/mais_art_journal`  
插件 ID: `1021143806.mais_art_journal` 版本 v4.2.0  
路径: `/root/MaiBot/data/MaiMBot/plugins/1021143806_mais_art_journal/`

## 主人改过的关键文件

- `config.toml`：`[[models.items]]` 加 `model1` 指向 NewAPI `https://api.wenxi.dev/v1`，`format=openai`，`model=gpt-image-2`，`api_key=Bearer sk-...`（主人 newapi_channel_conn）。
- `images/reference.jpg`（同内容 `reference.jfif`，约 310KB，1843x2693 JPEG）—— 人设参考图。
- `[selfie]`：`enabled=true`、`reference_image_path = "images/reference.jpg"`、`prompt_prefix` 留空。

## 配置要点

- 默认 / 命令 / 自拍模型均指向 `model1`；`fixed_size_enabled=false`，LLM 按内容选竖/横/方，`default_size=1024x1024` 仅作兜底。
- MaiTrace 跨插件 `generate_image` 超时 `timeout_ms=600000`（10 分钟，对齐 OpenAI 客户端 600s）。
- 自拍 / MaiTrace 配图在 `selfie_mode` 下读此图走图生图（仅在 `support_img2img=true` 的模型上生效）。

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
