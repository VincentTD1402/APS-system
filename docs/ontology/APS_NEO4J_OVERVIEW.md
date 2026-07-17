# APS Pipeline — Overview

## 1. Architecture

```
G-System ERP  (9 endpoints, A/U/D sync)
     │
     ▼
Phase 01: Local DB (PostgreSQL)
     │  8 SQLAlchemy tables: Item, BOM, WorkCenter, Routing,
     │  Operation, RoutingItem, CalendarEntry, Demand, ItemProcess
     ▼
Phase 02: RDF Graph (rdflib)
     │  TBox (OWL schema) + ABox (instance data)
     │  ~1200 triples
     ▼
Phase 03: Validate
     │  OWL-RL reasoning (owlrl)
     │  SHACL constraints (pyshacl)
     ▼
Phase 04: Neo4j
        139 nodes, 248 relationships
```

---

## 2. Initial Setup

### 2.1 Install dependencies

```bash
uv sync
```

### 2.2 Create `.env` file

```bash
cp .env.example .env
```

Contact the AI team leader to get the correct values for `.env` params.

Fill in `.env` (refer to `.env.example`):

```env
# APS PostgreSQL — via Docker Compose (host port 5433)
APS_DB_URL=postgresql://aps_user:yourpassword@localhost:5433/aps_db
APS_DB_USER=aps_user
APS_DB_PASSWORD=yourpassword
APS_DB_NAME=aps_db

# Neo4j — via Docker Compose
APS_NEO4J_URI=bolt://localhost:7687
APS_NEO4J_USER=neo4j
APS_NEO4J_PASSWORD=yourpassword
APS_NEO4J_DATABASE=neo4j

# G-System API
GSYSTEM_BASE_URL=https://...
GSYSTEM_API_KEY=
```

> `APS_DB_USER`, `APS_DB_PASSWORD`, `APS_DB_NAME` are read by docker-compose.yml to initialize the PostgreSQL container.

### 2.3 Start PostgreSQL + Neo4j

```bash
# Start only db + neo4j (does not affect other services running on the server)
docker compose up -d db neo4j

# Check status
docker compose ps

# Restart individual services if needed
docker compose restart db
docker compose restart neo4j
```

---

## 3. Initialize DB + Seed Mock Data

```bash
uv run python app/scripts/seed_mock_data.py
```

**Expected result:**

| Table | Rows | Description |
|-------|------|-------------|
| `aps_item` | 12 | 8 Product, 2 SemiProduct, 2 RawMaterial |
| `aps_bom` | 3 | BOM headers |
| `aps_bom_component` | ~9 | BOM component lines |
| `aps_workcenter` | 3 | Work centers |
| `aps_routing` | 5 | Routings |
| `aps_routing_item` | 8 | Item ↔ Routing links |
| `aps_operation` | 7 | Operations (production steps) |
| `aps_calendar_entry` | 90 | Work calendar (~3 months) |
| `aps_demand` | 5 | Production plans |
| `aps_item_process` | 0 | Item process config (populated via G-System sync) |

---

## 4. Run Pipeline / Sync API

### Via HTTP API (production / cron job)

```bash
# Trigger sync (Phase 01 only: G-System → APS DB)
curl -X POST http://localhost:8001/api/v1/gsystem/sync/run
# → {"job_id": "<uuid>", "status": "accepted"}

# Poll result
curl http://localhost:8001/api/v1/gsystem/sync/jobs/<job_id>
# → 202 while running, 200 when done
```

### Via CLI (dev / manual)

```bash
# Full pipeline: Phase 01 (G-System sync) → 02 → 03 → 04
uv run python app/scripts/run_pipeline.py

# Skip G-System sync — use existing DB data (local dev / no G-System access)
uv run python app/scripts/run_pipeline.py --use-mock

# Phase 01+02 only (dry-run, no owlrl/pyshacl/neo4j needed)
uv run python app/scripts/run_pipeline.py --skip-validation --skip-neo4j

# Phase 01+02+03 (validate only, no Neo4j import)
uv run python app/scripts/run_pipeline.py --skip-neo4j

# Phase 01+02+04 (skip validation)
uv run python app/scripts/run_pipeline.py --skip-validation
```

**Expected output (full pipeline, G-System reachable):**
```
── Phase 01: Syncing from G-System API ─────────────────────
   G-System sync + push confirmation complete
   Calendar data is always from mock (G-System endpoint pending)
── Phase 02: Building RDF ABox ──────────────────────────────
   Graph: 1199 triples (TBox + ABox)
── Phase 03: Validating RDF graph ───────────────────────────
── Phase 04: Importing to Neo4j ─────────────────────────────
   Imported — nodes=139 relationships=248
── Pipeline complete ─────────────────────────────────────────
```

