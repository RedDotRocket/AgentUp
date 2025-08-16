# AgentUp

<p align="center">
  <img src="assets/compie.png" alt="Compie Logo" width="200"/>
</p>

<p align="center">
  <a href="https://opensource.org/licenses/Apache-2.0"><img src="https://img.shields.io/badge/License-Apache2.0-brightgreen.svg?style=flat" alt="License: Apache 2.0"/></a>
  |
  <a href="https://github.com/RedDotRocket/AgentUp/actions/workflows/ci.yml"><img src="https://github.com/RedDotRocket/AgentUp/actions/workflows/ci.yml/badge.svg" alt="CI"/></a>
  |
  <a href="https://discord.gg/pPcjYzGvbS"><img src="https://img.shields.io/discord/1384081906773131274?label=Discord&logo=discord" alt="Discord"/></a>
  |
  <a href="https://pypi.org/project/AgentUp/"><img src="https://img.shields.io/pypi/v/AgentUp.svg" alt="PyPI Version"/></a>
  |
  <a href="https://pepy.tech/project/agentup"><img src="https://static.pepy.tech/badge/agentup" alt="Downloads"/></a>
</p>

<p align="center">
  AgentUp 在设计时将安全性、可扩展性和可延展性作为其基础，通过配置驱动的架构简化开发流程。它消除了样板代码，并提供了一个不断增长的社区插件生态系统，以根据需要扩展功能。快速前进，按需扩展。
</p>
<p align="center">
  由 <a href="https://sigstore.dev">Sigstore</a> 的创建者构建。
</p>

> ⚠️ **警告：此项目正在积极开发中**
>
> 此项目目前**不稳定**，可能会频繁更改。功能可能会在没有通知的情况下被添加、删除或修改。
> 欢迎贡献，但请注意代码库可能会快速变化，尽管我们会尽可能减少破坏性更改。


## 为什么选择 AgentUp？

**配置优于代码** - 通过 YAML 配置定义复杂的代理行为、数据源和工作流。无需样板代码，无需框架内部实现，无需冗长的开发周期。您的代理是可移植的、可版本化的和可维护的。

**设计即安全** - 工具 / MCP 服务器（插件！）受到 AgentUp 细粒度的基于作用域的访问控制系统保护。细粒度权限确保您的插件和 MCP 服务器只在需要时访问它们需要的内容，并且只有在您授权的情况下才能访问。内置的 OAuth2、JWT 和 API 密钥身份验证可与您现有的身份提供商集成。

**插件生态系统** - 通过不断增长的社区插件生态系统扩展功能，或构建您自己的插件。插件自动继承 AgentUp 的所有中间件、安全和操作功能。独立版本化插件，并与您现有的 CI/CD 管道无缝集成。


## 面向生产的高级架构

AgentUp 在设计时考虑了生产部署，具有随着框架成熟而扩展的架构模式。虽然目前处于 alpha 阶段，但核心安全和可扩展性功能为构建严肃的 AI 代理提供了坚实的基础。

### 高级安全模型

**基于作用域的访问控制** - AgentUp 的权限系统精确控制每个插件、MCP 服务器和功能可以访问的内容。创建从简单设置到复杂需求的分层作用域策略。内置的 OAuth2、JWT 和 API 密钥身份验证提供灵活的集成选项。

**全面的审计日志** - 每个操作都记录有经过清理的审计跟踪。安全事件按风险级别自动分类，便于监控代理行为。可配置的数据保留策略支持各种合规要求。

**安全优先设计** - AgentUp 遵循安全优先原则，具有故障关闭访问控制、输入清理和全面的错误处理。该框架旨在防止权限提升、注入攻击和信息泄露。

### 可扩展的插件系统

**零摩擦开发** - 无需触及核心代码即可创建自定义功能。插件自动继承 AgentUp 的中间件栈、安全模型和操作功能。使用您现有的包管理器（pip、uv、poetry）进行依赖管理和分发。

