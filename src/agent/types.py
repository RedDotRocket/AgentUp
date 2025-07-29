"""
Core type definitions for AgentUp.

This module provides common type aliases and utility types used throughout
the AgentUp codebase to ensure consistent typing.
"""

from datetime import datetime
from pathlib import Path
from typing import Any

# Common type aliases
UserId = str
ScopeName = str
IPAddress = str
ModulePath = str
FilePath = str | Path
HeaderName = str
QueryParam = str
CookieName = str

# HTTP-related types
Headers = dict[str, str]
QueryParams = dict[str, str | list[str]]
FormData = dict[str, str | list[str]]

# JSON-compatible value type (using Any to avoid recursion)
JsonValue = Any

# Configuration types
ConfigDict = dict[str, Any]
MetadataDict = dict[str, str]
EnvironmentDict = dict[str, str]

# Time-related types
Timestamp = datetime
Duration = float  # seconds
TTL = int  # seconds

# Service types
ServiceName = str
ServiceType = str
ServiceId = str


# Plugin types
PluginId = str
CapabilityId = str
HookName = str

# Security types
Token = str
Hash = str
Salt = str
Signature = str

# MCP types
MCPServerName = str
MCPToolName = str
MCPResourceId = str

# API types
RequestId = str
TaskId = str
SessionId = str
CorrelationId = str

# Error types
ErrorCode = str
ErrorMessage = str

# Version type
Version = str

# URL types
URL = str
WebSocketURL = str

# File content types
FileContent = str | bytes
MimeType = str

# Logging types
LogLevel = str
LoggerName = str

# Database types (for future use)
TableName = str
ColumnName = str
PrimaryKey = str | int


# Common constants as types
class HttpMethod:
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


class ContentType:
    JSON = "application/json"
    XML = "application/xml"
    TEXT = "text/plain"
    HTML = "text/html"
    FORM = "application/x-www-form-urlencoded"
    MULTIPART = "multipart/form-data"
    BINARY = "application/octet-stream"


class AuthScheme:
    BEARER = "Bearer"
    BASIC = "Basic"
    API_KEY = "ApiKey"
    OAUTH2 = "OAuth2"


# Re-export commonly used types
__all__ = [
    # Core JSON type
    "JsonValue",
    # Identity types
    "UserId",
    "ScopeName",
    "IPAddress",
    "ModulePath",
    "FilePath",
    # HTTP types
    "HeaderName",
    "QueryParam",
    "CookieName",
    "Headers",
    "QueryParams",
    "FormData",
    # Configuration types
    "ConfigDict",
    "MetadataDict",
    "EnvironmentDict",
    # Time types
    "Timestamp",
    "Duration",
    "TTL",
    # Service types
    "ServiceName",
    "ServiceType",
    "ServiceId",
    # Plugin types
    "PluginId",
    "CapabilityId",
    "HookName",
    # Security types
    "Token",
    "Hash",
    "Salt",
    "Signature",
    # MCP types
    "MCPServerName",
    "MCPToolName",
    "MCPResourceId",
    # API types
    "RequestId",
    "TaskId",
    "SessionId",
    "CorrelationId",
    # Error types
    "ErrorCode",
    "ErrorMessage",
    # Other types
    "Version",
    "URL",
    "WebSocketURL",
    "FileContent",
    "MimeType",
    "LogLevel",
    "LoggerName",
    "TableName",
    "ColumnName",
    "PrimaryKey",
    # Constants
    "HttpMethod",
    "ContentType",
    "AuthScheme",
]
