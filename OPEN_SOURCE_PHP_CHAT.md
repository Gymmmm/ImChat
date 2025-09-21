# 开源 PHP 聊天/IM 项目推荐

围绕“类似微信的即时通讯”这一需求，下列项目/方案都以 PHP 为核心或主要后端语言，能够提供点对点、群聊、消息持久化等能力。后续仍保留若干传统网页聊天室/客服系统，便于按场景选型。

## 一、类微信即时通讯（全双工 IM）

### 1. Workerman Chat / GatewayWorker
- **项目地址**：https://github.com/walkor/workerman-chat （基于 Workerman/GatewayWorker）
- **主要特性**：PHP 长连接服务器，支持在线/离线消息、好友/群组、聊天记录落库、WebSocket 推送；可扩展语音/文件发送等业务逻辑。
- **部署要点**：
  - 依赖 PHP 7.0+（建议 7.4+/8.x）及 `pcntl`、`posix` 扩展；在 Linux 环境启动 `php start.php start -d` 即可后台运行。
  - 可与 MySQL/Redis 组合实现消息存储、未读计数、设备多端同步。
  - 官方示例自带 H5 客户端，可结合 uni-app、Flutter 等构建移动端界面。
- **适用场景**：自建实时 IM、需要灵活定制业务逻辑且更贴近微信交互（好友、群聊、表情、文件等）。

### 2. Swoole Distributed IM 示例
- **项目地址**：https://github.com/swoole/distributed-IM
- **主要特性**：基于 Swoole 扩展的分布式 IM 后端，提供多节点长连接、消息路由、群聊、历史消息存储，以及简单的 Web/H5 客户端示例。
- **部署要点**：
  - 需要 PHP 7.2+/8.x 并安装 Swoole 扩展；Redis、MySQL 用作状态/历史存储，Nginx 反向代理 WebSocket。
  - 采用集群化架构，可横向扩容 Worker；支持为移动端提供 HTTP 登录接口 + WebSocket 推送。
- **适用场景**：需要高并发、分布式部署的 IM（例如内部社交、企业沟通），或希望以 PHP 实现服务端同时接入多端客户端。

### 3. PHP+GatewayWorker 社交 IM 脚手架
- **项目地址**：https://github.com/walkor/gatewayworker (框架) + 社区衍生脚手架如 https://gitee.com/matyhtf/Chat (示例)
- **主要特性**：通过 GatewayWorker 提供连接管理、心跳、广播、分布式路由；衍生脚手架整合注册登录、好友管理、群组、系统通知等模块，适合作为“微信类”IM 基础工程。
- **部署要点**：
  - 先安装 GatewayWorker，按示例脚手架配置数据库（MySQL）与缓存（Redis）。
  - 结合 Laravel/ThinkPHP 等框架提供 REST/管理后台，GatewayWorker 负责实时推送层。
- **适用场景**：需要更完整的 IM 基建（账号体系、联系人、群组、离线推送），同时希望用 PHP 生态快速二次开发。

#### 类微信 IM 的补充建议
1. **客户端选择**：
   - H5/桌面：直接复用官方示例或自研基于 Vue/React 的 Web 客户端。
   - 移动端：常见做法是通过 uni-app/Flutter/React Native 调用 PHP 提供的 REST 登录接口，再建立 WebSocket 连接。
2. **关键功能实现**：
   - **消息可靠性**：消息写入数据库/Redis 后再下发，失败时客户端可轮询补偿。
   - **离线/推送**：对接 APNs/FCM 或企业自研推送服务；同时维护未读计数。
   - **多媒体**：通过对象存储（OSS、COS、S3 等）存放图片/语音/文件，消息体保存文件 URL 与元数据。
3. **安全与扩展**：使用 JWT/自定义 Token 校验、TLS WebSocket；可叠加消息加密、审计与风控模块。

## 二、传统网页聊天室/客服系统

以下项目更偏重于嵌入式聊天室或在线客服，如不需要“好友+社交”模型亦可选用。

### 1. phpFreeChat
- **项目地址**：https://github.com/kerphi/phpfreechat
- **主要特性**：基于 PHP + JavaScript 的无数据库即时聊天，支持房间管理、用户昵称、私聊以及多语言界面。
- **部署要点**：解压源码后配置 `data/` 目录写权限，基于文件系统存储聊天记录；可嵌入到任意 PHP 页面。
- **适用场景**：需要快速在现有 PHP 网站中嵌入轻量级聊天室。

### 2. blueimp's AJAX Chat
- **项目地址**：https://blueimp.net/ajax/
- **主要特性**：经典的 PHP + MySQL 聊天室，内置用户权限、频道、私聊、IRC 网关等；界面可通过主题自定义。
- **部署要点**：需要 PHP 5.6+/MySQL 数据库，配置 `lib/config.php` 以设置数据库和频道信息。
- **适用场景**：需要传统网页聊天室、希望复用成熟权限体系的团队或论坛。

### 3. Live Helper Chat
- **项目地址**：https://github.com/LiveHelperChat/livehelperchat
- **主要特性**：面向客服/工单的实时聊天系统，提供访客端浮窗、客服面板、机器人流程、统计报表及移动端应用。
- **部署要点**：推荐使用 PHP 8.1+/MySQL；官方提供 Docker 镜像与 Web 安装向导，支持扩展到多客服和多语言。
- **适用场景**：希望搭建客服 IM、支持自动化和监控功能的企业或团队。

### 4. Mibew Messenger
- **项目地址**：https://github.com/Mibew/mibew
- **主要特性**：纯 PHP/JS 开源客服聊天系统，支持访客追踪、预设回复、离线留言以及插件/皮肤体系。
- **部署要点**：要求 PHP 7.2+/MySQL；部署后通过 Web 向导初始化数据库，支持通过 REST/WebSocket 扩展实时性。
- **适用场景**：需要自托管在线客服、强调插件扩展的团队。

### 5. Chatwoot（PHP 网关）
- **项目地址**：https://github.com/chatwoot/chatwoot
- **主要特性**：虽然核心为 Ruby on Rails，但官方维护的 PHP SDK/Webhook 可与现有 PHP 系统集成；支持多渠道统一客服、机器人、知识库。
- **部署要点**：建议使用 Docker 或 Heroku 部署核心服务，再通过 PHP SDK 对接现有网站，实现消息同步和用户身份验证。
- **适用场景**：需要全渠道 IM/客服，但仍希望与 PHP 业务系统深度集成的场合。

---

### 选型建议
1. **需要“类似微信”的社交 IM**：优先考虑 Workerman/GatewayWorker、Swoole Distributed IM 等长连接方案；根据并发量规划 Redis/消息队列。
2. **客服/站内轻量聊天**：phpFreeChat、blueimp AJAX Chat 更易部署；客服场景可选 Live Helper Chat、Mibew 或 Chatwoot。
3. **可维护性**：关注项目最近的提交频率和 issue 活跃度，优先选择仍在更新的社区；或基于框架（如 GatewayWorker）自建核心模块。
4. **二次开发**：结合 Laravel、ThinkPHP、Symfony 等框架实现业务层 API，再与实时通信层（Workerman/Swoole）通过消息队列或 Redis 通道解耦。

> 若需进一步贴近微信体验（朋友圈、支付、公众号等），可在上述 IM 底座上扩展动态、支付、机器人等模块，并结合小程序/APP 前端统一 UI 风格。
