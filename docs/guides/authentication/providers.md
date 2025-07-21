# OAuth2 Provider Integration Guide

**Step-by-step setup for popular OAuth2 providers**

This guide provides complete setup instructions for integrating AgentUp with popular OAuth2 providers. Each section includes provider-specific configuration, setup steps, and testing instructions.

## Table of Contents

- [Google OAuth2](#google-oauth2)
- [Auth0](#auth0)
- [Microsoft Azure AD](#microsoft-azure-ad)
- [AWS Cognito](#aws-cognito)
- [GitHub Apps](#github-apps)
- [Okta](#okta)
- [Custom Provider](#custom-provider)

## Google OAuth2

### Use Cases
- Google Workspace integration
- Gmail and Calendar access
- Google Cloud Platform authentication
- Service account authentication

### Setup Steps

#### 1. Create Google OAuth2 Application

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable the APIs you need (e.g., Gmail API, Calendar API)
4. Go to "Credentials" → "Create Credentials" → "OAuth 2.0 Client IDs"
5. Configure consent screen with your application details
6. Note your Client ID for audience configuration

#### 2. AgentUp Configuration

```yaml
security:
  enabled: true
  type: "oauth2"
  oauth2:
    validation_strategy: "jwt"
    jwks_url: "https://www.googleapis.com/oauth2/v3/certs"
    jwt_algorithm: "RS256"
    jwt_issuer: "https://accounts.google.com"
    jwt_audience: "YOUR_CLIENT_ID.apps.googleusercontent.com"
    required_scopes: ["openid", "email", "profile"]
```

#### 3. Getting Access Tokens

**For testing**, use Google's OAuth2 Playground:
1. Go to [OAuth2 Playground](https://developers.google.com/oauthplayground/)
2. Configure to use your own OAuth credentials
3. Authorize scopes: `openid email profile`
4. Exchange authorization code for tokens

**For applications**, implement OAuth2 flow:
```python
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow

# Configure OAuth2 flow
flow = Flow.from_client_config(
    client_config={
        "web": {
            "client_id": "YOUR_CLIENT_ID",
            "client_secret": "YOUR_CLIENT_SECRET",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    },
    scopes=["openid", "email", "profile"]
)
```

#### 4. Testing

```bash
# Test with Google access token
curl -H "Authorization: Bearer ya29.a0AfH6SMC..." \
     http://localhost:8000/agent/card
```

### Service Account Alternative

For server-to-server authentication:

```yaml
security:
  enabled: true
  type: "oauth2"
  oauth2:
    validation_strategy: "jwt"
    jwt_secret: "${GOOGLE_SERVICE_ACCOUNT_KEY}"  # Base64 encoded key
    jwt_algorithm: "RS256"
    jwt_issuer: "https://accounts.google.com"
    jwt_audience: "your-service-account@project.iam.gserviceaccount.com"
```

---

## Auth0

### Use Cases
- Universal login
- Multi-tenant SaaS applications
- Social login integration
- Enterprise SSO

### Setup Steps

#### 1. Create Auth0 Application

1. Log in to [Auth0 Dashboard](https://manage.auth0.com/)
2. Go to Applications → Create Application
3. Choose "Machine to Machine Applications" for API access
4. Select your API (create one if needed)
5. Configure scopes and permissions

#### 2. Configure API in Auth0

1. Go to APIs → Create API
2. Set Identifier (this becomes your audience)
3. Define scopes (e.g., `read:agents`, `write:agents`, `admin:agents`)
4. Configure JWT settings

#### 3. AgentUp Configuration

```yaml
security:
  enabled: true
  type: "oauth2"
  oauth2:
    validation_strategy: "jwt"
    jwks_url: "https://YOUR_DOMAIN.auth0.com/.well-known/jwks.json"
    jwt_algorithm: "RS256"
    jwt_issuer: "https://YOUR_DOMAIN.auth0.com/"
    jwt_audience: "https://your-api-identifier"
    required_scopes: ["read:agents"]
    allowed_scopes: ["read:agents", "write:agents", "admin:agents"]
```

#### 4. Getting Access Tokens

**For testing**, use Auth0's Test tab:
1. Go to Applications → Your App → Test
2. Copy the curl command with access token

**For applications**, use Auth0 SDKs:
```javascript
// Node.js example
const { AuthenticationClient } = require('auth0');

const auth0 = new AuthenticationClient({
  domain: 'YOUR_DOMAIN.auth0.com',
  clientId: 'YOUR_CLIENT_ID',
  clientSecret: 'YOUR_CLIENT_SECRET'
});

// Get token using client credentials flow
const token = await auth0.clientCredentialsGrant({
  audience: 'https://your-api-identifier',
  scope: 'read:agents write:agents'
});
```

#### 5. Testing

```bash
# Test with Auth0 access token
curl -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIs..." \
     http://localhost:8000/agent/card
```

### Custom Claims

Add custom claims to Auth0 tokens:

1. Go to Auth0 Dashboard → Rules
2. Create a new rule:
```javascript
function addCustomClaims(user, context, callback) {
  const namespace = 'https://agentup.com/';
  context.accessToken[namespace + 'user_id'] = user.user_id;
  context.accessToken[namespace + 'roles'] = user.app_metadata?.roles || [];
  callback(null, user, context);
}
```

---

## Microsoft Azure AD

### Use Cases
- Microsoft 365 integration
- Enterprise Active Directory
- Azure services authentication
- Office 365 APIs

### Setup Steps

#### 1. Register Application in Azure AD

1. Go to [Azure Portal](https://portal.azure.com/)
2. Navigate to Azure Active Directory → App registrations
3. Click "New registration"
4. Configure application details and redirect URIs
5. Note the Application (client) ID and Directory (tenant) ID

#### 2. Configure API Permissions

1. Go to API permissions → Add a permission
2. Add Microsoft Graph or custom API permissions
3. Grant admin consent for the permissions

#### 3. Create Client Secret

1. Go to Certificates & secrets → Client secrets
2. Create a new client secret
3. Copy the secret value immediately

#### 4. AgentUp Configuration

```yaml
security:
  enabled: true
  type: "oauth2"
  oauth2:
    validation_strategy: "jwt"
    jwks_url: "https://login.microsoftonline.com/TENANT_ID/discovery/v2.0/keys"
    jwt_algorithm: "RS256"
    jwt_issuer: "https://login.microsoftonline.com/TENANT_ID/v2.0"
    jwt_audience: "YOUR_CLIENT_ID"
    required_scopes: ["api://YOUR_CLIENT_ID/Agent.Read"]
```

#### 5. Getting Access Tokens

**Using Azure CLI**:
```bash
# Login and get token
az login
az account get-access-token --resource "YOUR_CLIENT_ID"
```

**Using MSAL (Microsoft Authentication Library)**:
```python
from msal import ConfidentialClientApplication

app = ConfidentialClientApplication(
    client_id="YOUR_CLIENT_ID",
    client_credential="YOUR_CLIENT_SECRET",
    authority="https://login.microsoftonline.com/TENANT_ID"
)

# Get token using client credentials flow
result = app.acquire_token_for_client(scopes=["api://YOUR_CLIENT_ID/.default"])
access_token = result["access_token"]
```

#### 6. Testing

```bash
# Test with Azure AD access token
curl -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiIs..." \
     http://localhost:8000/agent/card
```

---

## AWS Cognito

### Use Cases
- AWS service integration
- Serverless applications
- Mobile app authentication
- User pool management

### Setup Steps

#### 1. Create Cognito User Pool

1. Go to [AWS Cognito Console](https://console.aws.amazon.com/cognito/)
2. Create a new User Pool
3. Configure authentication attributes and policies
4. Create an App Client for your application

#### 2. Configure App Client

1. Go to App clients → Create app client
2. Disable "Generate client secret" for public clients
3. Configure OAuth2 flows and scopes
4. Note the App client id

#### 3. AgentUp Configuration

```yaml
security:
  enabled: true
  type: "oauth2"
  oauth2:
    validation_strategy: "jwt"
    jwks_url: "https://cognito-idp.REGION.amazonaws.com/USER_POOL_ID/.well-known/jwks.json"
    jwt_algorithm: "RS256"
    jwt_issuer: "https://cognito-idp.REGION.amazonaws.com/USER_POOL_ID"
    jwt_audience: "YOUR_APP_CLIENT_ID"
    required_scopes: ["openid", "email"]
```

#### 4. Getting Access Tokens

**Using AWS SDK**:
```python
import boto3

client = boto3.client('cognito-idp', region_name='us-east-1')

# Authenticate user
response = client.admin_initiate_auth(
    UserPoolId='USER_POOL_ID',
    ClientId='APP_CLIENT_ID',
    AuthFlow='ADMIN_NO_SRP_AUTH',
    AuthParameters={
        'USERNAME': 'user@example.com',
        'PASSWORD': 'password'
    }
)

access_token = response['AuthenticationResult']['AccessToken']
```

---

## GitHub Apps

### Use Cases
- GitHub API integration
- Repository access
- CI/CD automation
- Code analysis tools

### Setup Steps

#### 1. Create GitHub App

1. Go to GitHub Settings → Developer settings → GitHub Apps
2. Click "New GitHub App"
3. Configure app details and permissions
4. Generate a private key for JWT authentication

#### 2. Install App

1. Install the app on your organization/repositories
2. Note the Installation ID

#### 3. AgentUp Configuration

GitHub uses custom token validation, so we use introspection:

```yaml
security:
  enabled: true
  type: "oauth2"
  oauth2:
    validation_strategy: "introspection"
    client_id: "${GITHUB_CLIENT_ID}"
    client_secret: "${GITHUB_CLIENT_SECRET}"
    introspection_endpoint: "https://api.github.com/applications/${GITHUB_CLIENT_ID}/token"
```

#### 4. Getting Access Tokens

**Installation Access Token**:
```python
import jwt
import time
import requests

# Generate JWT for app authentication
def generate_jwt(app_id, private_key):
    payload = {
        'iat': int(time.time()),
        'exp': int(time.time()) + 600,  # 10 minutes
        'iss': app_id
    }
    return jwt.encode(payload, private_key, algorithm='RS256')

# Get installation access token
def get_installation_token(app_id, private_key, installation_id):
    jwt_token = generate_jwt(app_id, private_key)
    
    response = requests.post(
        f'https://api.github.com/app/installations/{installation_id}/access_tokens',
        headers={
            'Authorization': f'Bearer {jwt_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
    )
    
    return response.json()['token']
```

---

## Okta

### Use Cases
- Enterprise identity management
- SSO integration
- API access management
- Workforce authentication

### Setup Steps

#### 1. Create Okta Application

1. Log in to Okta Admin Console
2. Go to Applications → Create App Integration
3. Choose "API Services" for machine-to-machine
4. Configure application settings

#### 2. Configure Authorization Server

1. Go to Security → API → Authorization Servers
2. Create or configure an authorization server
3. Define scopes and claims
4. Configure access policies

#### 3. AgentUp Configuration

```yaml
security:
  enabled: true
  type: "oauth2"
  oauth2:
    validation_strategy: "jwt"
    jwks_url: "https://YOUR_DOMAIN.okta.com/oauth2/default/v1/keys"
    jwt_algorithm: "RS256"
    jwt_issuer: "https://YOUR_DOMAIN.okta.com/oauth2/default"
    jwt_audience: "api://default"
    required_scopes: ["agent:access"]
```

#### 4. Getting Access Tokens

**Using Okta SDK**:
```python
import okta

config = {
    'orgUrl': 'https://YOUR_DOMAIN.okta.com',
    'clientId': 'YOUR_CLIENT_ID',
    'clientSecret': 'YOUR_CLIENT_SECRET',
    'scopes': ['agent:access']
}

client = okta.Client(config)
token = client.get_access_token()
```

---

## Custom Provider

### Use Cases
- Internal OAuth2 server
- Custom authentication requirements
- Legacy system integration
- Specialized security needs

### Requirements

Your OAuth2 provider must support:
- JWT token issuance (for JWT validation)
- Token introspection endpoint (RFC 7662)
- JWKS endpoint (for JWT validation)

### Setup Steps

#### 1. Gather Provider Information

- Authorization endpoint
- Token endpoint  
- JWKS endpoint (for JWT validation)
- Introspection endpoint (for token introspection)
- Issuer identifier
- Supported algorithms

#### 2. AgentUp Configuration

**JWT Validation**:
```yaml
security:
  enabled: true
  type: "oauth2"
  oauth2:
    validation_strategy: "jwt"
    jwks_url: "https://your-provider.com/.well-known/jwks.json"
    jwt_algorithm: "RS256"  # Match your provider
    jwt_issuer: "https://your-provider.com"
    jwt_audience: "your-agent-identifier"
    required_scopes: ["agent:access"]
```

**Token Introspection**:
```yaml
security:
  enabled: true
  type: "oauth2"
  oauth2:
    validation_strategy: "introspection"
    client_id: "${OAUTH_CLIENT_ID}"
    client_secret: "${OAUTH_CLIENT_SECRET}"
    introspection_endpoint: "https://your-provider.com/oauth/introspect"
    required_scopes: ["api:access"]
```

#### 3. Testing Provider Compatibility

Test JWKS endpoint:
```bash
curl https://your-provider.com/.well-known/jwks.json
```

Test introspection endpoint:
```bash
curl -u "client_id:client_secret" \
     -d "token=YOUR_TOKEN" \
     https://your-provider.com/oauth/introspect
```

### Provider Implementation Guidelines

If you're implementing a custom OAuth2 provider:

#### JWT Token Requirements
- Include standard claims: `iss`, `aud`, `exp`, `iat`, `sub`
- Use `scope` claim for space-separated scopes
- Support RS256 algorithm (recommended)
- Provide JWKS endpoint with proper key rotation

#### Introspection Endpoint Requirements
- Follow RFC 7662 specification
- Return `active` boolean field
- Include `scope`, `client_id`, `username` fields
- Support client authentication via Basic auth or client credentials

## Testing and Validation

### Universal Testing Script

```bash
#!/bin/bash
# test-oauth2.sh - Test OAuth2 integration

AGENT_URL="http://localhost:8000"
ACCESS_TOKEN="$1"

if [ -z "$ACCESS_TOKEN" ]; then
    echo "Usage: $0 <access_token>"
    exit 1
fi

echo "Testing OAuth2 authentication..."

# Test 1: Discovery endpoint (should work without auth)
echo "1. Testing discovery endpoint..."
curl -s "${AGENT_URL}/.well-known/agent.json" | jq -r '.securitySchemes.OAuth2.description'

# Test 2: Protected endpoint without token (should fail)
echo "2. Testing protected endpoint without token..."
curl -s -w "%{http_code}" "${AGENT_URL}/agent/card" | tail -1

# Test 3: Protected endpoint with token (should work)
echo "3. Testing protected endpoint with token..."
curl -s -w "%{http_code}" \
     -H "Authorization: Bearer ${ACCESS_TOKEN}" \
     "${AGENT_URL}/agent/card" | tail -1

echo "OAuth2 testing complete!"
```

### Debugging Tools

**Decode JWT Token**:
```bash
# Install jq for JSON parsing
echo "YOUR_JWT_TOKEN" | cut -d. -f2 | base64 -d | jq .
```

**Validate JWKS**:
```bash
curl -s "https://your-provider.com/.well-known/jwks.json" | jq .
```

**Test Introspection**:
```bash
curl -u "client_id:secret" \
     -d "token=YOUR_TOKEN" \
     https://provider.com/oauth/introspect | jq .
```

## Next Steps

- **[OAuth2 Configuration Reference](oauth2.md#configuration-options)**
- **[Authentication Troubleshooting](../troubleshooting/authentication.md)**
- **[Production Deployment Guide](../examples/enterprise-agent.md)**
- **[Custom Authentication Development](../reference/custom-auth.md)**

---

**Quick Links:**
- 🔙 [OAuth2 Guide](oauth2.md)
- 🏠 [Documentation Home](../index.md)
- 🛠️ [Configuration Reference](../reference/config-schema.md)