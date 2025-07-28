# GitHub OAuth2 Setup Guide for AgentUp

## Overview
This guide walks you through setting up GitHub OAuth2 authentication with AgentUp. You'll perform all the setup steps while this guide provides detailed instructions.

## Prerequisites
- AgentUp development environment set up
- GitHub account
- Basic understanding of OAuth2 flow

## Step 1: Create GitHub OAuth App

### 1.1 Navigate to GitHub Settings
1. Go to GitHub.com and log in
2. Click your profile picture (top right)
3. Select "Settings"
4. In the left sidebar, click "Developer settings"
5. Click "OAuth Apps"
6. Click "New OAuth App"

### 1.2 Configure OAuth App
Fill in the following details:

**Application name:** `AgentUp Test`
**Homepage URL:** `http://localhost:8000`
**Application description:** `Testing OAuth2 with AgentUp`
**Authorization callback URL:** `http://localhost:8000/callback`

### 1.3 Save and Note Credentials
1. Click "Register application"
2. **IMPORTANT:** Copy and save the following:
   - Client ID (publicly visible)
   - Client Secret (click "Generate a new client secret" if needed)

## Step 2: Configure AgentUp Agent

### 2.1 Create Agent Configuration
Create a new file `agentup.yml` in your agent directory with the following content:

```yaml
# Agent Configuration with GitHub OAuth2
name: "oauth2-test-agent"
description: "Testing GitHub OAuth2 authentication"
version: "1.0.0"

# Security configuration
security:
  enabled: true
  auth_type: oauth2
  auth:
    oauth2:
      # Use introspection strategy for GitHub (opaque tokens)
      validation_strategy: "introspection"

      # GitHub token introspection endpoint
      introspection_endpoint: "https://api.github.com/applications/{CLIENT_ID}/token"

      # Your GitHub OAuth app credentials
      client_id: "${GITHUB_CLIENT_ID}"
      client_secret: "${GITHUB_CLIENT_SECRET}"

      # Required GitHub scopes
      required_scopes: ["user", "user:email"]

  # Scope hierarchy for your agent
  scope_hierarchy:
    admin: ["*"]
    user: ["user:email"]
    user:email: []

# Enable basic plugins for testing
plugins:
  - plugin_id: system_tools

# Basic server configuration
server:
  host: "0.0.0.0"
  port: 8000
  debug: true
```

### 2.2 Set Environment Variables
Replace `YOUR_CLIENT_ID` and `YOUR_CLIENT_SECRET` with your actual GitHub OAuth app credentials:

```bash
export GITHUB_CLIENT_ID="your_actual_client_id"
export GITHUB_CLIENT_SECRET="your_actual_client_secret"
```

## Step 3: Start Your Agent

### 3.1 Start the Agent Server
```bash
cd /path/to/your/agent
agentup agent serve
```

You should see output similar to:
```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

## Step 4: Test the OAuth2 Flow

### 4.1 Get GitHub Access Token
Since AgentUp expects you to already have a GitHub token, you'll need to get one. You can:

**Option A: Use GitHub CLI (Recommended)**
```bash
# Install GitHub CLI if you haven't already
# macOS: brew install gh
# Other platforms: https://cli.github.com/

# Authenticate and get token
gh auth login
gh auth token
```

**Option B: Use GitHub Personal Access Token**
1. Go to GitHub Settings > Developer settings > Personal access tokens > Tokens (classic)
2. Click "Generate new token (classic)"
3. Select scopes: `user`, `user:email`
4. Generate and copy the token

**Option C: Use OAuth2 Flow Manually**
```bash
# 1. Get authorization URL (replace YOUR_CLIENT_ID)
echo "Visit this URL in your browser:"
echo "https://github.com/login/oauth/authorize?client_id=YOUR_CLIENT_ID&scope=user%20user:email&redirect_uri=http://localhost:8000/callback"

# 2. After authorization, you'll be redirected with a code parameter
# 3. Exchange code for token (replace YOUR_CLIENT_ID, YOUR_CLIENT_SECRET, and CODE)
curl -X POST https://github.com/login/oauth/access_token \
  -H "Accept: application/json" \
  -d "client_id=YOUR_CLIENT_ID" \
  -d "client_secret=YOUR_CLIENT_SECRET" \
  -d "code=CODE_FROM_REDIRECT"
```

### 4.2 Test Agent Authentication
Once you have a GitHub access token, test your agent:

```bash
# Replace YOUR_GITHUB_TOKEN with your actual token
TOKEN="your_actual_github_token"

# Test unauthenticated request (should fail)
curl -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"status","id":1}'

# Test authenticated request (should succeed)
curl -X POST http://localhost:8000/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"status","id":1}'
```

### 4.3 Expected Responses

**Unauthenticated (should fail):**
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

**Authenticated (should succeed):**
```json
{
  "jsonrpc": "2.0",
  "result": {
    "status": "ready",
    "timestamp": "2024-01-15T10:30:00Z"
  },
  "id": 1
}
```

## Step 5: Verify Scope Validation

### 5.1 Test Required Scopes
Your agent requires `user` and `user:email` scopes. Test with a token that has different scopes:

```bash
# This should work (token has required scopes)
curl -X POST http://localhost:8000/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"capabilities","id":1}'
```

### 5.2 Test Scope Hierarchy
Test that your scope hierarchy works correctly:

```bash
# Test with user scope (should work for user:email protected endpoints)
curl -X POST http://localhost:8000/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"list_directory","params":{"path":"/tmp"},"id":1}'
```

## How It Works

### 1. Token Validation Process
1. Client sends request with `Authorization: Bearer {github_token}`
2. AgentUp extracts the token from the header
3. AgentUp calls GitHub's token introspection endpoint:
   ```
   POST https://api.github.com/applications/{client_id}/token
   Authorization: Basic {base64(client_id:client_secret)}
   Content-Type: application/json

   {"access_token": "github_token"}
   ```
4. GitHub responds with token validity and user info
5. AgentUp validates required scopes
6. AgentUp grants or denies access

### 2. Scope Validation
- GitHub returns user scopes in the token introspection response
- AgentUp checks if required scopes are present
- Scope hierarchy allows inherited permissions

### 3. Security Features
- Constant-time token comparison
- Comprehensive audit logging
- Rate limiting per authenticated user
- Secure credential handling

## Next Steps
- Test with different GitHub scopes
- Implement proper error handling in your client
- Set up production GitHub OAuth app
- Configure HTTPS for production use

## Troubleshooting
See the troubleshooting guide in the next section for common issues and solutions.