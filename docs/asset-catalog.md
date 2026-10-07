# Fabric Asset Catalogue

Generated from repository definitions, not a live workspace inventory.
Regenerate with `python scripts/build_asset_catalog.py` after item changes.
Environment binding and release gates still apply; this is not a deployment instruction.

## Items

| Item | Type | Description |
| --- | --- | --- |
| [lh_retail_bronze](../workspace/lh_retail_bronze.Lakehouse) | Lakehouse | Raw landing Lakehouse for source-shaped PostgreSQL and S3 arrivals. Preserves source values and ingestion lineage for replay and audit; business cleansing, joins, and deduplication belong in Silver. |
| [lh_retail_silver](../workspace/lh_retail_silver.Lakehouse) | Lakehouse | Conformed Lakehouse for validated and deduplicated retail data, SCD Type 1/2 dimensions, line-item sales and event facts, reference joins, late-arrival handling, and quality rejects. |
| [nb_bronze_batch_guard](../workspace/nb_bronze_batch_guard.Notebook) | Notebook | Creates and checks approved Bronze landing targets, enforces exact batch counts and schema observations, and writes immutable manifests before checkpoint commit. |
| [nb_bronze_prepare_snapshot_target](../workspace/nb_bronze_prepare_snapshot_target.Notebook) | Notebook | Adds nullable ingest-lineage columns to approved Bronze snapshot tables and clears only rows from the supplied retry batch; existing baseline data is preserved. |
| [nb_gold_serving_health](../workspace/nb_gold_serving_health.Notebook) | Notebook | After Gold publication, compares its KPI audit and publication timestamp with the live semantic model, logs the verdict in the control Warehouse, and fails the daily pipeline on stale or mismatched serving data. |
| [nb_silver_dimensions](../workspace/nb_silver_dimensions.Notebook) | Notebook | Builds Silver customer, product, category, location, and warehouse-coverage dimensions from Bronze snapshots with the approved SCD rules and inferred history. |
| [nb_silver_events](../workspace/nb_silver_events.Notebook) | Notebook | Conforms order, shipment, and payment events while preserving business event time and Bronze arrival time; merges on immutable source event keys. |
| [nb_silver_order_header](../workspace/nb_silver_order_header.Notebook) | Notebook | Conforms complete-population PostgreSQL order headers into one Silver row per order, preserving current status, delivery/payment times, source lineage, and validity flags. |
| [nb_silver_reconciliation](../workspace/nb_silver_reconciliation.Notebook) | Notebook | Checks Silver row counts, uniqueness, conformed order coverage, status validity, and reconciliation before Gold publication. |
| [nb_silver_sales](../workspace/nb_silver_sales.Notebook) | Notebook | Builds the line-item sales fact, resolves SCD dimension versions as of order date, flags soft data defects, rejects hard reference failures, and merges on source sales key. |
| [pl_bronze_orchestrator](../workspace/pl_bronze_orchestrator.DataPipeline) | DataPipeline | Resolves approved source metadata and routes PostgreSQL deltas, master snapshots, or S3 reference snapshots. Snapshots append run-tagged SCD2 history; facts/events use bounded watermarks. Runs only when triggered or scheduled. |
| [pl_bronze_pg_full_refresh](../workspace/pl_bronze_pg_full_refresh.DataPipeline) | DataPipeline | Appends an approved PostgreSQL master snapshot with Fabric run, source, arrival-time, and batch lineage. Adds nullable columns without rewriting baseline rows. Preserves history for Silver SCD2; does not advance source watermarks. |
| [pl_bronze_pg_incremental_all](../workspace/pl_bronze_pg_incremental_all.DataPipeline) | DataPipeline | Runs the four PostgreSQL fact/event objects serially through the metadata parent. Each object gets its own lock, bounded watermark, batch manifest, and commit record; serial execution protects gateway and source capacity. |
| [pl_bronze_pg_order_header](../workspace/pl_bronze_pg_order_header.DataPipeline) | DataPipeline | Runs the governed PostgreSQL order-header source through the shared watermark child. Initial load creates the complete-population order denominator; later runs append only changed headers with a committed manifest. |
| [pl_bronze_pg_partition_append](../workspace/pl_bronze_pg_partition_append.DataPipeline) | DataPipeline | One-time PostgreSQL baseline continuation: appends a bounded non-overlapping key range to a target initialized by the overwrite child. The lower-exclusive/upper-inclusive interval prevents boundary duplicates. Not for recurring incremental loads. |
| [pl_bronze_pg_partition_overwrite](../workspace/pl_bronze_pg_partition_overwrite.DataPipeline) | DataPipeline | One-time PostgreSQL baseline initializer: writes the first bounded numeric-key range with overwrite semantics. Use only for an approved initial load or deliberate rebuild; later ranges use the append child. Not for recurring incremental capture. |
| [pl_bronze_pg_watermark](../workspace/pl_bronze_pg_watermark.DataPipeline) | DataPipeline | Incremental PostgreSQL child: lock the object, freeze inclusive dwh_load_ts/key bounds, prepare a batch, copy its delta with lineage, validate and write a manifest, then commit. Failures do not advance the watermark; retries replay the interval. |
| [pl_bronze_s3_snapshot](../workspace/pl_bronze_s3_snapshot.DataPipeline) | DataPipeline | Appends an approved S3 reference CSV as a full-file snapshot with Fabric run, source, arrival-time, and batch lineage. Run when the file changes; this is not row-level CDC. Retained versions preserve geography and coverage history for Silver SCD2. |
| [pl_daily_retail_processing](../workspace/pl_daily_retail_processing.DataPipeline) | DataPipeline | Daily PostgreSQL Bronze, incremental Silver, audited Gold publication, and a logged semantic-serving health gate. S3 reference snapshots refresh separately. |
| [pl_gold_orchestrator](../workspace/pl_gold_orchestrator.DataPipeline) | DataPipeline | Builds and audits Gold candidates, then transactionally replaces live rows without dropping semantic-model tables. Gross booked sales is not net revenue. |
| [pl_silver_orchestrator](../workspace/pl_silver_orchestrator.DataPipeline) | DataPipeline | Runs Silver in order: lock, set arrival boundary, build SCD dimensions/coverage, merge events and sales, reconcile, then commit. Failures are logged and release locks; baseline rebuilds, incremental processes new arrivals. |
| [sm_retail_order_intelligence](../workspace/sm_retail_order_intelligence.SemanticModel) | SemanticModel | Certified retail Gold semantic model. Line and order facts use audited eligibility rules; documented DAX measures cover revenue, orders, SLA, lifecycle, payments, and YoY. |
| [wh_retail_control](../workspace/wh_retail_control.Warehouse) | Warehouse | Metadata-driven control plane for source configuration, pipeline and object runs, locks and checkpoints, schema contracts/drift, batch manifests, and quality results. Contains no retail business facts or credentials. |
| [wh_retail_gold](../workspace/wh_retail_gold.Warehouse) | Warehouse | Business-facing Gold Warehouse sourced only from conformed Silver. Hosts SCD-aware dimensions, line-item sales, and certified gross-sales marts. Order, fulfillment, lifecycle, and payment KPIs are gated pending source identity repair. |

