# Admonitions Guide

Admonitions are special callout boxes that help highlight important information in your documentation. They provide visual emphasis and can organize content like warnings, tips, and examples.

## Basic Syntax

### Static Admonitions

Use three exclamation marks (`!!!`) for admonitions that are always visible:

```markdown
!!! note "Optional Custom Title"
    This is the content of the admonition.
    All content lines must be indented with exactly 4 spaces.
    
    You can include multiple paragraphs, lists, and even code blocks.
```

### Collapsible Admonitions

Use three question marks (`???`) for admonitions that can be collapsed:

```markdown
??? tip "Click to expand this tip"
    This content is hidden by default.
    Users can click the header to expand and view the content.
```

### Expanded Collapsible Admonitions

Use `???+` to create a collapsible admonition that's expanded by default:

```markdown
???+ warning "Important Warning (expanded by default)"
    This content is visible by default.
    Users can still click to collapse it if needed.
```

## Available Admonition Types

The following types are available, each with its own color scheme and icon:

### Informational Types

!!! note "Note"
    General information or notes. Uses a blue color scheme with an info icon.

!!! abstract "Abstract"
    For summaries or abstracts. Uses an indigo color scheme with a document icon.

!!! info "Information"
    Informational content. Uses a blue color scheme with an info icon.

### Positive Types

!!! tip "Tip"
    Helpful tips and best practices. Uses an emerald color scheme with a lightbulb icon.

!!! success "Success"
    Success messages or confirmations. Uses a green color scheme with a check circle icon.

### Attention Types

!!! question "Question"
    Questions or FAQs. Uses a purple color scheme with a help circle icon.

!!! warning "Warning"
    Important warnings. Uses a yellow color scheme with a warning triangle icon.

### Critical Types

!!! failure "Failure"
    Failure notifications. Uses a red color scheme with an X circle icon.

!!! danger "Danger"
    Critical warnings about dangerous operations. Uses a red color scheme with an alert octagon icon.

!!! bug "Bug"
    Bug reports or known issues. Uses a rust color scheme with a bug icon.

### Special Types

!!! example "Example"
    Code examples or demonstrations. Uses a slate color scheme with a code icon.

!!! quote "Quote"
    Quotations or citations. Uses a charcoal color scheme with a quote icon.

## Syntax Rules and Requirements

### 1. Indentation
All content within an admonition **must** be indented with exactly 4 spaces:

```markdown
!!! note
    ✓ This line has 4 spaces - correct!
        ✗ This line has 8 spaces - incorrect!
  ✗ This line has 2 spaces - incorrect!
```

### 2. Title Handling
- Titles are optional and must be enclosed in double quotes
- If no title is provided, the type name is capitalized and used as the title

```markdown
!!! tip
    This will have "Tip" as the title

!!! tip "Pro Tip"
    This will have "Pro Tip" as the title
```

### 3. Multi-line Content
Maintain the 4-space indentation for all lines:

```markdown
!!! example "Complete Example"
    Here's a multi-line example with various content:
    
    - First list item
    - Second list item
    
    ```python
    def hello():
        print("Hello, World!")
    ```
    
    And some final text.
```

### 4. Nested Content
You can include any markdown content inside admonitions:

```markdown
!!! note "Nested Content Example"
    You can include:
    
    **Bold text**, *italic text*, and `inline code`
    
    > Blockquotes work too!
    
    1. Numbered lists
    2. With multiple items
    
    Even tables:
    
    | Column 1 | Column 2 |
    |----------|----------|
    | Data 1   | Data 2   |
```

## Common Use Cases

### Security Warnings
```markdown
!!! danger "Security Warning"
    Never commit API keys or passwords to your repository!
    Always use environment variables for sensitive data.
```

### Installation Notes
```markdown
!!! info "System Requirements"
    This package requires:
    - Python 3.10 or higher
    - 4GB of RAM minimum
    - 10GB of free disk space
```

### Troubleshooting
```markdown
??? failure "Installation Failed?"
    If you encounter installation errors:
    
    1. Check your Python version: `python --version`
    2. Update pip: `pip install --upgrade pip`
    3. Try installing in a virtual environment
```

### Code Examples
```markdown
???+ example "API Usage Example"
    ```python
    from agentup import Agent
    
    # Create a new agent
    agent = Agent(name="MyAgent")
    
    # Start the agent
    agent.start()
    ```
```

## Best Practices

1. **Choose the Right Type**: Use the appropriate admonition type for your content
   - `tip` for helpful suggestions
   - `warning` for important cautions
   - `danger` for critical warnings
   - `example` for code demonstrations

2. **Keep Titles Concise**: Titles should be short and descriptive

3. **Use Collapsible for Long Content**: If the admonition contains lengthy content, consider using the collapsible syntax (`???`)

4. **Be Consistent**: Use the same type for similar content throughout your documentation

5. **Don't Overuse**: Too many admonitions can be distracting. Use them to highlight truly important information

## Troubleshooting

### Content Not Showing
If your admonition content isn't displaying:
- Check that all content lines have exactly 4 spaces of indentation
- Ensure there's a blank line before and after the admonition
- Verify the type is one of the 12 valid types (lowercase)

### Title Not Displaying
- Make sure titles are enclosed in double quotes
- Check for any escaped quotes in the title

### Collapsible Not Working
- Verify you're using `???` (three question marks) not `!!!`
- For expanded by default, ensure you're using `???+` with the plus sign

## Examples Gallery

Here's a quick reference of all types:

```markdown
!!! note "Note Example"
    General information

!!! abstract "Abstract Example"
    Summary content

!!! info "Info Example"
    Informational content

!!! tip "Tip Example"
    Helpful suggestion

!!! success "Success Example"
    Operation successful

!!! question "Question Example"
    Frequently asked question

!!! warning "Warning Example"
    Important warning

!!! failure "Failure Example"
    Operation failed

!!! danger "Danger Example"
    Critical warning

!!! bug "Bug Example"
    Known issue

!!! example "Example Example"
    Code demonstration

!!! quote "Quote Example"
    Citation or quotation
```

This guide covers all aspects of using admonitions in your AgentUp documentation. The admonition system provides a powerful way to structure and highlight important information while maintaining the consistent retro comic book theme of your documentation site.