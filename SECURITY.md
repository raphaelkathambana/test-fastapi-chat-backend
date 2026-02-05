# Security Policy

## Overview

This document outlines the security measures implemented in the FastAPI Chat Backend and provides guidance for maintaining security in production deployments.

## Security Improvements (v2.0)

This version includes comprehensive security hardening:

### ✅ Fixed Critical Vulnerabilities

1. **CORS Wildcard Removed**
   - **Issue**: `allow_origins=["*"]` allowed any website to make requests
   - **Fix**: Configurable CORS origins via environment variable
   - **Configuration**: Set `CORS_ORIGINS` in `.env` file

2. **No Default Secrets**
   - **Issue**: Hardcoded default values for SECRET_KEY and ENCRYPTION_KEY
   - **Fix**: Application requires `.env` file with strong random keys
   - **Impact**: Prevents running with known/weak encryption keys

3. **Secure Docker Configuration**
   - **Issue**: Hardcoded PostgreSQL credentials in docker-compose.yml
   - **Fix**: Credentials loaded from environment variables
   - **Configuration**: DATABASE_USER, DATABASE_PASSWORD, DATABASE_NAME

4. **Header-Based Authentication**
   - **Issue**: JWT tokens passed in query strings (logged in server logs)
   - **Fix**: Authorization header with Bearer token for REST API
   - **Note**: WebSocket still uses query param (browser limitation)

### 🛡️ Added Security Features

5. **Rate Limiting**
   - **Registration**: 5 attempts per minute per IP
   - **Login**: 10 attempts per minute per IP
   - **Prevents**: Brute force attacks, account enumeration

6. **Password Complexity Requirements**
   - Minimum 8 characters
   - At least one uppercase letter
   - At least one lowercase letter
   - At least one digit
   - Maximum 128 characters

7. **Username Validation**
   - 3-50 characters
   - Alphanumeric characters, underscores, and hyphens only
   - Prevents: SQL injection attempts, special character exploits

8. **Separated Database Credentials**
   - **Issue**: Password visible in DATABASE_URL string
   - **Fix**: Separate environment variables for host, user, password
   - **Benefit**: Easier credential rotation, better secret management

## Security Architecture

### Authentication Flow

```
1. User submits credentials → POST /api/auth/login
2. Rate limiter checks request frequency
3. Password validated against bcrypt hash
4. JWT token generated with 30-minute expiration
5. Token returned to client
6. Client includes token in Authorization header
7. Server validates token on each request
```

### Encryption Layers

1. **Passwords**: bcrypt (12 rounds)
2. **JWT Tokens**: HMAC-SHA256
3. **Messages**: Fernet (AES-128-CBC + HMAC-SHA256)

### Network Security

- **CORS**: Restricted to configured origins
- **HTTPS**: Recommended for production
- **Headers**: Proper security headers should be added (CSP, HSTS, etc.)

## Configuration Best Practices

### Required Environment Variables