## pl_bronze_orchestrator

Concurrency: `not explicitly set`.

### Parameters

| Name | Type | Default |
| --- | --- | --- |
| partition_lower_key | String | 0 |
| partition_upper_key | String | 0 |
| partition_write_mode | String | append |
| source_object_id | String | not supplied |

### Variables

None declared.

### Activities

| Activity path | Type | Description |
| --- | --- | --- |
| ResolveSourceObjectMetadata | Script | Reads the active source-object configuration from wh_retail_control so the parent can route using approved source, target, connection, and load-strategy metadata. |
| DispatchPostgreSqlBaselineOverwrite | IfCondition | Checks whether an explicitly requested first baseline partition uses overwrite initialization; only the approved initial range takes this path. |
| DispatchPostgreSqlBaselineOverwrite/RunPostgreSqlPartitionOverwriteChild | ExecutePipeline | Invokes the one-time PostgreSQL partition initializer with the configured key bounds and Bronze target; not used for recurring incrementals. |
| DispatchPostgreSqlBaselineAppend | IfCondition | Checks whether the requested baseline continuation uses append semantics for a non-overlapping PostgreSQL key range. |
| DispatchPostgreSqlBaselineAppend/RunPostgreSqlPartitionAppendChild | ExecutePipeline | Copies the requested lower-exclusive, upper-inclusive PostgreSQL partition to the existing Bronze baseline target. |
| DispatchPostgreSqlFullRefresh | IfCondition | Routes an approved small PostgreSQL master snapshot to the append-with-lineage child; the source watermark is not advanced. |
| DispatchPostgreSqlFullRefresh/RunPostgreSqlFullRefreshChild | ExecutePipeline | Appends a run-tagged customer or product snapshot to Bronze so Silver can observe source history. |
| DispatchPostgreSqlWatermark | IfCondition | Routes transactional PostgreSQL objects to bounded watermark extraction when their configured load strategy is watermark_incremental. |
| DispatchPostgreSqlWatermark/RunPostgreSqlWatermarkChild | ExecutePipeline | Runs the reusable bounded PostgreSQL delta child with the metadata-defined table, watermark, tie-breaker, and Bronze target. |
| DispatchS3Snapshot | IfCondition | Routes an approved S3 reference file to full-snapshot ingestion only when explicitly invoked; S3 does not use row-level watermarks. |
| DispatchS3Snapshot/RunS3SnapshotChild | ExecutePipeline | Invokes the S3 CSV snapshot child using the configured object, source prefix/file, and Bronze target. |