**社区生态系统** - 通过 [AgentUp 插件注册表](https://agentup.dev) 发现和安装插件，或发布您自己的插件。浏览系统工具、图像处理、数据分析和专业功能的插件。使用您喜欢的 Python 工具（pip、uv、poetry）安装或使用 twine 发布。每个插件都是独立版本化的，可以在不影响其他组件的情况下更新。发布到注册表的每个插件都会自动扫描安全漏洞、不安全的编码模式和恶意软件 - 确保生态系统的安全。

**MCP 集成** - 利用不断扩展的模型上下文协议生态系统。所有 MCP 服务器都通过 AgentUp 的作用域系统自动保护，您可以将自己的代理功能作为 MCP 可流式端点公开，供其他系统使用！

### 灵活的基础设施

**多提供商 AI 支持** - 通过 OpenAI 兼容的 API（Ollama）连接到 OpenAI、Anthropic 或本地模型。无需代码更改即可切换提供商，并同时使用多个提供商实现不同的功能。

**可配置的状态管理** - 选择您的存储后端以满足您的需求。用于开发的文件系统 / 内存，用于结构化查询的数据库，或用于高性能分布式缓存的 Redis/Valkey。内置的对话跟踪具有可配置的 TTL 和历史管理。

**代理间通信** - 通过 A2A（代理对代理）协议合规性构建多代理系统。代理可以安全地相互发现和通信，实现复杂的工作流和分布式处理。AgentUp 建立在 A2A（代理对代理）规范之上，维护者积极参与 A2A 社区。

### 开发者体验

**CLI 优先的工作流** - 您需要的一切都可以通过命令行获得。从模板创建新代理、启动开发服务器、管理插件，并使用与您现有工具链集成的直观命令部署到生产环境。

**配置即代码** - 代理行为、数据源和工作流通过版本控制的 YAML 配置定义。无需学习框架内部，无需维护样板代码。您的代理可在环境和团队之间移植。

**实时操作** - 内置支持流式响应、异步操作和推送通知。通过全面的日志记录和可配置的指标收集监控代理性能和行为。

## 几分钟内开始

### 安装

使用您喜欢的 Python 包管理器安装 AgentUp：

```bash
pip install agentup
```

### 创建您的第一个代理

使用交互式配置生成新的代理项目：

```bash
agentup init
```

从可用选项中选择，并通过交互式提示配置您的代理的功能、身份验证和 AI 提供商设置。

### 开始开发

启动开发服务器并开始构建：

```bash
agentup run
```

您的代理现在运行在 `http://localhost:8000`，具有完整的 A2A 兼容 JSON RPC API、安全中间件和所有配置的功能。

### 下一步

探索全面的[文档](https://docs.agentup.dev)，了解高级功能、教程、API 参考和真实示例，帮助您快速构建代理。

## 开源和社区驱动

AgentUp 采用 Apache 2.0 许可证，基于开放标准构建。该框架实现了 A2A（代理对代理）规范以实现互操作性，并遵循 MCP（模型上下文协议）以与更广泛的 AI 工具生态系统集成。

**贡献** - 无论您是修复错误、添加功能还是改进文档，我们都欢迎贡献。加入不断增长的开发者社区，共同构建 AI 代理基础设施的未来。

**社区支持** - 通过 [GitHub Issues](https://github.com/RedDotRocket/AgentUp/issues) 报告问题、请求功能和获取帮助。在 [Discord](https://discord.gg/pPcjYzGvbS) 上加入实时讨论并与其他开发者联系。

## 表达您的支持 ⭐

如果 AgentUp 正在帮助您构建更好的 AI 代理，或者您想鼓励开发，请考虑给它一个星标，以帮助其他人发现该项目，并让我知道继续投入时间到这个框架是值得的！

[![GitHub stars](https://img.shields.io/github/stars/RedDotRocket/AgentUp.svg?style=social&label=Star)](https://github.com/RedDotRocket/AgentUp)

---

**许可证** - Apache 2.0


[badge-discord-img]: https://img.shields.io/discord/1384081906773131274?label=Discord&logo=discord
[badge-discord-url]: https://discord.gg/pPcjYzGvbS
