ALTER TABLE retail_oi.customer_master
    ADD COLUMN IF NOT EXISTS state_province VARCHAR(100),
    ADD COLUMN IF NOT EXISTS city VARCHAR(100),
    ADD COLUMN IF NOT EXISTS postal_code VARCHAR(30);

CREATE INDEX IF NOT EXISTS ix_customer_master_postal_code
    ON retail_oi.customer_master (postal_code);