## pl_bronze_pg_full_refresh

Concurrency: `not explicitly set`.

### Parameters

| Name | Type | Default |
| --- | --- | --- |
| bronze_target | String | not supplied |
| source_object_id | String | not supplied |
| source_schema | String | retail_oi |
| source_table | String | not supplied |

### Variables

None declared.

### Activities

| Activity path | Type | Description |
| --- | --- | --- |
| PrepareSnapshotTargetSchema | TridentNotebook | Adds nullable Bronze ingest-lineage columns when missing and removes only rows belonging to this retry batch; existing baseline rows are preserved. |
| CopySourceObjectToBronze | Copy | Reads the configured PostgreSQL master table and appends its rows with Fabric run, source-object, arrival-time, and batch lineage. |

## pl_bronze_pg_incremental_all

Concurrency: `not explicitly set`.

### Parameters

None declared.

### Variables

None declared.

### Activities

| Activity path | Type | Description |
| --- | --- | --- |
| RunSalesOrderLineWatermark | ExecutePipeline | Runs metadata object 1003 for sales_order_line through the shared bounded watermark child and waits for completion before the next object. |
| RunOrderStatusEventWatermark | ExecutePipeline | Runs metadata object 1004 for order_status_event through the shared bounded watermark child. |
| RunShipmentStatusEventWatermark | ExecutePipeline | Runs metadata object 1005 for shipment_status_event through the shared bounded watermark child. |
| RunPaymentStatusEventWatermark | ExecutePipeline | Runs metadata object 1006 for payment_status_event through the shared bounded watermark child. |

## pl_bronze_pg_order_header

Concurrency: `not explicitly set`.

### Parameters

None declared.

### Variables

None declared.

### Activities

| Activity path | Type | Description |
| --- | --- | --- |
| RunOrderHeaderWatermark | ExecutePipeline | Loads metadata object 1007 through the bounded PostgreSQL watermark child and waits for its count validation, manifest, and checkpoint commit. |

## pl_bronze_pg_partition_append

Concurrency: `not explicitly set`.

### Parameters

| Name | Type | Default |
| --- | --- | --- |
| bronze_target | String | not supplied |
| lower_key | String | not supplied |
| partition_column | String | not supplied |
| source_object_id | String | not supplied |
| source_schema | String | retail_oi |
| source_table | String | not supplied |
| upper_key | String | not supplied |

### Variables

None declared.

### Activities

