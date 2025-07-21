# Navigation Ordering Guide

This guide explains how to control the sort order of items in the table of contents and navigation sidebar in your AgentUp documentation.

## Current Ordering System

The navigation system uses the `order` property from frontmatter to determine the sort order of sections and pages.

## Method 1: Frontmatter Order Property

The simplest way to control order is by adding an `order` field to your markdown files' frontmatter:

```markdown
---
title: "Installation"
order: 1
---

# Installation Guide
```

```markdown
---
title: "Configuration"
order: 2
---

# Configuration Guide
```

```markdown
---
title: "Advanced Topics"
order: 99
---

# Advanced Topics
```

**How it works:**
- Lower numbers appear first (1 comes before 2)
- If no order is specified, defaults to 0
- Items with the same order are sorted alphabetically

## Method 2: Section Ordering with _meta.json

For directory sections, create a `_meta.json` file in the directory:

### Example Directory Structure
```
docs/
├── getting-started/
│   ├── _meta.json
│   ├── installation.md
│   └── quickstart.md
├── guides/
│   ├── _meta.json
│   └── ...
└── reference/
    ├── _meta.json
    └── ...
```

### _meta.json Content
```json
{
  "title": "Getting Started",
  "order": 1
}
```

This controls where the entire "Getting Started" section appears relative to other sections.

## Method 3: Combining Both Approaches

Use `_meta.json` for section ordering and frontmatter for page ordering within sections:

### Section: getting-started/_meta.json
```json
{
  "title": "Getting Started",
  "order": 1
}
```

### Page: getting-started/installation.md
```markdown
---
title: "Installation"
order: 1
---
```

### Page: getting-started/quickstart.md
```markdown
---
title: "Quick Start"
order: 2
---
```

## Common Ordering Patterns

### 1. Sequential Documentation Flow
```
Order 1: Introduction
Order 2: Installation
Order 3: Getting Started
Order 4: Core Concepts
Order 5: Guides
Order 10: API Reference
Order 20: Troubleshooting
```

### 2. Priority-Based Ordering
```
Order 10: Most Important
Order 20: Important
Order 30: Useful
Order 99: Additional Resources
```

### 3. Alphabetical with Exceptions
```
Order 1: Overview (forced first)
Order 2: Quick Start (forced second)
Order: (unset) - Everything else alphabetical
Order: 999: Appendix (forced last)
```

## Best Practices

### 1. Use Consistent Intervals
Leave gaps between order numbers for future additions:
```
Order: 10, 20, 30, 40...
```
This allows inserting new items without renumbering everything.

### 2. Document Your Ordering Scheme
Create a README in your docs explaining the ordering logic:
```markdown
# Documentation Order Guide
- 1-10: Getting started content
- 11-50: Core guides
- 51-100: Advanced topics
- 101-200: API references
- 201+: Appendices
```

### 3. Group Related Content
Use similar order ranges for related content:
```
Authentication:
- order: 30 - Overview
- order: 31 - OAuth Setup
- order: 32 - API Keys
- order: 33 - Troubleshooting
```

## Example Implementation

### Directory Structure
```
docs/
├── getting-started/
│   ├── _meta.json (order: 10)
│   ├── 01-installation.md (order: 1)
│   ├── 02-quickstart.md (order: 2)
│   └── 03-first-agent.md (order: 3)
├── guides/
│   ├── _meta.json (order: 20)
│   ├── authentication/
│   │   ├── _meta.json (order: 10)
│   │   ├── overview.md (order: 1)
│   │   └── oauth.md (order: 2)
│   └── deployment/
│       ├── _meta.json (order: 20)
│       └── ...
└── reference/
    ├── _meta.json (order: 100)
    └── ...
```

### Result in Navigation
1. **Getting Started** (order: 10)
   - Installation (order: 1)
   - Quick Start (order: 2)
   - First Agent (order: 3)
2. **Guides** (order: 20)
   - Authentication (order: 10)
     - Overview (order: 1)
     - OAuth (order: 2)
   - Deployment (order: 20)
3. **Reference** (order: 100)

## Troubleshooting Order Issues

### Items Not Appearing in Expected Order
1. Check frontmatter syntax - YAML is sensitive to formatting
2. Verify the `order` field is a number, not a string
3. Check for duplicate order values
4. Look for missing `_meta.json` files in directories

### Sections Not Ordering Correctly
1. Ensure `_meta.json` is valid JSON
2. Check that `order` property exists in the JSON
3. Verify no syntax errors in the JSON file

### Mixed Ordering
If some items use `order` and others don't:
- Items without `order` default to 0
- This can cause unexpected positioning
- Solution: Add explicit order to all items

## Advanced: Custom Ordering Logic

If you need more complex ordering (e.g., by date, custom fields), you can modify the navigation processing functions in `lib/navigation.ts` to implement custom sort logic:

```typescript
// Example: Sort by date for blog posts
sections.forEach(section => {
  if (section.title === 'Blog') {
    section.items.sort((a, b) => {
      const dateA = new Date(a.date || 0)
      const dateB = new Date(b.date || 0)
      return dateB.getTime() - dateA.getTime() // Newest first
    })
  } else {
    section.items.sort((a, b) => (a.order || 0) - (b.order || 0))
  }
})
```

This guide should help you implement any ordering scheme you need for your documentation!