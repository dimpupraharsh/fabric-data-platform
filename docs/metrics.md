# Metrics and Reporting Contract

Sales grain is one source sales line; order grain is one business order.
Explicit eligibility flags define metric populations. Sampled events are not
company-wide denominators. Stable entity keys collapse SCD2 versions for rollups.

## The 18 Explicit DAX Measures

| Measure | Definition |
| --- | --- |
| Gross Booked Sales | Eligible sales-line amounts |
| Units Sold | Quantity on eligible lines |
| Sales Lines | Eligible line count, not orders |
| Average Selling Price | Gross booked sales / units |
| Prior Year Gross Booked Sales | Equivalent prior-year dates; blank without date filtering |
| Gross Booked Sales YoY % | Date-aligned change / prior-year sales |
| Eligible Orders | Orders passing eligibility |
| Eligible Order Gross Booked Sales | Booked sales assigned to eligible orders |
| Average Order Value | Eligible-order sales / eligible orders |
| Cancelled Orders | Eligible orders currently cancelled |
| Cancellation Rate | Cancelled / eligible orders |
| Returned Orders | Eligible orders currently returned |
| Return Rate | Returned / eligible orders |
| SLA Eligible Deliveries | Eligible orders also passing shipping eligibility |
| On-Time Deliveries | Delivered date on/before promised due date |
| On-Time Delivery Rate | On-time / SLA-eligible deliveries |
| Paid Orders | Eligible orders currently paid |
| Paid Order Share | Paid / eligible orders, not payment attempt success |

Authority: [sales TMDL](https://github.com/dimpupraharsh/fabric-data-platform/blob/setup/enterprise-fabric-cicd/workspace/sm_retail_order_intelligence.SemanticModel/definition/tables/fact_sales.tmdl)
and [order TMDL](https://github.com/dimpupraharsh/fabric-data-platform/blob/setup/enterprise-fabric-cicd/workspace/sm_retail_order_intelligence.SemanticModel/definition/tables/fact_order.tmdl).

## The 11 Gold Marts

| Mart | Purpose |
| --- | --- |
| `mart_daily_sales` | Daily sales, units, lines and weighted selling price |
| `mart_monthly_sales` | Monthly equivalents |
| `mart_customer_spend` | Spend, units and first/latest sales |
| `mart_product_performance` | Sales/units by stable product |
| `mart_category_performance` | Sales by historical category |
| `mart_geography_sales` | Sales/units by historical location |
| `mart_sales_yoy` | Full-year comparison, currently 2020-2025 only |
| `mart_order_lifecycle` | Current status counts, AOV, cancellation and return |
| `mart_shipping_sla` | On-time/late counts, on-time rate and calendar delivery days by zone |
| `mart_payment_status` | Current payment-status counts and associated booked sales |
| `mart_customer_order_frequency` | Order counts, first/latest dates, repeat flags |

Definitions: [sales SQL](https://github.com/dimpupraharsh/fabric-data-platform/blob/setup/enterprise-fabric-cicd/fabric/gold_warehouse/12_create_sales_marts.sql)
and [order SQL](https://github.com/dimpupraharsh/fabric-data-platform/blob/setup/enterprise-fabric-cicd/fabric/gold_warehouse/15_create_order_marts.sql).
These are reference building blocks. The deployed pipeline manages candidate
rebuild/publication; create-if-absent scripts alone do not refresh existing tables.

## Deliberate Limits

- Booked sales is not net/recognized revenue, profit or settled cash.
- Customer spend is not lifetime value; no cohort-retention definition exists.
- Payment states are not attempts, settlement amounts or refund amounts.
- Shipping uses promised dates/calendar days, not carrier contracts/business days.
- Repeat flags exist in SQL; no explicit repeat-share DAX measure exists.
- DAX YoY needs date filtering; the full-year mart excludes partial current years.
- Real cross-market financial totals require an agreed common-currency/conversion contract.
