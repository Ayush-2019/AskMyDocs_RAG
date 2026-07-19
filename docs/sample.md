# Acme Platform Documentation

Welcome to the Acme Platform documentation. This guide covers setup, authentication, configuration, and troubleshooting.

## Getting Started

### System Requirements

Acme Platform requires the following to run:

- Python 3.11 or higher
- PostgreSQL 15+ with the pgvector extension
- At least 4 GB of RAM for the ML models
- Docker and Docker Compose for local development

### Installation

Clone the repository and install dependencies:

```bash
git clone https://github.com/acme/platform.git
cd platform
pip install -r requirements.txt
```

Then start the infrastructure services:

```bash
docker-compose up -d
python scripts/setup_db.py
```

## Authentication

### OAuth2 Configuration

Acme Platform uses OAuth2 with PKCE for secure authentication. To configure OAuth2, edit the `auth.yaml` configuration file.

To enable refresh token rotation, set `oauth2.refresh.rotation=true` in `auth.yaml`. The default refresh token lifetime is 7 days, configurable via `oauth2.refresh.lifetime_days`. Rotation ensures that each refresh token can only be used once, improving security against token theft.

### API Key Authentication

For machine-to-machine communication, Acme supports API key authentication. API keys are scoped to specific permissions and can be created in the Admin Dashboard under Settings > API Keys.

API keys must be passed in the `X-API-Key` header. Keys are rate-limited to 1000 requests per minute by default. To adjust the rate limit, set `api_keys.rate_limit_rpm` in `config.yaml`.

### Single Sign-On (SSO)

Enterprise customers can configure SAML 2.0 SSO. Contact support@acme.com to enable SSO for your organization. SSO supports IdP-initiated and SP-initiated flows. Supported identity providers include Okta, Azure AD, and OneLogin.

## Configuration

### Environment Variables

The following environment variables control the platform behavior:

- `ACME_DATABASE_URL` — PostgreSQL connection string (required)
- `ACME_REDIS_URL` — Redis connection string for caching (optional, defaults to localhost:6379)
- `ACME_SECRET_KEY` — 256-bit secret key for session encryption (required)
- `ACME_LOG_LEVEL` — Logging verbosity: DEBUG, INFO, WARNING, ERROR (default: INFO)
- `ACME_MAX_UPLOAD_MB` — Maximum file upload size in megabytes (default: 50)

### Database Configuration

Acme uses PostgreSQL as its primary datastore. The connection is configured via the `ACME_DATABASE_URL` environment variable in standard PostgreSQL URI format:

```
postgresql://user:password@host:port/dbname
```

Connection pooling is handled by PgBouncer in production. The recommended pool size is 20 connections for most workloads. Set `database.pool_size=20` in `config.yaml`.

### Caching

Redis is used for caching API responses and session data. Cache TTL defaults to 300 seconds. To adjust, set `cache.ttl_seconds` in `config.yaml`. Cache invalidation happens automatically when the underlying data changes.

## Troubleshooting

### Common Errors

**Error: "Connection refused on port 5432"**
This means PostgreSQL is not running. Start it with `docker-compose up -d postgres` and verify with `pg_isready -h localhost`.

**Error: "JWT token expired"**
The default JWT lifetime is 15 minutes. If you see this error frequently, check that your client is refreshing tokens before expiry. Enable debug logging with `ACME_LOG_LEVEL=DEBUG` to see token refresh attempts.

**Error: "Rate limit exceeded"**
API keys are rate-limited to 1000 RPM by default. If you need higher limits, contact support or upgrade your plan. You can check current usage via the `GET /api/v1/usage` endpoint.

### Performance Tuning

For optimal performance, ensure PostgreSQL has adequate shared_buffers (recommended: 25% of system RAM) and work_mem (recommended: 256MB for analytical queries). Enable query logging with `log_min_duration_statement=1000` to identify slow queries.

The application's response cache reduces database load significantly. Monitor cache hit rates via the `/metrics` endpoint. A healthy cache hit rate is above 80%.