**Failure behavior:**

| Phase | On failure |
|-------|-----------|
| Phase 01 (G-System sync) | `GSystemSyncError` — DB rolled back, pipeline stops |
| Phase 02 (ABox build) | `ABoxBuildError` — pipeline stops |
| Phase 03 (Validation) | `ValidationError` — graph cleared, no Neo4j import |
| Phase 04 (Neo4j) | Retry 3× with 1s/2s/4s backoff → `Neo4jImportError` |

---

## 5. Verify Results

### 5.1 PostgreSQL (DBeaver / psql)

```bash
psql $APS_DB_URL
```

```sql
-- Row counts per table
SELECT 'aps_item'            AS tbl, COUNT(*) FROM aps_item
UNION ALL SELECT 'aps_routing',        COUNT(*) FROM aps_routing
UNION ALL SELECT 'aps_operation',      COUNT(*) FROM aps_operation
UNION ALL SELECT 'aps_calendar_entry', COUNT(*) FROM aps_calendar_entry
UNION ALL SELECT 'aps_demand',         COUNT(*) FROM aps_demand
UNION ALL SELECT 'aps_item_process',   COUNT(*) FROM aps_item_process;

-- Check Item types distribution
SELECT asset_type, COUNT(*) FROM aps_item GROUP BY asset_type;

-- Verify work_time_hours is decimal hours (integer minutes ÷ 60)
SELECT gsystem_process_id, work_time_hours, setup_time_hours FROM aps_operation LIMIT 5;
-- Expected: 16.9167 for 1015 minutes

-- Check Routing → Operation links
SELECT r.routing_no, COUNT(o.id) AS op_count
FROM aps_routing r
LEFT JOIN aps_operation o ON o.routing_id = r.id
GROUP BY r.routing_no;
```

### 5.2 Neo4j

Open Neo4j Browser: `http://localhost:7474` (login with `APS_NEO4J_USER` / `APS_NEO4J_PASSWORD`)

```cypher
// Count nodes by label
MATCH (n) RETURN labels(n)[0] AS label, count(n) AS count ORDER BY label;

// Item → Routing → Operations
MATCH (i)-[:HAS_ROUTING]->(r)-[:HAS_OPERATION]->(op)
RETURN i.itemNo, r.routingNo, op.procSeq, op.procName, op.workTime
ORDER BY i.itemNo, op.procSeq;

// Operation sequence chain (production step order)
MATCH path = (op1:Operation)-[:IMMEDIATELY_PRECEDES*]->(op2:Operation)
WHERE NOT ()-[:IMMEDIATELY_PRECEDES]->(op1)
RETURN [n IN nodes(path) | n.procName] AS sequence;

// Demand → Item → BOM → Components
MATCH (d:Demand)-[:DEMANDS_ITEM]->(i)-[:HAS_BOM]->(bom)
      -[:HAS_BOM_COMPONENT]->(comp)-[:COMPONENT_ITEM]->(ci)
RETURN d.planNo, d.planQty, i.itemNo AS product,
       ci.itemNo AS component, comp.quantity;

// WorkCenter + Calendar shift count
MATCH (wc:WorkCenter)-[:HAS_CALENDAR]->(c:Calendar)-[:HAS_SHIFT]->(s:CalendarShift)
RETURN wc.workshopCd, wc.hourlyCapacity, count(s) AS shift_days;

// Visualize full graph (Neo4j Browser)
MATCH (n)-[r]->(m) RETURN n, r, m LIMIT 50;
```

---

## 6. Code Architecture

