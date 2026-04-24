-- Add nullable category for channel-based product classification
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables WHERE table_name = 'products'
    ) THEN
        ALTER TABLE products
            ADD COLUMN IF NOT EXISTS category VARCHAR(64) NULL;
    END IF;
END $$;
