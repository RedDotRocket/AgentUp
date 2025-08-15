# AgentUp Rate-Limiting

Rate limiting in AgentUp is managed through **middleware**.  
You can apply it globally (network-level) or override for specific plugins.  
Root-level configuration is no longer supported — use middleware only.  

---

## Network-Level Rate Limiting (FastAPI Middleware)

Rate limiting on AgentUp's FastAPI middleware is exposed via `agentup.yml`:

```yaml
rate_limiting:
  enabled: true
  endpoint_limits:
    "/": {"rpm": 100, "burst": 120}
    "/mcp": {"rpm": 60, "burst": 150}
```

**Details:**

| Aspect     | Description                                |
|------------|--------------------------------------------|
| Scope      | All HTTP requests to specific endpoints    |
| Applied    | Before requests reach any plugin code      |
| Purpose    | Network-level protection                   |

The applied Rate Limiting can be seen when starting an Agent in **DEBUG** mode, for example:

```text
2025-07-28 19:43:02 [DEBUG] Network rate limiting middleware initialized endpoint_limits={'/': {'rpm': 100, 'burst': 120}, '/mcp': {'rpm': 50, 'burst': 60}, '/health': {'rpm': 200, 'burst': 240}, '/status': {'rpm': 60, 'burst': 72}, 'default': {'rpm': 60, 'burst': 72}}
```

---

## Plugin-Specific Override (Per-Plugin Middleware)

You can override the global middleware for a specific plugin by adding a plugin-level override in `agentup.yml`:

```yaml
plugins:
- plugin_id: name
    middleware_override:
    - name: rate_limited
      params:
        requests_per_minute: 10
```

**Details:**

| Aspect     | Description                                |
|------------|--------------------------------------------|
| Scope      | ONLY that specific plugin                  |
| Applied    | Replaces global middleware for that plugin |
| Purpose    | Fine-tuned control per plugin              |

---

## ⚠️ Note on Root-Level Configuration

Previous versions of AgentUp allowed **root-level rate limiting config**.  
This is no longer supported — all configuration must now be done through **middleware**.