```
app/
├── models/
│   ├── input/                  # Phase 01: input domain models (public schema)
│   │   ├── item.py             # Item (aps_item)
│   │   ├── bom.py              # BOM, BOMComponent
│   │   ├── workcenter.py       # WorkCenter
│   │   ├── routing.py          # Routing, RoutingItem, Operation
│   │   ├── calendar.py         # CalendarEntry
│   │   ├── demand.py           # Demand
│   │   └── item_process.py     # ItemProcess (aps_item_process)
│   │       # NOTE: scheduler/solver removed — ScheduleRun/ScheduledOperation no longer exist
│   ├── output/                 # Result models (aps_result schema)
│   │   ├── plan_scenario.py    # PlanScenario
│   │   ├── plan_order.py       # PlanOrder, PlanOperation
│   │   ├── plan_shortage.py    # PlanShortage
│   │   ├── plan_utilization.py # PlanUtilization
│   │   ├── plan_evaluation.py  # PlanEvaluationSummary, Detail, Action
│   │   └── risk.py             # RiskResult
│   └── __init__.py             # re-exports all models
├── db/
│   └── database.py             # engine, SessionLocal
├── services/gsystem/           # Phase 01: G-System sync
│   ├── api_client.py           # GSystemClient — fetch 9 endpoints + push confirm
│   ├── db_syncer.py            # sync_all() — A/U/D upsert into Local DB
│   ├── calendar_db_syncer.py   # sync calendar from G-System DB directly
│   └── sync_service.py         # run_gsystem_sync() — used by API + pipeline
├── services/ontology/          # Phase 02+03
│   ├── namespace.py            # APS namespace + URI builders
│   ├── tbox.py                 # OWL TBox: 15 classes, 19 properties
│   ├── data_props.py           # OWL DatatypeProperties
│   ├── abox_builder.py         # Phase 02: Local DB → RDF triples
│   ├── rdf_validator.py        # Phase 03: OWL-RL + SHACL
│   └── shacl_shapes.py         # SHACL shapes
├── services/neo4j/             # Phase 04
│   └── graph_importer.py       # RDF → Neo4j MERGE (batch, with indexes)
├── scripts/
│   ├── seed_mock_data.py       # Seed Local DB (dev/testing)
│   ├── run_pipeline.py         # Orchestrator (Phase 01→04)
│   ├── dump_databases.py       # pg_dump + Neo4j export + rotation
│   └── export_ontology_ttl.py  # Export TBox → .ttl
└── config/
    ├── config.py               # pydantic_settings BaseSettings
    └── logger.py               # Centralized logging
```

### OWL TBox (schema)

**Classes (15):**
`Item` → `Product`, `SemiProduct`, `RawMaterial`
`BOM`, `BOMComponent`, `WorkCenter`, `Routing`, `Operation`
`Demand`, `Calendar`, `CalendarShift`
`ProcessType`, `RoutingType`, `DemandStatus`, `DayOfWeek`

**Object Properties (19):**

| Property | Domain → Range |
|----------|---------------|
| `hasBOM` | Item → BOM |
| `hasRouting` | Item → Routing |
| `hasOperation` | Routing → Operation |
| `immediatelyPrecedes` | Operation → Operation |
| `usesWorkCenter` | Operation → WorkCenter |
| `hasCalendar` | WorkCenter → Calendar |
| `hasShift` | Calendar → CalendarShift |
| `demandsItem` | Demand → Item |
| `componentItem` | BOMComponent → Item |
| ... | ... |

**OWL features:** disjoint classes, cardinality restrictions, inverse properties, `InverseFunctionalProperty`, property chain axiom (`plannedRouting ∘ routingOfItem ⊆ demandsItem`).

### ABox builder — execution order matters

```python
# app/services/ontology/abox_builder.py
item_by_id = _build_items(session, g)       # → index {db_id: URIRef}
wc_by_id   = _build_workcenters(session, g) # → index + creates shared Calendar node
             _build_calendar(session, g)    # CalendarShift nodes (1 per day)
             _build_routings(session, g, item_by_id)   # + Item↔Routing links
             _build_operations(session, g, wc_by_id)   # + immediatelyPrecedes chain
             _build_bom(session, g, item_by_id)
             _build_demands(session, g, item_by_id)
```

### URI convention

```
aps:Item/HEAD_07                      → Item (by itemNo)
aps:Routing/R001                      → Routing (by routing_no)
aps:Routing/id/42                     → Routing (fallback when routing_no is NULL)
aps:Operation/42/10                   → Operation (routing_gsystem_id / process_seq)
aps:Calendar/shared                   → Single shared Calendar for all WorkCenters
aps:Calendar/shared/shift/2024-01-01  → CalendarShift (1 per day)
```

---

## 7. G-System Sync (Phase 01)

### How it works

APS integrates with G-System via **HTTP API interface** — not direct DB access.
G-System exposes a set of `pending` endpoints that return records not yet confirmed by APS.
After APS saves data to its local DB, it calls a `push` endpoint to confirm receipt.

```
APS                                G-System
 │                                     │
 │  POST /xxx/aps/pending              │
 │ ──────────────────────────────────► │  returns records where ifRecvYn = false
 │ ◄────────────────────────────────── │
 │                                     │
 │  [save to APS DB]                   │
 │                                     │
 │  POST /xxx/aps/pushXxxInterface     │
 │ ──────────────────────────────────► │  sets ifRecvYn = true on those records
 │ ◄────────────────────────────────── │
```

### Protocol

```
For each of 9 active endpoints:
  1. POST /endpoint/aps/pending       → list of pending records (ifRecvYn=false)
  2. Sort records by "id" ASC         → G-System processing order
  3. Dispatch by ifStatus:
       "A" → INSERT
       "U" → UPDATE
       "D" → DELETE
  4. Commit APS DB
  5. POST /endpoint/aps/pushXxxInterface  with original array
     → G-System sets ifRecvYn=true (confirms APS received)
```

