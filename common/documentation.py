"""
API Documentation utilities and enhanced OpenAPI configuration
"""
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from typing import Dict, Any

def create_custom_openapi(app: FastAPI, title: str, version: str, description: str) -> Dict[str, Any]:
    """Create enhanced OpenAPI schema with detailed documentation"""
    
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title=title,
        version=version,
        description=description,
        routes=app.routes,
    )
    
    # Add custom info
    openapi_schema["info"]["x-logo"] = {
        "url": "https://fastapi.tiangolo.com/img/logo-margin/logo-teal.png"
    }
    
    # Add authentication info
    openapi_schema["components"]["securitySchemes"] = {
        "bearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "JWT Bearer token for authentication"
        }
    }
    
    # Add common response schemas
    openapi_schema["components"]["schemas"]["ErrorResponse"] = {
        "type": "object",
        "required": ["success", "error", "timestamp"],
        "properties": {
            "success": {
                "type": "boolean",
                "example": False,
                "description": "Always false for error responses"
            },
            "error": {
                "type": "object",
                "required": ["code", "message"],
                "properties": {
                    "code": {
                        "type": "string",
                        "example": "VALIDATION_ERROR",
                        "description": "Standardized error code"
                    },
                    "message": {
                        "type": "string",
                        "example": "Invalid input provided",
                        "description": "Human-readable error message"
                    },
                    "field": {
                        "type": "string",
                        "example": "amount",
                        "description": "Field that caused the error (optional)"
                    },
                    "context": {
                        "type": "object",
                        "description": "Additional error context (optional)"
                    }
                }
            },
            "timestamp": {
                "type": "number",
                "example": 1699123456.789,
                "description": "Unix timestamp when error occurred"
            },
            "trace_id": {
                "type": "string",
                "example": "abc123def456",
                "description": "Trace ID for debugging (optional)"
            }
        }
    }
    
    # Add standard HTTP responses
    standard_responses = {
        "400": {
            "description": "Bad Request",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                }
            }
        },
        "401": {
            "description": "Unauthorized",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                }
            }
        },
        "403": {
            "description": "Forbidden",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                }
            }
        },
        "404": {
            "description": "Not Found",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                }
            }
        },
        "429": {
            "description": "Rate Limit Exceeded",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                }
            }
        },
        "500": {
            "description": "Internal Server Error",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                }
            }
        }
    }
    
    # Add standard responses to all paths
    for path_item in openapi_schema["paths"].values():
        for operation in path_item.values():
            if isinstance(operation, dict) and "responses" in operation:
                operation["responses"].update(standard_responses)
    
    # Add tags
    openapi_schema["tags"] = [
        {
            "name": "Authentication",
            "description": "User authentication and authorization"
        },
        {
            "name": "Accounts",
            "description": "Account management operations"
        },
        {
            "name": "Transfers",
            "description": "Money transfer operations"
        },
        {
            "name": "Analytics",
            "description": "System analytics and statistics"
        },
        {
            "name": "Health",
            "description": "System health and monitoring"
        },
        {
            "name": "Administration",
            "description": "Administrative operations"
        }
    ]
    
    # Add servers
    openapi_schema["servers"] = [
        {
            "url": "http://localhost:8006",
            "description": "Local development server"
        },
        {
            "url": "https://api.paytm-style.com",
            "description": "Production server"
        }
    ]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

# Documentation strings for common operations
TRANSFER_DOCS = """
## Transfer Funds

Transfer money between users across shards with full ACID guarantees.

### Features
- **Cross-shard support**: Transfer between users on different database shards
- **ACID transactions**: Ensures data consistency across all operations
- **Rate limiting**: Prevents abuse with configurable limits
- **Fraud detection**: Real-time fraud scoring and blocking
- **Audit trail**: Complete transaction history and logging

### Authentication
Requires JWT Bearer token. Users can only transfer from their own accounts.

### Rate Limits
- 10 transfers per minute per user
- Higher limits available for verified merchants

### Error Handling
Returns standardized error responses with detailed error codes for different failure scenarios.
"""

ACCOUNT_DOCS = """
## Account Management

Create and manage user accounts across database shards.

### Features
- **Automatic sharding**: Accounts distributed across multiple database shards
- **Balance caching**: Redis caching for improved performance
- **Real-time updates**: Balance updates propagated immediately

### Security
- JWT authentication required for account operations
- Users can only access their own account data
- Audit logging for all account modifications
"""

AUTH_DOCS = """
## Authentication System

JWT-based authentication with role-based access control.

### Token Format
```
Authorization: Bearer <JWT_TOKEN>
```

### Token Claims
- `sub`: User ID
- `scope`: User permissions
- `iat`: Issued at timestamp
- `exp`: Expiration timestamp

### Security Features
- Token expiration and refresh
- Rate limiting on authentication endpoints
- Audit logging for security events
"""