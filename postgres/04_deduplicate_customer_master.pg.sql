WITH ranked AS (
    SELECT
        customer_key,
        ROW_NUMBER() OVER (
            PARTITION BY customer_id
            ORDER BY
                CASE WHEN postal_code IS NOT NULL THEN 0 ELSE 1 END,
                CASE WHEN birth_date IS NOT NULL THEN 0 ELSE 1 END,
                customer_key
        ) AS rn
    FROM retail_oi.customer_master
)
DELETE FROM retail_oi.customer_master AS cm
USING ranked
WHERE cm.customer_key = ranked.customer_key
  AND ranked.rn > 1;
