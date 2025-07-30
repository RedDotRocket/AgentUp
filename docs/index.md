# AgentUp Documentation

<p align="center">
  <img src="images/compie.png" alt="AgentUp Logo" width="150"/>
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
  Designed with security, scalability, and extensibility at its foundation, AgentUp streamlines development through a configuration-driven architecture.
</p>

## Welcome to the AgentUp documentation! 

You'll find everything you need here to get started with AgentUp, from installation to advanced configuration and troubleshooting.

## How This Guide is Organized

### Progressive disclosure

This documentation follows a [progressive disclosure](https://en.wikipedia.org/wiki/Progressive_disclosure) approach:

<img src="images/next.png" alt="drawing" width="300"/>

1. **Quick Start sections** get you up and running immediately
2. **Detailed guides** provide comprehensive coverage of each topic
3. **Reference materials** offer complete technical specifications
4. **Troubleshooting** helps solve specific problems

Each section starts with a preequisites list. No asumptions are made about your prior knowledge. We intend for all to come on this journey, so we will start with the basics and build up from there.

!!! Prerequisites
    What you need before starting, e.g.:

    * Python version
    * Libraries
    * Snacks
    * Hat and sun protector

We attempt to narrow in on the essentials:

- Code blocks for commands and code snippets
- Highlighted lines for key parts of code examples

``` py hl_lines="2 3"
def bubble_sort(items):
    for i in range(len(items)):
        for j in range(len(items) - 1 - i):
            if items[j] > items[j + 1]:
                items[j], items[j + 1] = items[j + 1], items[j]
```

#### Helpful Tips

We attempt to teach as we go along, so you can learn the concepts behind the commands. You should see lots of **tips** at various intervals, there to help you understand the underlying principles of AgentUp.

!!! tip
    **AgentUp** is designed to be **extensible**. You can create custom plugins for reuse or share with the community.

## Human Curated Documentation

Time has been taken to ensure clarity and accuracy, so you can trust the information provided here. You won't find a sea of emojis or mermaid diagrams galore. We believe in quality over quantity, and we hope you appreciate the effort that has been invested in creating this documentation.

---

## Support and Community

Should you need help or want to connect with other users, we have several options:

- **Discord**: Jump on [Discord](https://discord.gg/pPcjYzGvbS), we would love to have you!
- **GitHub Issues**: [Report bugs and request features](https://github.com/rdrocket-projects/AgentUp/issues)

---

## Contributing

We welcome contributions to improve this documentation, code, and overall experience!
