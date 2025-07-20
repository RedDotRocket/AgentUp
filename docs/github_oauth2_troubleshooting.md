# GitHub OAuth2 Troubleshooting Guide

## Common Issues and Solutions

### 1. Authentication Failures

#### Issue: "Unauthorized" responses
**Symptoms:**
```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32001,
    "message": "Unauthorized"
  },
  "id": 1
}
```

**Possible Causes & Solutions:**

1. **Invalid Token**
   ```bash
   # Validate your token with GitHub
   curl -X POST https://api.github.com/applications/YOUR_CLIENT_ID/token \
     -u "YOUR_CLIENT_ID:YOUR_CLIENT_SECRET" \
     -H "Content-Type: application/json" \
     -d '{"access_token":"YOUR_TOKEN"}'
   ```

2. **Incorrect Authorization Header**
   ```bash
   # Wrong:
   curl -H "Authorization: YOUR_TOKEN"
   
   # Correct:
   curl -H "Authorization: Bearer YOUR_TOKEN"
   ```

3. **Token Expired**
   - GitHub tokens don't expire automatically, but can be revoked
   - Generate a new token if the old one is invalid

### 2. Configuration Issues

#### Issue: "OAuth2 configuration is required"
**Cause:** Missing or incorrect OAuth2 configuration in `agentup.yml`

**Solution:**
```yaml
security:
  enabled: true
  auth_type: oauth2  # Make sure this is set
  auth:
    oauth2:
      validation_strategy: "introspection"
      introspection_endpoint: "https://api.github.com/applications/{CLIENT_ID}/token"
      client_id: "${GITHUB_CLIENT_ID}"
      client_secret: "${GITHUB_CLIENT_SECRET}"
```

#### Issue: "Token introspection requires client_id and client_secret"
**Cause:** Environment variables not set

**Solution:**
```bash
export GITHUB_CLIENT_ID="your_actual_client_id"
export GITHUB_CLIENT_SECRET="your_actual_client_secret"
```

### 3. Scope Issues

#### Issue: "Required scopes not met"
**Cause:** GitHub token doesn't have required scopes

**Solution:**
1. Check your token scopes:
   ```bash
   curl -H "Authorization: Bearer YOUR_TOKEN" https://api.github.com/user
   ```

2. Generate new token with correct scopes:
   - Go to https://github.com/settings/tokens
   - Select required scopes: `user`, `user:email`

3. Or use GitHub CLI:
   ```bash
   gh auth login --scopes "user,user:email"
   ```

### 4. GitHub API Issues

#### Issue: "Token introspection failed"
**Symptoms:** 404 or 401 from GitHub API

**Possible Causes & Solutions:**

1. **Wrong Client ID in introspection endpoint**
   ```yaml
   # Wrong:
   introspection_endpoint: "https://api.github.com/applications/{CLIENT_ID}/token"
   
   # Correct (replace with actual client ID):
   introspection_endpoint: "https://api.github.com/applications/Iv1.abc123def456/token"
   ```

2. **Invalid Client Credentials**
   ```bash
   # Test your credentials
   curl -X POST https://api.github.com/applications/YOUR_CLIENT_ID/token \
     -u "YOUR_CLIENT_ID:YOUR_CLIENT_SECRET" \
     -H "Content-Type: application/json" \
     -d '{"access_token":"test"}'
   ```

3. **Rate Limiting**
   - GitHub API has rate limits
   - Wait and retry, or use different credentials

### 5. Network Issues

#### Issue: "Connection refused" or timeouts
**Cause:** Network connectivity issues

**Solution:**
1. **Check internet connectivity**
2. **Test GitHub API directly:**
   ```bash
   curl -I https://api.github.com/
   ```
3. **Check proxy settings** if behind corporate firewall
4. **Verify DNS resolution:**
   ```bash
   nslookup api.github.com
   ```

### 6. Server Issues

#### Issue: AgentUp server not responding
**Symptoms:** Connection refused to localhost:8000

