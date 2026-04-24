-- Add marketplace product metadata columns without removing old data
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables WHERE table_name = 'products'
    ) THEN
        ALTER TABLE products
            ADD COLUMN IF NOT EXISTS channel_id BIGINT NULL,
            ADD COLUMN IF NOT EXISTS message_id BIGINT NULL,
            ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
    END IF;
END $$;
