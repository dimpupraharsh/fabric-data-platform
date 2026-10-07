-- Continuous Gregorian calendar, 2010-2030 inclusive. This supports real
-- date relationships and YoY calculations even when a day has no orders.
IF OBJECT_ID('gold.dim_date', 'U') IS NULL
    CREATE TABLE gold.dim_date AS
    SELECT CAST(DATEADD(day, n.value, CAST('2010-01-01' AS date)) AS date) AS calendar_date,
           YEAR(DATEADD(day, n.value, CAST('2010-01-01' AS date))) AS calendar_year,
           DATEPART(quarter, DATEADD(day, n.value, CAST('2010-01-01' AS date))) AS calendar_quarter,
           MONTH(DATEADD(day, n.value, CAST('2010-01-01' AS date))) AS calendar_month,
           CAST(DATENAME(month, DATEADD(day, n.value, CAST('2010-01-01' AS date))) AS varchar(20)) AS month_name,
           DAY(DATEADD(day, n.value, CAST('2010-01-01' AS date))) AS day_of_month,
           DATEFROMPARTS(YEAR(DATEADD(day, n.value, CAST('2010-01-01' AS date))),
                         MONTH(DATEADD(day, n.value, CAST('2010-01-01' AS date))), 1) AS month_start_date
    FROM GENERATE_SERIES(0, DATEDIFF(day, CAST('2010-01-01' AS date), CAST('2030-12-31' AS date)), 1) AS n;
GO

-- A unique stable-entity table for order-grain semantic relationships.
-- The full dim_customer table continues to hold every SCD2 version.
IF OBJECT_ID('gold.dim_customer_current', 'U') IS NULL
    CREATE TABLE gold.dim_customer_current AS
    SELECT customer_entity_key, customer_id, customer_business_key,
           first_name, last_name, country, location_entity_key
    FROM gold.dim_customer
    WHERE dwh_is_current = 1;
GO
