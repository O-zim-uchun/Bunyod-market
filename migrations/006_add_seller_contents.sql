CREATE TABLE IF NOT EXISTS seller_contents (
    id BIGSERIAL PRIMARY KEY,
    seller_id BIGINT NOT NULL REFERENCES sellers(id) ON DELETE CASCADE,
    content_type VARCHAR(32) NOT NULL,
    channel_id BIGINT NULL,
    message_id BIGINT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_seller_content_type UNIQUE (seller_id, content_type)
);
