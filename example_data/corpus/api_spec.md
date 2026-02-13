# API Specification

## Authentication Endpoints

### POST /api/auth/login
Authenticate user with email and password.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "secure_password"
}
```

**Response:**
```json
{
  "token": "jwt_token_here",
  "user_id": "user_123",
  "expires_in": 3600
}
```

## User Management Endpoints

### GET /api/users/{user_id}
Retrieve user profile information.

**Response:**
```json
{
  "user_id": "user_123",
  "email": "user@example.com",
  "name": "John Doe",
  "created_at": "2024-01-01T00:00:00Z"
}
```

### POST /api/users/{user_id}/export
Request user data export.

**Query Parameters:**
- format: csv, json

**Response:**
```json
{
  "export_id": "export_456",
  "status": "processing",
  "estimated_time": 300
}
```
