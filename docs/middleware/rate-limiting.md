# AgentUp Rate-Limiting

As with all middleware in AgentUp, there is an option to apply globally and
then override for specific plugins, but also network specific

## Network-Level Rate Limiting (FastAPI Middleware)

Rate limiting on AgentUp's FastAPI middleware is exposed via AgentUp's `agentup.yml`

```yaml
rate_limiting:
  enabled: true
  endpoint_limits:
    "/": {"rpm": 100, "burst": 120}
    "/mcp": {"rpm": 60, "burst": 150}
```
| Aspect | Description |
|--------|-------------|
| Scope | All HTTP requests to specific endpoints |
| Applied | Before requests reach any plugin code |
| Purpose | Network-level protection |

The applied Rate Limiting, can be seen when starting an Agent in DEBUG mode, for example:

```
2025-07-28 19:43:02 [DEBUG] Network rate limiting middleware initialized endpoint_limits={'/': {'rpm': 100, 'burst': 120}, '/mcp': {'rpm': 50, 'burst': 60}, '/health': {'rpm': 200, 'burst': 240}, '/status': {'rpm': 60, 'burst': 72}, 'default': {'rpm': 60, 'burst': 72}}

## Root-Level Middleware (Global Plugin Middleware)

Root-level Middleware is applied universally to all plugins (unless as below, over-ridden)

```yaml
  middleware:
    - name: rate_limited
      enabled: true
      params:
        requests_per_minute: 10
```

| Aspect | Description |
|--------|-------------|
| Scope | ALL plugins/capabilities by default |
| Applied | To every plugin function unless overridden |
| Purpose | Organization-wide baseline policies |

## Plugin-Specific Override (Per-Plugin Middleware)

```yaml
plugins:
- plugin_id: name
    middleware_override:
    - name: rate_limited
        params:
        requests_per_minute: 10
```

| Aspect | Description |
|--------|-------------|
| Scope | ONLY that specific plugin |
| Applied | Replaces global middleware for that plugin |
| Purpose | Fine-tuned control per plugin |

