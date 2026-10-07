-- The operational header is the complete-population current state. The
-- historical event feeds are sampled and remain separate event-time evidence.
ALTER TABLE retail_oi.order_header
    ADD COLUMN IF NOT EXISTS order_status VARCHAR(30),
    ADD COLUMN IF NOT EXISTS shipment_status VARCHAR(30),
    ADD COLUMN IF NOT EXISTS payment_status VARCHAR(30),
    ADD COLUMN IF NOT EXISTS delivered_ts TIMESTAMPTZ(3),
    ADD COLUMN IF NOT EXISTS payment_ts TIMESTAMPTZ(3),
    ADD COLUMN IF NOT EXISTS status_updated_ts TIMESTAMPTZ(3);

-- Persist one deterministic historical snapshot per simulated order. The
-- hashed buckets are repeatable, and all derived times follow order_date.
WITH scored AS (
    SELECT order_number,
           MOD(ABS(hashtext(order_number)::BIGINT), 1000) AS status_bucket,
           MOD(ABS(hashtext(order_number || ':ship')::BIGINT), 1000) AS ship_bucket,
           MOD(ABS(hashtext(order_number || ':pay')::BIGINT), 1000) AS pay_bucket
    FROM retail_oi.order_header
    WHERE order_status IS NULL
)
UPDATE retail_oi.order_header AS h
SET order_status = CASE WHEN x.status_bucket < 20 THEN 'cancelled'
                        WHEN x.status_bucket < 25 THEN 'returned'
                        WHEN x.status_bucket < 970 THEN 'delivered'
                        ELSE 'shipped' END,
    shipment_status = CASE WHEN x.status_bucket < 20 THEN 'pending'
                           WHEN x.status_bucket < 25 OR x.status_bucket < 970 THEN 'delivered'
                           WHEN x.ship_bucket < 200 THEN 'delayed'
                           ELSE 'in_transit' END,
    payment_status = CASE WHEN x.status_bucket BETWEEN 20 AND 24 THEN 'refunded'
                          WHEN x.status_bucket < 20 THEN
                              CASE WHEN x.pay_bucket < 500 THEN 'failed' ELSE 'refunded' END
                          WHEN x.status_bucket < 970 THEN 'paid'
                          WHEN x.pay_bucket < 900 THEN 'paid' ELSE 'pending' END,
    delivered_ts = CASE WHEN x.status_bucket BETWEEN 20 AND 969 THEN
                        (h.order_date::timestamp AT TIME ZONE 'UTC')
                        + (2 + MOD(x.ship_bucket, 9)) * INTERVAL '1 day'
                        + MOD(x.pay_bucket, 1440) * INTERVAL '1 minute'
                        ELSE NULL END,
    payment_ts = CASE WHEN x.status_bucket < 970 OR x.pay_bucket < 900 THEN
                      (h.order_date::timestamp AT TIME ZONE 'UTC')
                      + MOD(x.pay_bucket, 1440) * INTERVAL '1 minute'
                      ELSE NULL END,
    status_updated_ts = CURRENT_TIMESTAMP(3),
    dwh_load_ts = CURRENT_TIMESTAMP(3)
FROM scored AS x
WHERE h.order_number = x.order_number;

ANALYZE retail_oi.order_header;