| Activity path | Type | Description |
| --- | --- | --- |
| AppendPostgreSqlBaselinePartition | Copy | Appends one PostgreSQL key range to the initialized baseline; lower-exclusive and upper-inclusive bounds prevent overlap at partition edges. |

## pl_bronze_pg_partition_overwrite

Concurrency: `not explicitly set`.

### Parameters

| Name | Type | Default |
| --- | --- | --- |
| bronze_target | String | not supplied |
| lower_key | String | 0 |
| partition_column | String | not supplied |
| source_object_id | String | not supplied |
| source_schema | String | retail_oi |
| source_table | String | not supplied |
| upper_key | String | not supplied |

### Variables

None declared.

### Activities

| Activity path | Type | Description |
| --- | --- | --- |
| CopyFirstPostgreSqlBaselinePartition | Copy | Initializes the first approved PostgreSQL baseline partition with overwrite semantics; use only for the first load or an authorized rebuild. |

## pl_bronze_pg_watermark

Concurrency: `not explicitly set`.

### Parameters

| Name | Type | Default |
| --- | --- | --- |
| bronze_target | String | not supplied |
| source_object_id | String | not supplied |
| source_schema | String | retail_oi |
| source_table | String | not supplied |
| tie_breaker_column | String | not supplied |
| watermark_column | String | dwh_load_ts |

### Variables

None declared.

### Activities

| Activity path | Type | Description |
| --- | --- | --- |
| CaptureUpperBoundAndSchema | Lookup | Captures a fixed source-side upper watermark and observed schema so this run processes a bounded, auditable interval. |
| PrepareControlledBatch | Script | Acquires the object lease and registers the deterministic batch and expected interval in the control warehouse before copying. |
| ProcessPreparedBatch | IfCondition | Skips a no-change interval or executes count, replay reset, copy, validation, manifest, and checkpoint commit in order. |
| ProcessPreparedBatch/CountBoundedSourceRows | Lookup | Counts source rows inside the frozen lower/upper timestamp and tie-breaker bounds to establish the expected copy count. |
| ProcessPreparedBatch/RegisterExpectedRows | Script | Stores the source count for this object batch so Bronze validation can compare actual rows with the expected interval. |
| ProcessPreparedBatch/ResetStagedBatchForReplay | TridentNotebook | Deletes only an uncommitted partial Bronze copy tagged with this deterministic batch ID before retrying the same interval. |
| ProcessPreparedBatch/CopyBoundedRowsToBronze | Copy | Copies only rows within the frozen watermark window and adds source, run, arrival-time, and batch lineage columns. |
| ProcessPreparedBatch/ValidateBatchAndWriteManifest | TridentNotebook | Compares Bronze batch rows with the expected source count and writes immutable manifest evidence before checkpoint advancement. |
| ProcessPreparedBatch/CommitCheckpoint | Script | Commits the upper watermark and releases the object lock only after copy validation and manifest creation succeed. |
| ProcessPreparedBatch/FailAfterCountBoundedSourceRows | Script | Records the failure after source counting and releases the object lease without advancing the checkpoint. |
| ProcessPreparedBatch/FailAfterRegisterExpectedRows | Script | Records the failure after expected-count registration and releases the object lease without advancing the checkpoint. |
| ProcessPreparedBatch/FailAfterResetStagedBatchForReplay | Script | Records the failure after replay cleanup and leaves the prior committed watermark unchanged. |
| ProcessPreparedBatch/FailAfterCopyBoundedRowsToBronze | Script | Records the failed copy and preserves the prior checkpoint so the deterministic batch can be retried safely. |
| ProcessPreparedBatch/FailAfterValidateBatchAndWriteManifest | Script | Records validation/manifest failure and prevents the pipeline from committing the upper watermark. |
| ProcessPreparedBatch/FailAfterCommitCheckpoint | Script | Records a checkpoint-commit activity failure for operator investigation; inspect control state before retrying. |
| ProcessPreparedBatch/PropagateFailAfterCountBoundedSourceRows | Fail | Preserves the failed child outcome after cleanup, even if failure logging itself fails; downstream success branches must not run. |
| ProcessPreparedBatch/PropagateFailAfterRegisterExpectedRows | Fail | Preserves the failed child outcome after cleanup, even if failure logging itself fails; downstream success branches must not run. |
| ProcessPreparedBatch/PropagateFailAfterResetStagedBatchForReplay | Fail | Preserves the failed child outcome after cleanup, even if failure logging itself fails; downstream success branches must not run. |
| ProcessPreparedBatch/PropagateFailAfterCopyBoundedRowsToBronze | Fail | Preserves the failed child outcome after cleanup, even if failure logging itself fails; downstream success branches must not run. |
| ProcessPreparedBatch/PropagateFailAfterValidateBatchAndWriteManifest | Fail | Preserves the failed child outcome after cleanup, even if failure logging itself fails; downstream success branches must not run. |
| ProcessPreparedBatch/PropagateFailAfterCommitCheckpoint | Fail | Preserves the failed child outcome after cleanup, even if failure logging itself fails; downstream success branches must not run. |