> **⚠️ DB Reset Warning:** If APS DB is dropped/reset, re-running the pipeline will only
> receive records that are still pending on G-System side (newly added/changed since last push).
> Records already confirmed (`ifRecvYn=true`) will NOT be returned again.
> To force a full re-sync, ask the G-System team to reset `if_recv_yn = 'N'` on their side.

### Active Endpoints

| # | Entity | DB Table | Upsert Key |
|---|--------|----------|-----------|
| 1 | Item | `aps_item` | `itemNo` (string) |
| 2 | Workshop | `aps_workcenter` | `workshopId` (int) |
| 3 | Process Master | *(in-memory index only)* | `processId` |
| 4 | Routing | `aps_routing` | `routingId` (int) |
| 5 | Routing Item | `aps_routing_item` | `(routingId, itemId)` |
| 6 | Routing Process | `aps_operation` | `(routingId, processSeq)` |
| 7 | BOM | `aps_bom` + `aps_bom_component` | `(upitemId, downitemId)` |
| 8 | Prod Plan | `aps_demand` | `planNo` (string) |
| 9 | Item Process | `aps_item_process` | `(itemId, procSno)` |
| — | Calendar | `aps_calendar_entry` | endpoint not yet open |

### Confirmed Field Mapping

| Entity | G-System field | DB column | Note |
|--------|---------------|-----------|------|
| Item | `itemId` | *(index key)* | G-System business integer ID |
| Item | `itemNo` | `item_no` | Upsert key |
| Item | `itemNm` | `item_name` | |
| Item | `spec` | `spec` | |
| Item | `assetTypeCdNm` | `asset_type` | "반제품"→"SemiProduct" etc. |
| Workshop | `workshopId` | `gsystem_id` | Business integer ID |
| Workshop | `workshopCd` | `workcenter_no` | |
| Workshop | `workshopNm` | `workcenter_name` | |
| Routing | `routingId` | `gsystem_id` | |
| Routing | `routingNo` | `routing_no` | nullable |
| Routing | `routingNm` | `routing_name` | |
| Routing Process | `workTime` | `work_time_hours` | Integer minutes ÷ 60 |
| Routing Process | `setupTime` | `setup_time_hours` | Integer minutes ÷ 60 |
| Routing Process | `workcenterId` | `workcenter_id` FK | |
| BOM | `upitemId` | `parent_item_id` FK | lowercase `i` |
| BOM | `downitemId` | `component_item_id` FK | lowercase `i` |
| BOM | `qty1` | `quantity` | |
| BOM | `bomSort` | `bom_seq` | |
| Prod Plan | `planNo` | `plan_no` | |
| Prod Plan | `delvDate` | `delivery_date` | (not `deliveryDate`) |
| Prod Plan | `statusCd` | `status_cd` | |

> Field names confirmed via curl against G-System mes_dev (2026-04-22).

### Calendar (direct DB)

Calendar endpoint `/cm/calendar/aps/pending` not yet open from G-System API.
As a workaround, APS queries the G-System DB directly via `GSYSTEM_DB_URL`:

```
G-System DB: mes_dev.cm_calendar
  → app/services/gsystem/calendar_db_syncer.py
  → aps_calendar table
```

Requires `GSYSTEM_DB_URL`, `GSYSTEM_DB_USER`, `GSYSTEM_DB_PASSWORD` in `.env`.
When the API endpoint opens, replace with the standard pending/push flow.

### Request / Response format

**Fetch pending (POST body):**
```json
{"ifType": "item"}          // entities with ifType
{}                          // routing_process, routing_item, item_process
```

**G-System response envelope:**
```json
{
  "statusCode": "000",      // "000" = success
  "message": "...",
  "result": [ {...}, ... ]  // array of records
}
```

**Push confirmation (POST body):** raw array from `result` — sent back unchanged.

---

## 8. Database Backup

```bash
# Dump PostgreSQL + Neo4j to backups/ (+ delete files > 60 days)
just backup

# Delete old backups only
just backup-clean
```

Backup files saved to `backups/` (gitignored):
- `backups/postgres_YYYYMMDD_HHMMSS.sql.gz`
- `backups/neo4j_YYYYMMDD_HHMMSS.json.gz`

Script: `app/scripts/dump_databases.py`

---

## 9. Open Questions

| # | Question | Impact | Status |
|---|----------|--------|--------|
| Q_enum1 | `routingTypeCd` "14681001/2" → which RoutingType named individual? | `hasRoutingType` link missing | Open |
| Q_enum2 | `statusCd` → which DemandStatus named individual? | `hasDemandStatus` link missing | Open |
| Q_calendar_format | `workDate` format (YYYYMMDD or ISO?) + `workHours` unit (minutes or hours)? | Calendar parse logic | Open — waiting for endpoint |
