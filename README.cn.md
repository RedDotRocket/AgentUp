<div align="center">
<a href="README.md">English</a> | 简体中文
</div>

<div align="center">
  <img src="https://raw.githubusercontent.com/RedDotRocket/AgentUp/main/assets/logo.png" alt="AgentUp Logo" width="400"/>
  <h3>为AI智能体带来Docker对容器的革命性改变</h3>
  <br/>

  <!-- CTA 按钮 -->
  <p>
    <a href="https://github.com/RedDotRocket/AgentUp/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22">
      <img src="https://img.shields.io/badge/贡献-新手友好问题-green?style=for-the-badge&logo=github" alt="新手友好问题"/>
    </a>
    &nbsp;
    <a href="https://discord.gg/pPcjYzGvbS">
      <img src="https://img.shields.io/badge/聊天-加入Discord-7289da?style=for-the-badge&logo=discord&logoColor=white" alt="加入Discord"/>
    </a>
  </p>

  <!-- 徽章 -->
  <p>
    <a href="https://opensource.org/licenses/Apache-2.0">
      <img src="https://img.shields.io/badge/许可证-Apache%202.0-blue.svg" alt="许可证"/>
    </a>
    <a href="https://github.com/RedDotRocket/AgentUp/actions/workflows/ci.yml">
      <img src="https://github.com/RedDotRocket/AgentUp/actions/workflows/ci.yml/badge.svg" alt="CI状态"/>
    </a>
    <a href="https://pypi.org/project/AgentUp/">
      <img src="https://img.shields.io/pypi/v/AgentUp.svg" alt="PyPI版本"/>
    </a>
    <a href="https://pepy.tech/project/agentup">
      <img src="https://static.pepy.tech/badge/agentup" alt="下载量"/>
    </a>
    <a href="https://discord.gg/pPcjYzGvbS">
      <img src="https://img.shields.io/discord/1384081906773131274?color=7289da&label=Discord&logo=discord&logoColor=white" alt="Discord"/>
    </a>
    <a href="https://x.com/RedDotRocket">
      <img src="https://img.shields.io/badge/Follow%20on-X-black?style=flat&logoColor=white" alt="Follow on X"/>
    </a>
  </p>
  <br/>
</div>

<!-- 状态框 -->
<div align="center">
   <table>
    <tr>
      <td align="center">
        <strong>🚀 积极开发中</strong>
        <br/>
        <sub>🏃‍♂️ 我们进展很快，可能会有变化！</sub>
        <br/>
      </td>
    </tr>
  </table>
</div>

  <br/>

## 为什么选择AgentUp？

正如Docker让应用程序变得不可变、可重现且运维友好，**AgentUp**为AI智能体带来了同样的革命。通过配置定义您的智能体，它可以在任何地方一致运行。与团队成员分享智能体，他们可以克隆/分叉并立即运行。部署时确信您的智能体在开发、测试和生产环境中都会表现一致。

AgentUp由拥有丰富经验的工程师构建，他们曾为**Google、GitHub、Nvidia、Red Hat、Shopify等公司**的关键任务系统创建开源解决方案。我们深知构建稳定、安全、可扩展软件的要求，并将这些原则应用于让AI智能体真正做到生产就绪、安全可靠。

## AgentUp：开发者优先的智能体框架

AgentUp提供企业级智能体基础架构，专为需要强大功能与简洁性的专业开发者而设计。

**开发者优先的操作**：由了解现实约束的开发者构建。每个智能体都存在于自己的代码库中，仅需一个AgentUp配置文件。克隆、运行`agentup run`，所有依赖项在初始化期间解决——不再有环境设置的烦恼。

**安全设计**：内置基于范围的细粒度访问控制，支持OAuth2、JWT和API密钥认证，防止未授权的工具/MCP访问，确保数据保护。安全不是事后考虑——它是AgentUp的基础架构。

**配置驱动架构**：通过声明式配置定义复杂的智能体行为、数据源和工作流。跳过数周的样板代码和框架争夺。您的智能体成为可移植、可版本化的资产，具有清晰的契约定义其能力和交互。

