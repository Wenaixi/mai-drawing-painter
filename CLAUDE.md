# CLAUDE.md - 麦麦绘卷 (Claude MAInet) (1021143806_mais_art_journal)

## 1. 模块定位与系统职责
- **插件标识符**：`1021143806_mais_art_journal`
- **当前生效版本**：`v4.1.0`
- **托管仓库**：[`Wenaixi/mais_art_journal`](https://github.com/Wenaixi/mais_art_journal)
- **核心定位**：基于 MaiBot 的多模型智能生图插件，支持配图生成、图生图与风格渲染。

## 2. 关键工程规范与配置说明
- **配置路径**：`config.toml`（所有业务调优与鉴权参数收敛于此）；
- **数据持久化**：优先遵循 MaiBot SDK 标准持久化规范，不直接向源码目录写入易失数据；
- **编码与日志规范**：严格遵循 PEP 8 风格，文档与代码注释杜绝 emoji，避免虚假套话。

## 3. 本地深度定制与稳定性修复
修复了国内双栈网络下 IPv4 优先解析防死锁、现代浏览器 User-Agent 伪装防 Cloudflare 拦截，并将模型重试提升至 10 次。

---

## 上游项目与开源溯源
- **原作者 / 组织**：`1021143806 (Cloude / MAInet)`
- **官方上游仓库**：[https://github.com/1021143806/mais_art_journal](https://github.com/1021143806/mais_art_journal)
- **开源许可证**：`GPL-3.0`
- **分支演进模式**：本仓库作为主人的深度定制与生产维护分支（`Wenaixi/mais_art_journal`）。在保持与官方上游架构演进对齐的同时，锁死并持续维护针对本服务器生产环境的稳定性补丁与核心特性。