## pl_bronze_s3_snapshot

Concurrency: `not explicitly set`.

### Parameters

| Name | Type | Default |
| --- | --- | --- |
| bronze_target | String | not supplied |
| source_file | String | not supplied |
| source_folder | String | not supplied |
| source_object_id | String | not supplied |
| source_object_name | String | not supplied |

### Variables

None declared.

### Activities

| Activity path | Type | Description |
| --- | --- | --- |
| PrepareSnapshotTargetSchema | TridentNotebook | Adds nullable Bronze ingest-lineage columns when missing and removes only rows belonging to this retry batch; existing baseline rows are preserved. |
| CopyS3ReferenceSnapshotToBronze | Copy | Reads the configured S3 CSV as a complete reference snapshot and appends run, source, arrival-time, and batch lineage to Bronze. |

## pl_daily_retail_processing

Concurrency: `1`.

### Parameters

None declared.

### Variables

None declared.

### Activities

| Activity path | Type | Description |
| --- | --- | --- |
| BronzeCustomerSnapshot | ExecutePipeline | Invokes the metadata-driven Bronze parent for PostgreSQL customer object 1001 and waits for the snapshot append to succeed. |
| BronzeProductSnapshot | ExecutePipeline | Invokes the metadata-driven Bronze parent for PostgreSQL product object 1002 after the customer snapshot succeeds. |
| BronzeSalesWatermark | ExecutePipeline | Invokes the metadata-driven Bronze parent for sales object 1003 after both master snapshots succeed. |
| BronzeOrderEventsWatermark | ExecutePipeline | Invokes the metadata-driven Bronze parent for order event object 1004 after sales delta completion. |
| BronzeShipmentEventsWatermark | ExecutePipeline | Invokes the metadata-driven Bronze parent for shipment event object 1005 after order event completion. |
| BronzePaymentEventsWatermark | ExecutePipeline | Invokes the metadata-driven Bronze parent for payment event object 1006 after shipment event completion. |
| BronzeOrderHeaderWatermark | ExecutePipeline | Loads changed complete-population order headers as source object 1007 and waits for the Bronze manifest and watermark checkpoint to commit. |
| SilverIncrementalProcessing | ExecutePipeline | Starts Silver incremental processing only after all seven PostgreSQL Bronze loads, including order headers, complete successfully. |
| GoldAuditedPublication | ExecutePipeline | Builds Gold candidate tables, audits the KPI contract, and transactionally replaces live Gold rows only after the Silver child succeeds. Failure leaves the prior publication in place. |
| PostGoldServingHealth | TridentNotebook | Compares the published Gold audit, freshness timestamp, and four certified KPIs with the live semantic model; logs the result in wh_retail_control and fails the parent on a stale or mismatched view. |

## pl_gold_orchestrator

Concurrency: `1`.

### Parameters

None declared.

### Variables

None declared.

### Activities

