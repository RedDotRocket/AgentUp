# AgentUp Documentation

!!! warning "Documentation in Progress"
    Development has been moving fast in the AgentUp framework, and this documentation is due for a refresh.
    Once its been updated, this notice will be removed.

Welcome to the AgentUp documentation! 

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

We welcome contributions to improve this documentation, code, and overall experience! Please see our [Contributing Guide](../CONTRIBUTING.md) for details on how to help make AgentUp better for everyone.