**Solution:**
1. **Check if server is running:**
   ```bash
   ps aux | grep agentup
   ```

2. **Check port availability:**
   ```bash
   netstat -tlnp | grep :8000
   ```

3. **Start server in debug mode:**
   ```bash
   agentup agent serve --debug
   ```

4. **Check logs for errors:**
   ```bash
   agentup agent serve --log-level DEBUG
   ```

### 7. Environment Variable Issues

#### Issue: Variables not being substituted
**Symptoms:** Literal `${GITHUB_CLIENT_ID}` in error messages

**Solution:**
1. **Check environment variables are set:**
   ```bash
   echo $GITHUB_CLIENT_ID
   echo $GITHUB_CLIENT_SECRET
   ```

2. **Export variables in current shell:**
   ```bash
   export GITHUB_CLIENT_ID="your_id"
   export GITHUB_CLIENT_SECRET="your_secret"
   ```

3. **Use .env file** (if supported):
   ```bash
   echo "GITHUB_CLIENT_ID=your_id" > .env
   echo "GITHUB_CLIENT_SECRET=your_secret" >> .env
   ```

### 8. JWT vs Introspection Strategy

#### Issue: "JWT validation failed"
**Cause:** Using JWT strategy with GitHub (which uses opaque tokens)

**Solution:**
```yaml
security:
  auth:
    oauth2:
      validation_strategy: "introspection"  # NOT "jwt"
```

GitHub uses opaque tokens, not JWTs, so always use introspection strategy.

## Debugging Steps

### 1. Enable Debug Logging
```yaml
# In agentup.yml
logging:
  level: "DEBUG"
  format: "structured"
```

### 2. Test Components Individually

1. **Test GitHub token validity:**
   ```bash
   curl -H "Authorization: Bearer YOUR_TOKEN" https://api.github.com/user
   ```

2. **Test GitHub introspection endpoint:**
   ```bash
   curl -X POST https://api.github.com/applications/YOUR_CLIENT_ID/token \
     -u "YOUR_CLIENT_ID:YOUR_CLIENT_SECRET" \
     -H "Content-Type: application/json" \
     -d '{"access_token":"YOUR_TOKEN"}'
   ```

3. **Test AgentUp without auth:**
   ```yaml
   # Temporarily disable auth
   security:
     enabled: false
   ```

### 3. Check System Requirements
- Python 3.11+
- Required packages: `authlib`, `httpx`
- Network access to api.github.com

### 4. Verify OAuth App Configuration
1. Go to GitHub Settings > Developer settings > OAuth Apps
2. Check redirect URIs match your setup
3. Verify app is active and not suspended

## Getting Help

If you're still having issues:

1. **Check AgentUp logs** for detailed error messages
2. **Use the test script** with verbose output
3. **Verify all prerequisites** are met
4. **Test with minimal configuration** first
5. **Check GitHub's OAuth documentation** for any changes

## Common Error Codes

| Error Code | Meaning | Solution |
|------------|---------|----------|
| -32001 | Unauthorized | Check token and scopes |
| -32002 | Invalid Request | Check JSON-RPC format |
| -32003 | Internal Error | Check server logs |
| 401 | GitHub API Unauthorized | Check client credentials |
| 404 | GitHub API Not Found | Check endpoint URL |
| 422 | GitHub API Validation Error | Check request format |

## Test Environment Setup

For testing purposes, you can create a minimal setup:

```bash
# 1. Create test directory
mkdir oauth2_test && cd oauth2_test

# 2. Copy example configuration
cp ../examples/oauth2_github_agent/agentup.yml .

# 3. Set environment variables
export GITHUB_CLIENT_ID="your_id"
export GITHUB_CLIENT_SECRET="your_secret"

# 4. Start agent
agentup agent serve

# 5. Test in another terminal
curl -X POST http://localhost:8000/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"status","id":1}'
```

This minimal setup helps isolate configuration issues from your main agent setup.