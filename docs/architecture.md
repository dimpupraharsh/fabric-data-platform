# Architecture

## Data Plane: Where Records Move

```mermaid
flowchart TB
    CSV[Private CRM and ERP CSV seeds] --> STG[PostgreSQL staging]
    STG --> PG[(PostgreSQL retail_oi)]
    SIM[Controlled source-change generator] --> PG
    REF[Local reference generator] --> S3[(Private AWS S3 retail_ref)]
    PG --> GW[Windows gateway]
    GW --> PC[PostgreSQL snapshot or watermark child]
    S3 --> SC[S3 full-file snapshot child]
    PC --> B[(Bronze Lakehouse)]
    SC --> B
    B --> D[Dimension notebook<br/>Customer, product and location SCD2]
    B --> F[Fact notebooks<br/>Deduplication, quality and historical joins]
    D --> SL[(Silver Lakehouse)]
    F --> SL
    F --> DQ[Rejected records and quality evidence]
    SL --> GB[Gold candidate build]
    GB --> AUD[Audit grain, totals and denominators]
    AUD --> PUB[Transactional Gold publication]
    PUB --> G[(Gold Warehouse)]
    G --> MODEL[Direct Lake semantic model]
    MODEL --> HEALTH[Warehouse/model health comparison]
    MODEL -. "Consumer path; no deployed report claimed" .-> REPORT[Power BI]
```

Bronze retains source shape and lineage. Silver owns cleansing, conformance,
history and late arrivals. Gold owns analytical facts and marts. S3 enriches
transactions; it does not duplicate the sales fact.

## Control Plane: What Tells Pipelines What to Do

```mermaid
flowchart LR
    CFG[Source and object configuration] --> LOOKUP[Parent lookup]
    LOOKUP --> ROUTE[ForEach and source-type routing]
    ROUTE --> CHILD[Child ingestion pipeline]
    STATE[Committed watermark and manifest state] --> CHILD
    CONTRACT[Schema contracts and quality rules] --> CHILD
    CHILD --> CHECK[Copy and validation outcome]
    CHECK --> OK{Succeeded?}
    OK -- Yes --> COMMIT[Commit successful boundary and manifest]
    OK -- No --> FAIL[Log failure and propagate it]
    COMMIT --> LOG[Run and quality history]
    FAIL --> LOG
```

This is the control contract, not universal exactly-once proof. Open findings
concern overlapping arrivals, DQ classification transitions and independently
arriving reference snapshots. Runtime state stays in the control Warehouse,
never in Terraform or Git.

## Delivery Plane: How Code Reaches Fabric

```mermaid
flowchart LR
    CODE[Developer branch] --> PR[Pull request]
    PR --> CI[Credential-free CI<br/>Definitions, tests and Terraform validation]
    CI --> REVIEW[Review and required checks]
    REVIEW --> MAIN[Main commit]
    MAIN --> PACK[Explicit release dispatch<br/>One checksummed artifact]
    PACK --> DEV[Dev publication and validation]
    DEV --> TEST[Test acceptance]
    TEST --> GATE{Production gates and approval}
    GATE -- Approved --> PROD[Production promotion]
    GATE -- Not ready --> STOP[No Production deployment]
    TF[Terraform plan and approved apply] -. "Infrastructure, not business data" .-> ENV[Workspaces and identities]
    ENV -.-> DEV
    ENV -.-> TEST
    ENV -.-> PROD
```

GitHub Actions is the documented application promotion authority. The native
Fabric deployment pipeline is a stage/comparison surface; do not release the
same items independently through both mechanisms.

| Component | Execution location |
| --- | --- |
| Source generators | Local operator; writes only the owned project source |
| Gateway | Windows VM; network bridge, not transformation compute |
| Pipelines | Fabric orchestration and Copy |
| PySpark/Delta notebooks | Fabric Spark |
| Gold SQL | Fabric Warehouse |
| DAX | Semantic model |
| CI | GitHub runner without cloud credentials |
| Release/Terraform tools | Authorized runner/operator with explicit execution |

Business-data backup, replay and migration are separate from Git and item deployment.