```env
# Database (separate credentials)
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=chatdb
DATABASE_USER=postgres
DATABASE_PASSWORD=<strong-random-password>

# Cryptographic keys (REQUIRED)
SECRET_KEY=<hex-string-64-chars>
ENCRYPTION_KEY=<fernet-key-44-chars>

# CORS (comma-separated, no spaces)
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

### Generating Secure Keys

**SECRET_KEY** (for JWT signing):
```bash
openssl rand -hex 32
```

**ENCRYPTION_KEY** (for message encryption):
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Key Rotation

If you need to rotate encryption keys:

1. **SECRET_KEY**: Generate new key, restart application
   - Existing JWT tokens will become invalid
   - Users need to re-login

2. **ENCRYPTION_KEY**: Requires data migration
   - Decrypt existing messages with old key
   - Re-encrypt with new key
   - Not supported out-of-box (requires custom migration)

## Production Deployment Checklist

### Critical (Must Do)

- [ ] Generate strong random SECRET_KEY
- [ ] Generate strong random ENCRYPTION_KEY
- [ ] Configure CORS_ORIGINS for your domain only
- [ ] Use managed PostgreSQL database (not Docker)
- [ ] Enable HTTPS with valid SSL certificate
- [ ] Set strong DATABASE_PASSWORD
- [ ] Never commit .env file to version control
- [ ] Run behind reverse proxy (nginx/traefik)

### Recommended (Should Do)

- [ ] Implement structured logging
- [ ] Set up monitoring and alerting
- [ ] Add health check for database connectivity
- [ ] Implement session management with refresh tokens
- [ ] Add account lockout after failed login attempts
- [ ] Implement email verification for new accounts
- [ ] Add password reset via email
- [ ] Set up automated database backups
- [ ] Implement audit logging for sensitive operations
- [ ] Add WebSocket connection limits per user

### Optional (Nice to Have)

- [ ] Add 2FA/MFA support
- [ ] Implement IP whitelisting for admin operations
- [ ] Add user session management (view/revoke sessions)
- [ ] Implement message retention policies
- [ ] Add content filtering/moderation
- [ ] Implement user blocking/reporting
- [ ] Add API versioning
- [ ] Set up WAF (Web Application Firewall)

## Known Limitations

### 1. WebSocket Authentication
- **Issue**: Token still passed in query string
- **Reason**: Browser WebSocket API doesn't support custom headers
- **Mitigation**: Use short-lived tokens, monitor logs for token exposure

### 2. No Refresh Tokens
- **Issue**: Users must re-login every 30 minutes
- **Impact**: Poor UX for long sessions
- **Recommendation**: Implement refresh token mechanism

### 3. No Rate Limiting on WebSocket
- **Issue**: WebSocket connections not rate-limited
- **Impact**: Potential for connection exhaustion
- **Recommendation**: Add connection limits per user/IP

### 4. No Message History Pagination
- **Issue**: GET /api/chat/messages returns all messages up to limit
- **Impact**: Performance issues with large message volumes
- **Recommendation**: Implement cursor-based pagination

### 5. Encryption Key Rotation
- **Issue**: No built-in support for key rotation
- **Impact**: Cannot easily change ENCRYPTION_KEY
- **Recommendation**: Implement key versioning and migration script

## Incident Response

If you suspect a security breach:

1. **Immediate Actions**:
   - Rotate SECRET_KEY immediately (invalidates all sessions)
   - Rotate DATABASE_PASSWORD
   - Check logs for suspicious activity
   - Notify affected users

2. **Investigation**:
   - Review access logs
   - Check for unauthorized database access
   - Verify no data exfiltration occurred
   - Document timeline of events

3. **Remediation**:
   - Apply security patches
   - Update affected dependencies
   - Review and update security policies
   - Conduct security audit

## Reporting Security Issues

If you discover a security vulnerability, please:

1. **DO NOT** open a public issue
2. Email security details to: [your-security-email]
3. Include:
   - Description of vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

We aim to respond within 48 hours.

## Compliance Notes

### Data Protection

- **Encryption at Rest**: All messages encrypted with Fernet
- **Encryption in Transit**: HTTPS required (production)
- **Password Storage**: bcrypt hashing (industry standard)

### GDPR Considerations

If handling EU user data:
- Implement right to data export
- Implement right to deletion
- Add consent management
- Maintain data processing records
- Implement breach notification

### OWASP Top 10 Coverage

✅ A01: Broken Access Control - JWT authentication, rate limiting
✅ A02: Cryptographic Failures - Fernet encryption, bcrypt hashing
✅ A03: Injection - SQLAlchemy ORM, input validation
⚠️ A04: Insecure Design - Basic security, needs enhancements
✅ A05: Security Misconfiguration - No defaults, required .env
⚠️ A06: Vulnerable Components - Regular updates needed
⚠️ A07: Identification/Auth Failures - Basic auth, needs MFA
⚠️ A08: Software/Data Integrity - No signing, needs checksums
⚠️ A09: Logging/Monitoring - Basic logging, needs enhancement
⚠️ A10: SSRF - Not applicable (no user-provided URLs)

## Security Audit History

- **v2.0** (2026-02-05): Comprehensive security hardening
  - Fixed CORS wildcard
  - Removed hardcoded secrets
  - Added rate limiting
  - Added input validation
  - Separated database credentials
  - Moved tokens to headers

- **v1.0** (Initial): Basic security implementation
  - JWT authentication
  - bcrypt password hashing
  - Message encryption

## References

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [FastAPI Security Best Practices](https://fastapi.tiangolo.com/tutorial/security/)
- [SQLAlchemy Security](https://docs.sqlalchemy.org/en/20/faq/security.html)
- [Cryptography Documentation](https://cryptography.io/)