| Activity path | Type | Description |
| --- | --- | --- |
| ValidateSilverReady | Script | Requires nonempty Silver sales-line and complete-population order facts before preparing a Gold candidate. |
| ClearPriorGoldBuild | Script | Removes only the previous candidate tables; currently served Gold and the semantic model stay available. |
| BuildGoldDimensions | Script | Builds candidate SCD2 customer, product, location, and category dimensions from conformed Silver. |
| BuildGoldSalesFact | Script | Builds one candidate row per Silver sales line with order-identity and eligibility audit flags. |
| BuildGoldSalesMarts | Script | Builds candidate daily, monthly, customer, product, category, geography, and complete-year YoY summaries. |
| BuildGoldOrderMarts | Script | Builds candidate order state, lifecycle, payment, shipping SLA, and repeat-order marts from full-population headers. |
| BuildSemanticDimensions | Script | Builds candidate continuous date and current-customer dimensions for stable semantic relationships. |
| AuditGoldCandidate | Script | Audits candidate denominators and blocks publication if grain, coverage, revenue, or mart totals disagree. |
| PublishGoldAtomically | Script | Copies audited candidate rows into existing Gold tables in one rollback-capable transaction; table identities remain stable. |
| VerifyPublishedGold | Script | Confirms the committed serving audit row exactly matches the candidate that passed the KPI gate. |

## pl_silver_orchestrator

Concurrency: `not explicitly set`.

### Parameters

| Name | Type | Default |
| --- | --- | --- |
| load_mode | String | incremental |

### Variables

None declared.

### Activities

| Activity path | Type | Description |
| --- | --- | --- |
| StartSilverRunAndAcquireLocks | Script | Creates the Silver run record and acquires transform locks so overlapping executions cannot write the same targets. |
| ResolveSilverIngestLowerBound | Script | Reads the last committed Silver arrival boundary used by event and sales notebooks to select newly landed Bronze versions. |
| BuildSilverDimensionsAndBridges | TridentNotebook | Runs the dimensions notebook to conform customer, product, category, location, and warehouse coverage history before facts resolve keys. |
| BuildSilverEventFacts | TridentNotebook | Runs the event notebook to standardize and idempotently merge order, shipment, and payment events by source event key. |
| BuildSilverSalesFact | TridentNotebook | Runs the sales notebook to resolve line items against SCD dimensions as of order date and write accepted facts or hard rejects. |
| BuildSilverOrderFact | TridentNotebook | Merges the complete-population order header by order number, retaining current lifecycle/payment/fulfillment state and source quality flags. |
| ReconcileSilverModel | TridentNotebook | Runs hard Silver integrity assertions; the parent cannot commit success unless keys, counts, histories, and event uniqueness reconcile. |
| CommitSilverRunSuccess | Script | Marks the Silver run successful and advances transform state only after all builds and reconciliation pass. |
| LogDimensionsFailure | Script | Marks the Silver run failed after the dimensions notebook fails and records a diagnostic message for operators. |
| LogEventsFailure | Script | Marks the Silver run failed after the event notebook fails and records a diagnostic message for operators. |
| LogSalesFailure | Script | Marks the Silver run failed after the sales notebook fails and records a diagnostic message for operators. |
| LogOrderFactFailure | Script | Marks the Silver run failed if order-header conformance fails, preserving its checkpoint for a safe retry. |
| LogReconciliationFailure | Script | Marks the Silver run failed when a hard invariant fails; inspect reconciliation_result and notebook output before retrying. |
| PropagateLogDimensionsFailure | Fail | Preserves the failed child outcome after cleanup, even if failure logging itself fails; downstream success branches must not run. |
| PropagateLogEventsFailure | Fail | Preserves the failed child outcome after cleanup, even if failure logging itself fails; downstream success branches must not run. |
| PropagateLogSalesFailure | Fail | Preserves the failed child outcome after cleanup, even if failure logging itself fails; downstream success branches must not run. |
| PropagateLogOrderFactFailure | Fail | Preserves the failed child outcome after cleanup, even if failure logging itself fails; downstream success branches must not run. |
| PropagateLogReconciliationFailure | Fail | Preserves the failed child outcome after cleanup, even if failure logging itself fails; downstream success branches must not run. |
