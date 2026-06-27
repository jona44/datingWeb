# Railway Deployment

This project is configured for Railway with `railway.json`.

## What Railway Runs

- Build: `tailwindcss -i ./theme/static_src/src/input.css -o ./theme/static/css/dist/styles.css --config ./theme/static_src/tailwind.config.js --minify && python manage.py collectstatic --noinput`
- Pre-deploy: `python manage.py migrate`
- Start: `daphne -b 0.0.0.0 -p $PORT core.asgi:application`

The app uses Daphne because messaging depends on Django Channels and WebSockets.

## Railway Services

Create these services in the same Railway project:

- App service from this repository
- PostgreSQL database
- Redis database, recommended for Channels and presence

## App Variables

Set these variables on the app service:

```text
DJANGO_SETTINGS_MODULE=core.settings
DEBUG=False
SECRET_KEY=<generate-a-long-random-secret>
DATABASE_URL=${{Postgres.DATABASE_URL}}
REDIS_URL=${{Redis.REDIS_URL}}
ACCOUNT_DEFAULT_HTTP_PROTOCOL=https
```

Optional variables:

```text
ALLOWED_HOSTS=your-custom-domain.com
CSRF_TRUSTED_ORIGINS=https://your-custom-domain.com
CORS_ALLOWED_ORIGINS=https://your-frontend-domain.com
EMAIL_HOST=<smtp-host>
EMAIL_PORT=587
EMAIL_HOST_USER=<smtp-user>
EMAIL_HOST_PASSWORD=<smtp-password>
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=support@your-domain.com
```

Railway provides `RAILWAY_PUBLIC_DOMAIN` automatically after a public domain is generated, and the Django settings add it to `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`.

## Deploy

1. Push this repository to GitHub.
2. In Railway, create a new project from the GitHub repo.
3. Add PostgreSQL and Redis services.
4. Set the app variables above.
5. Generate a public domain for the app service.
6. Redeploy the app service.
