# Neo4j Cypher Query Reference

> Open Neo4j Browser at `http://localhost:7474` (login: `APS_NEO4J_USER` / `APS_NEO4J_PASSWORD`)
> Paste queries below directly into the query bar.

---

## 0. Index Setup

Indexes được pipeline tạo tự động (`_ensure_indexes`) mỗi lần import — idempotent, safe to re-run.

Để tạo thủ công hoặc kiểm tra:

```cypher
// Tạo indexes cho tất cả 15 node labels
CREATE INDEX IF NOT EXISTS FOR (n:Product) ON (n.id);
CREATE INDEX IF NOT EXISTS FOR (n:SemiProduct) ON (n.id);
CREATE INDEX IF NOT EXISTS FOR (n:RawMaterial) ON (n.id);
CREATE INDEX IF NOT EXISTS FOR (n:BOM) ON (n.id);
CREATE INDEX IF NOT EXISTS FOR (n:BOMComponent) ON (n.id);
CREATE INDEX IF NOT EXISTS FOR (n:WorkCenter) ON (n.id);
CREATE INDEX IF NOT EXISTS FOR (n:Routing) ON (n.id);
CREATE INDEX IF NOT EXISTS FOR (n:Operation) ON (n.id);
CREATE INDEX IF NOT EXISTS FOR (n:Demand) ON (n.id);
CREATE INDEX IF NOT EXISTS FOR (n:Calendar) ON (n.id);
CREATE INDEX IF NOT EXISTS FOR (n:CalendarShift) ON (n.id);
CREATE INDEX IF NOT EXISTS FOR (n:ProcessType) ON (n.id);
CREATE INDEX IF NOT EXISTS FOR (n:RoutingType) ON (n.id);
CREATE INDEX IF NOT EXISTS FOR (n:DemandStatus) ON (n.id);
CREATE INDEX IF NOT EXISTS FOR (n:DayOfWeek) ON (n.id);
```

```cypher
// Kiểm tra indexes hiện có (phải thấy 15 indexes APS)
SHOW INDEXES WHERE labelsOrTypes IS NOT NULL
RETURN name, labelsOrTypes, properties, state
ORDER BY labelsOrTypes;
```

---

## 1. Health Check

```cypher
// Count all nodes by label
MATCH (n) RETURN labels(n)[0] AS label, count(n) AS count ORDER BY label;
```

```cypher
// Count all relationship types
MATCH ()-[r]->() RETURN type(r) AS rel_type, count(r) AS count ORDER BY rel_type;
```

```cypher
// Quick summary: total nodes + relationships
MATCH (n) WITH count(n) AS nodes
MATCH ()-[r]->() RETURN nodes, count(r) AS relationships;
```

---

## 2. Visualize Graph (Neo4j Browser)

```cypher
// Full graph — limit 100 to avoid lag
MATCH (n)-[r]->(m) RETURN n, r, m LIMIT 100
```

```cypher
// Item → Routing → Operation → WorkCenter flow
MATCH path = (i)-[:HAS_ROUTING]->(r)-[:HAS_OPERATION]->(op)-[:USES_WORK_CENTER]->(wc)
RETURN path
```

```cypher
// Demand → Item → BOM → Components flow
MATCH path = (d:Demand)-[:DEMANDS_ITEM]->(i)-[:HAS_BOM]->(bom)-[:HAS_BOM_COMPONENT]->(comp)
RETURN path
```

```cypher
// Operation sequence chain (production step order)
MATCH path = (op1:Operation)-[:IMMEDIATELY_PRECEDES*]->(op2:Operation)
RETURN path LIMIT 20
```

```cypher
// WorkCenter → Calendar → Shifts
MATCH path = (wc:WorkCenter)-[:HAS_CALENDAR]->(c:Calendar)-[:HAS_SHIFT]->(s:CalendarShift)
RETURN path LIMIT 30
```

---

## 3. Items

```cypher
// All items with type
MATCH (i) WHERE i:Product OR i:SemiProduct OR i:RawMaterial
RETURN labels(i)[0] AS type, i.itemNo, i.itemName
ORDER BY type, i.itemNo;
```

```cypher
// Items that have a Routing (manufactured items)
MATCH (i)-[:HAS_ROUTING]->(r)
RETURN labels(i)[0] AS type, i.itemNo, r.routingNo, r.routingName;
```

```cypher
// Items WITHOUT a Routing (raw materials or missing link)
MATCH (i) WHERE i:Product OR i:SemiProduct OR i:RawMaterial
AND NOT (i)-[:HAS_ROUTING]->()
RETURN labels(i)[0] AS type, i.itemNo, i.itemName;
```

---

## 4. BOM

```cypher
// All BOMs with component count
MATCH (bom:BOM)-[:HAS_BOM_COMPONENT]->(comp)
RETURN bom.id AS bom, count(comp) AS component_count;
```

