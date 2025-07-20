# GitHub OAuth2 Test Agent

This directory contains a complete example of setting up GitHub OAuth2 authentication with AgentUp.

## Quick Start

1. **Set up GitHub OAuth App** (follow the main guide)
2. **Set environment variables:**
   ```bash
   export GITHUB_CLIENT_ID="your_client_id"
   export GITHUB_CLIENT_SECRET="your_client_secret"
   ```
3. **Start the agent:**
   ```bash
   cd examples/oauth2_github_agent
   agentup agent serve
   ```
4. **Run the test script:**
   ```bash
   ./test_oauth2.sh
   ```

## Files

- `agentup.yml` - Complete agent configuration with GitHub OAuth2
- `test_oauth2.sh` - Interactive test script for OAuth2 flow
- `README.md` - This file

## Test Script Features

The test script will:
- Check if your agent is running
- Test unauthenticated requests (should fail)
- Help you get a GitHub token (multiple methods)
- Validate the token with GitHub
- Test authenticated requests
- Verify OAuth2 is working correctly

## Manual Testing

### Get GitHub Token
```bash
# Option 1: GitHub CLI
gh auth login --scopes "user,user:email"
export GITHUB_TOKEN=$(gh auth token)

# Option 2: Personal Access Token
# Go to https://github.com/settings/tokens
# Create token with scopes: user, user:email
```

### Test Requests
```bash
# Unauthenticated (should fail)
curl -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"status","id":1}'

# Authenticated (should succeed)
curl -X POST http://localhost:8000/ \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"status","id":1}'
```

## Configuration Notes

- **Validation Strategy**: Uses "introspection" because GitHub tokens are opaque
- **Required Scopes**: Configured for "user" and "user:email"
- **Scope Hierarchy**: Admin > user > user:email permissions
- **Rate Limiting**: Configured for 60 requests per minute

## Troubleshooting

See the main troubleshooting guide in `docs/github_oauth2_setup.md`.