**可扩展的定制生态系统**：需要RAG、图像处理、自定义API逻辑？没问题。利用社区插件或构建自动继承AgentUp中间件、安全和操作功能的自定义扩展。独立的插件版本控制与现有CI/CD管道无缝集成，确保核心平台更新不会破坏您的实现。使用AgentUp，您可以获得运行智能体的即时反馈，以及框架的可扩展性。

**智能体到智能体发现**：自动A2A智能体卡生成向生态系统中的其他智能体公开您的智能体能力，实现无缝的智能体间通信和编排。

**异步任务架构**：消息驱动的任务管理支持基于回调通知的长时间运行操作。非常适合研究智能体、数据处理工作流和事件驱动自动化。跨Redis和其他后端的状态持久化确保大规模可靠性。

## 面向生产的先进架构

AgentUp在设计时考虑了生产部署，具备随着框架成熟而扩展的架构模式。虽然目前仍在alpha阶段，但核心安全和可扩展性功能已经为构建严肃的AI智能体提供了坚实的基础。

## 保持更新

AgentUp 开发进展很快 🏃‍♂️，要跟进项目动态并第一时间收到新版本通知，请给仓库点星。

<img src="/assets/star.gif" width="40%" height="40%"/>

## 几分钟内开始使用

### 安装

使用您首选的Python包管理器安装AgentUp：

```bash
pip install agentup
```

### 创建您的第一个智能体

通过交互式配置生成新的智能体项目：

```bash
agentup init
```

从可用选项中选择，并通过交互式提示配置您的智能体能力、认证和AI提供商设置。

### 启动您的智能体

启动开发服务器并开始构建：

```bash
agentup run
```

您的智能体现在运行在`http://localhost:8000`，具有完整的A2A兼容JSON RPC API、安全中间件和所有配置的可用能力。

### 下一步

探索全面的[文档](https://docs.agentup.dev)以了解高级功能、教程、API参考和现实世界示例，帮助您快速构建智能体。

### 当前集成

AgentUp智能体能够将自己作为工具呈现给不同的框架，这带来了确保所有工具使用一致且安全、被跟踪和可追溯的优势。

- [CrewAI](https://crewai.com)，详见[文档](docs/integrations/crewai.md)。

## 开源和社区驱动

AgentUp采用Apache 2.0许可证，基于开放标准构建。该框架实现了A2A（智能体到智能体）规范以实现互操作性，并遵循MCP（模型上下文协议）与更广泛的AI工具生态系统集成。

**贡献** - 无论您是修复错误、添加功能还是改进文档，都欢迎贡献。加入不断增长的开发者社区，共同构建AI智能体基础设施的未来。

**社区支持** - 通过[GitHub Issues](https://github.com/RedDotRocket/AgentUp/issues)报告问题、请求功能和获取帮助。在[Discord](https://discord.gg/pPcjYzGvbS)上参与实时讨论并与其他开发者联系。

## 什么是DCO Bot？

我们使用开发者原创证书（DCO）来保持项目的法律健全性并保护我们的社区。这在开源项目中很常见（Linux内核、Kubernetes、Docker）。

DCO防止意外包含专有代码等问题，并确保所有贡献者都有权提交他们的更改。

这保护了项目的贡献者和用户。

### 如何签署提交
在提交时简单地添加`-s`标志：

```bash
git commit -s -m "添加很棒的新功能"
```

这会添加一行"Signed-off-by"，证明您编写了代码或有权限在Apache 2.0下贡献它。您保留对贡献的所有权——无需文书工作！

## 表达您的支持 ⭐

如果AgentUp正在帮助您构建更好的AI智能体，或者您想鼓励开发，请考虑给它一个星标，帮助其他人发现这个项目，也让我知道值得继续投入时间到这个框架中！

[![GitHub stars](https://img.shields.io/github/stars/RedDotRocket/AgentUp.svg?style=social&label=Star)](https://github.com/RedDotRocket/AgentUp)

---

**许可证** - Apache 2.0


[badge-discord-img]: https://img.shields.io/discord/1384081906773131274?label=Discord&logo=discord
[badge-discord-url]: https://discord.gg/pPcjYzGvbS