```cypher
// Full BOM explosion: product → components
MATCH (i)-[:HAS_BOM]->(bom)-[:HAS_BOM_COMPONENT]->(comp)-[:COMPONENT_ITEM]->(ci)
RETURN i.itemNo AS product, ci.itemNo AS component,
       labels(ci)[0] AS component_type, comp.quantity
ORDER BY i.itemNo, comp.bomSeq;
```

---

## 5. Routing & Operations

```cypher
// All routings with operation count
MATCH (r:Routing)
OPTIONAL MATCH (r)-[:HAS_OPERATION]->(op)
RETURN r.routingNo, r.routingName, count(op) AS op_count
ORDER BY r.routingNo;
```

```cypher
// Operations per routing with work time
MATCH (r:Routing)-[:HAS_OPERATION]->(op)
RETURN r.routingNo, op.procSeq, op.procName, op.workTime, op.setupTime
ORDER BY r.routingNo, op.procSeq;
```

```cypher
// Operation sequence chains (start → end of each routing)
MATCH path = (op1:Operation)-[:IMMEDIATELY_PRECEDES*]->(op2:Operation)
WHERE NOT ()-[:IMMEDIATELY_PRECEDES]->(op1)
  AND NOT (op2)-[:IMMEDIATELY_PRECEDES]->()
RETURN [n IN nodes(path) | n.procName] AS sequence,
       length(path) + 1 AS step_count;
```

```cypher
// Operations assigned to each WorkCenter
MATCH (op:Operation)-[:USES_WORK_CENTER]->(wc:WorkCenter)
RETURN wc.workshopCd, wc.workshopName, count(op) AS op_count,
       collect(op.procName) AS operations
ORDER BY wc.workshopCd;
```

---

## 6. WorkCenter & Calendar

```cypher
// WorkCenter capacity summary
MATCH (wc:WorkCenter)
RETURN wc.workshopCd, wc.workshopName, wc.hourlyCapacity
ORDER BY wc.workshopCd;
```

```cypher
// Calendar shift count per WorkCenter
MATCH (wc:WorkCenter)-[:HAS_CALENDAR]->(c:Calendar)-[:HAS_SHIFT]->(s:CalendarShift)
RETURN wc.workshopCd, count(s) AS shift_days,
       min(s.workDate) AS from_date, max(s.workDate) AS to_date;
```

```cypher
// Working hours by day of week
MATCH (s:CalendarShift)-[:HAS_SHIFT_DAY]->(dow:DayOfWeek)
WHERE s.isHoliday = false
RETURN dow.id AS day, avg(s.workHours) AS avg_hours, count(s) AS days
ORDER BY day;
```

```cypher
// Holiday entries
MATCH (s:CalendarShift)
WHERE s.isHoliday = true
RETURN s.workDate, s.workHours
ORDER BY s.workDate;
```

---

## 7. Demand

```cypher
// All demands with item info
MATCH (d:Demand)-[:DEMANDS_ITEM]->(i)
RETURN d.planNo, d.planQty, d.planDate, d.deliveryDate,
       i.itemNo AS item, labels(i)[0] AS item_type
ORDER BY d.planDate;
```

```cypher
// Demands with full production path (item → routing → first operation)
MATCH (d:Demand)-[:DEMANDS_ITEM]->(i)-[:HAS_ROUTING]->(r)-[:HAS_OPERATION]->(op)
WHERE NOT ()-[:IMMEDIATELY_PRECEDES]->(op)
RETURN d.planNo, d.planQty, i.itemNo, r.routingNo, op.procName AS first_op
ORDER BY d.planDate;
```

---

## 8. Data Quality Checks

```cypher
// Operations with no WorkCenter assigned (scheduling blocker)
MATCH (op:Operation)
WHERE NOT (op)-[:USES_WORK_CENTER]->()
RETURN op.id, op.procName, op.procSeq;
```

```cypher
// BOMComponents with quantity = 0 or missing
MATCH (comp:BOMComponent)
WHERE comp.quantity IS NULL OR comp.quantity = 0
RETURN comp.id, comp.quantity;
```

```cypher
// Routings with no operations (empty routing)
MATCH (r:Routing)
WHERE NOT (r)-[:HAS_OPERATION]->()
RETURN r.routingNo, r.routingName;
```

```cypher
// Items that are Product/SemiProduct but have no BOM
MATCH (i) WHERE i:Product OR i:SemiProduct
AND NOT (i)-[:HAS_BOM]->()
RETURN labels(i)[0] AS type, i.itemNo, i.itemName;
```

```cypher
// Demands with no item link (orphan demands)
MATCH (d:Demand)
WHERE NOT (d)-[:DEMANDS_ITEM]->()
RETURN d.planNo, d.planQty;
```

---

## 9. Cleanup (use with caution)

```cypher
// Delete all nodes and relationships (full reset)
MATCH (n) DETACH DELETE n;
```
