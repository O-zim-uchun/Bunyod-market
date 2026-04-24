-- Add seller_id to products without affecting existing data
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_name = 'products'
    ) THEN
        ALTER TABLE products
            ADD COLUMN IF NOT EXISTS seller_id BIGINT NULL;

        IF NOT EXISTS (
            SELECT 1
            FROM pg_constraint
            WHERE conname = 'fk_products_seller_id_sellers'
        ) THEN
            ALTER TABLE products
                ADD CONSTRAINT fk_products_seller_id_sellers
                FOREIGN KEY (seller_id) REFERENCES sellers(id)
                ON DELETE SET NULL;
        END IF;

        CREATE INDEX IF NOT EXISTS ix_products_seller_id ON products (seller_id);
    END IF;
END $$;
