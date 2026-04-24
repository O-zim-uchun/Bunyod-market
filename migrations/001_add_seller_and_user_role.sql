-- Add sellers table
CREATE TABLE IF NOT EXISTS sellers (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    telegram_id BIGINT NOT NULL UNIQUE,
    channel_id BIGINT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Add role column to users if it does not exist
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS role VARCHAR(20) NOT NULL DEFAULT 'user';

-- Add seller_id column to users if it does not exist
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS seller_id BIGINT NULL;

-- Add FK from users.seller_id -> sellers.id
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_users_seller_id_sellers'
    ) THEN
        ALTER TABLE users
            ADD CONSTRAINT fk_users_seller_id_sellers
            FOREIGN KEY (seller_id) REFERENCES sellers(id)
            ON DELETE SET NULL;
    END IF;
END $$;

-- Add role constraint safely
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_users_role_allowed_values'
    ) THEN
        ALTER TABLE users
            ADD CONSTRAINT ck_users_role_allowed_values
            CHECK (role IN ('super_admin', 'seller', 'user'));
    END IF;
END $$;

-- Backfill role for existing records:
-- if users.is_admin exists and true -> super_admin
-- otherwise -> user
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'users' AND column_name = 'is_admin'
    ) THEN
        EXECUTE $sql$
            UPDATE users
            SET role = CASE
                WHEN is_admin IS TRUE THEN 'super_admin'
                ELSE 'user'
            END
            WHERE role IS NULL OR role = 'user'
        $sql$;
    ELSE
        UPDATE users
        SET role = 'user'
        WHERE role IS NULL;
    END IF;
END $$;

-- seller_id remains NULL by default for backward compatibility
