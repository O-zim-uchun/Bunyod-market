# Railway Variables (copy-paste)

Quyidagini Railway → Service → **Variables** bo'limiga nusxalab qo'ying.

## Minimal (ishlashi uchun yetarli)

```env
BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN
ADMIN_ID=123456789
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname
```

## Agar `DATABASE_URL` bo'lmasa (fallback variant)

```env
BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN
ADMIN_ID=123456789
DATABASE_PUBLIC_URL=postgresql+asyncpg://user:pass@host:5432/dbname
POSTGRES_URL=postgresql+asyncpg://user:pass@host:5432/dbname
```

## Ixtiyoriy (legacy/fallback)

```env
TELEGRAM_BOT_TOKEN=
TOKEN=
ADMIN_BOT_TOKEN=
CLIENT_BOT_TOKEN=
REDIS_URL=
WEBHOOK_BASE_URL=
WEBHOOK_SECRET=
PORT=
```
