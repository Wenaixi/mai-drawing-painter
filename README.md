# 麦麦绘卷 (Claude MAInet)

[![Release](https://img.shields.io/github/v/release/Wenaixi/mai-drawing-painter?style=flat-square&color=blue&label=release)](https://github.com/Wenaixi/mai-drawing-painter/releases)
[![CI](https://img.shields.io/github/actions/workflow/status/Wenaixi/mai-drawing-painter/ci.yml?branch=main&style=flat-square&label=CI)](https://github.com/Wenaixi/mai-drawing-painter/actions)
[![License](https://img.shields.io/badge/license-GPL--v3.0--or--later-green?style=flat-square)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12%20%7C%203.13-blue?style=flat-square)](https://www.python.org/)
[![MaiBot](https://img.shields.io/badge/MaiBot-1.2%2B-orange?style=flat-square)](https://docs.mai-mai.org)

> 本插件由 [Wenaixi](https://github.com/Wenaixi) 维护，是专为生产环境深度调优的高可用分支。

## 简介与定位

基于 MaiBot 的多模型智能生图插件，支持图生图、文生图与说说生活照配图。

- **插件目录**：`wenaixi_mai_drawing_painter`
- **开源许可证**：`GPL-3.0`

---

## 核心特性与本地深度调优

- 修复国内双栈 IPv4 优先解析，防死锁
- 注入现代 Chrome User-Agent 绕过 Cloudflare 1010 防火墙
- 生图调用增加 10 次弹性重试与指数退避

---

## 指令与工具速查

### 常用指令 (Command)
- `/dr <提示词> - 快速生成画作`

### 大模型工具 (Tool)
- `@Tool("draw_picture") - 大模型自主调用绘图工具`

---

## 快速配置

配置文件统一定位于插件根目录下的 `config.toml`。修改后重启或通过 WebUI 热重载即可生效。

---

## 上游项目与开源溯源

- **原作者 / 组织**：`1021143806 (Cloude / MAInet)`
- **官方原版开源仓库**：[https://github.com/1021143806/mais_art_journal](https://github.com/1021143806/mais_art_journal)
- **开源协议**：`GPL-3.0`
- **声明**：本项目遵循开源协议，特此致敬原作者的杰出贡献。本分支针对生产环境的高并发网络、个性化社交和抗风控需求进行了深度稳定性修复与定制化演进。