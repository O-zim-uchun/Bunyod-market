-- Add telegram_id to users for /start role resolution by Telegram account
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS telegram_id BIGINT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS ix_users_telegram_id
    ON users (telegram_id)
    WHERE telegram_id IS NOT NULL;
