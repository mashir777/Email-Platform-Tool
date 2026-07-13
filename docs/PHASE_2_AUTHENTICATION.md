# Phase 2 — Authentication API

Base URL: `/api/v1/auth/`

All successful responses follow:

```json
{
  "success": true,
  "message": "Optional message",
  "data": {}
}
```

Error responses follow:

```json
{
  "success": false,
  "errors": {}
}
```

## Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/register/` | No | Register a new user (role: Client) |
| POST | `/login/` | No | Login with email and password |
| POST | `/logout/` | Yes | Blacklist refresh token |
| POST | `/token/refresh/` | No | Refresh JWT access token |
| POST | `/password/forgot/` | No | Request password reset email |
| POST | `/password/reset/` | No | Reset password with token |
| POST | `/password/change/` | Yes + Verified | Change password |
| POST | `/email/verify/` | No | Verify email with token |
| POST | `/email/resend/` | Yes | Resend verification email |
| GET | `/profile/` | Yes | Get current user profile |
| PATCH | `/profile/` | Yes | Update profile fields |
| POST | `/profile/avatar/` | Yes + Verified | Upload avatar |
| DELETE | `/profile/avatar/` | Yes + Verified | Remove avatar |
| GET | `/roles/` | Yes | List available user roles |

## User Roles

| Role | Value | Description |
|------|-------|-------------|
| Super Admin | `super_admin` | Full platform access |
| Admin | `admin` | Administrative access |
| Manager | `manager` | Team/campaign management |
| Client | `client` | Default role for new registrations |

## Authentication

Include the JWT access token in requests:

```
Authorization: Bearer <access_token>
```

## Interactive Documentation

- Swagger UI: `/api/docs/`
- ReDoc: `/api/redoc/`
- OpenAPI Schema: `/api/schema/`

## Example: Register

```bash
curl -X POST http://localhost:8000/api/v1/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePass123!",
    "password_confirm": "SecurePass123!",
    "first_name": "Jane",
    "last_name": "Doe"
  }'
```

## Example: Login

```bash
curl -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "SecurePass123!"}'
```

## Example: Refresh Token

```bash
curl -X POST http://localhost:8000/api/v1/auth/token/refresh/ \
  -H "Content-Type: application/json" \
  -d '{"refresh": "<refresh_token>"}'
```

## Example: Logout

```bash
curl -X POST http://localhost:8000/api/v1/auth/logout/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"refresh": "<refresh_token>"}'
```

## Example: Update Profile

```bash
curl -X PATCH http://localhost:8000/api/v1/auth/profile/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"first_name": "Jane", "company_name": "Acme Inc"}'
```

## Example: Upload Avatar

```bash
curl -X POST http://localhost:8000/api/v1/auth/profile/avatar/ \
  -H "Authorization: Bearer <access_token>" \
  -F "avatar=@/path/to/avatar.png"
```

## Rate Limits

| Scope | Limit |
|-------|-------|
| register | 10/hour |
| login | 20/hour |
| token_refresh | 30/hour |
| password_reset | 5/hour |
| email_verify | 10/hour |
