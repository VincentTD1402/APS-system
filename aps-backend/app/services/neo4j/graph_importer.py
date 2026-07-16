"""APS Neo4j graph importer — Phase 04 of the APS pipeline.

Imports RDF ABox triples into Neo4j via Cypher MERGE statements.

Node strategy:
  - OWL class instance → Neo4j node with label = class name
  - Node id = URI fragment after namespace prefix (e.g. "Item/HEAD_07")
  - Literal data properties → Neo4j node properties

Relationship strategy:
  - ObjectProperty triple (s, p, o) → Neo4j relationship (s)-[:REL_TYPE]->(o)
  - All MERGEs are idempotent — safe to re-run

Performance:
  - Indexes on `id` property for all 15 node labels (created via _ensure_indexes)
  - Batched UNWIND MERGE for nodes (1 Cypher call per label, not per node)
  - Batched UNWIND MERGE for relationships (1 Cypher call per rel type, not per triple)

Config via app.config.settings:
    APS_NEO4J_URI       — e.g. bolt://localhost:7687
    APS_NEO4J_USER      — default: neo4j
    APS_NEO4J_PASSWORD  — required
    APS_NEO4J_DATABASE  — default: neo4j
"""

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.namespace import RDF, XSD

from ..ontology.namespace import APS

from app.config import get_logger

logger = get_logger(__name__)


_APS_PREFIX = str(APS)  # "http://example.org/aps#"

# Ordered by specificity — subclasses before parent (Product before Item)
_NODE_CLASSES = [
    "Product", "SemiProduct", "RawMaterial",
    "BOM", "BOMComponent",
    "WorkCenter", "Routing", "Operation",
    "Demand", "Calendar", "CalendarShift",
    "ProcessType", "RoutingType", "DemandStatus", "DayOfWeek",
]

# ObjectProperty local name → Neo4j relationship type
_REL_TYPE: dict[str, str] = {
    "demandsItem":        "DEMANDS_ITEM",
    "plannedRouting":     "PLANNED_ROUTING",
    "hasBOM":             "HAS_BOM",
    "producesItem":       "PRODUCES_ITEM",
    "hasBOMComponent":    "HAS_BOM_COMPONENT",
    "belongsToBOM":       "BELONGS_TO_BOM",
    "componentItem":      "COMPONENT_ITEM",
    "hasRouting":         "HAS_ROUTING",
    "routingOfItem":      "ROUTING_OF_ITEM",
    "hasOperation":       "HAS_OPERATION",
    "belongsToRouting":   "BELONGS_TO_ROUTING",
    "immediatelyPrecedes":"IMMEDIATELY_PRECEDES",
    "usesWorkCenter":     "USES_WORK_CENTER",
    "hasCalendar":        "HAS_CALENDAR",
    "hasShift":           "HAS_SHIFT",
    "hasProcessType":     "HAS_PROCESS_TYPE",
    "hasRoutingType":     "HAS_ROUTING_TYPE",
    "hasDemandStatus":    "HAS_DEMAND_STATUS",
    "hasShiftDay":        "HAS_SHIFT_DAY",
}


# ── Config ────────────────────────────────────────────────────────────────────

@dataclass
class Neo4jConfig:
    uri: str
    user: str
    password: str
    database: str = "neo4j"


# ── Importer ──────────────────────────────────────────────────────────────────

class Neo4jImporter:
    """Import RDF graph into Neo4j via Cypher MERGE.

    Usage:
        with Neo4jImporter(Neo4jConfig(...)) as importer:
            stats = importer.import_graph(g)
    """

    def __init__(self, config: Neo4jConfig) -> None:
        from neo4j import GraphDatabase
        self._driver = GraphDatabase.driver(config.uri, auth=(config.user, config.password))
        self._db = config.database

    def close(self) -> None:
        self._driver.close()

    def __enter__(self) -> "Neo4jImporter":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def import_graph(self, g: Graph) -> dict[str, int]:
        """Import all nodes and relationships from *g* into Neo4j.

        Returns {"nodes": <count>, "relationships": <count>}.
        """
        node_count = 0
        rel_count = 0
        with self._driver.session(database=self._db) as session:
            _ensure_indexes(session)
            for label in _NODE_CLASSES:
                node_count += _merge_nodes(session, g, label)
            rel_count = _merge_relationships(session, g)
        logger.info("import_graph: %d nodes, %d relationships", node_count, rel_count)
        return {"nodes": node_count, "relationships": rel_count}


# ── Internal helpers ──────────────────────────────────────────────────────────

def _ensure_indexes(session: Any) -> None:
    """Create indexes on `id` property for all node labels (idempotent).

    Uses CREATE INDEX IF NOT EXISTS — safe to call on every import run.
    These indexes speed up MATCH (n {id: $id}) lookups in _merge_relationships.
    """
    for label in _NODE_CLASSES:
        session.run(f"CREATE INDEX IF NOT EXISTS FOR (n:`{label}`) ON (n.id)")
    logger.info("Ensured indexes for %d node labels", len(_NODE_CLASSES))


def _node_id(uri: URIRef) -> str:
    """Extract node id from APS URI (strip namespace prefix)."""
    return str(uri)[len(_APS_PREFIX):]


def _py_value(literal: Literal) -> Any:
    """Convert rdflib Literal to Python primitive for Neo4j driver."""
    dt = literal.datatype
    if dt in (XSD.integer, XSD.int, XSD.nonNegativeInteger, XSD.long):
        return int(literal)
    if dt in (XSD.decimal, XSD.float, XSD.double):
        return float(literal)
    if dt == XSD.boolean:
        return bool(literal)
    return str(literal)  # xsd:string, xsd:date, xsd:time — store as string


def _merge_nodes(session: Any, g: Graph, label: str) -> int:
    """MERGE all instances of *label* into Neo4j using batched UNWIND.

    Collects all nodes of the given label into a batch list, then sends
    a single UNWIND Cypher call instead of one call per node.
    Returns node count merged.
    """
    batch: list[dict[str, Any]] = []
    for subj in g.subjects(RDF.type, APS[label]):
        if isinstance(subj, BNode):
            continue  # OWL restriction blank nodes — skip
        node_id = _node_id(subj)
        props: dict[str, Any] = {"id": node_id, "uri": str(subj)}
        for pred, obj in g.predicate_objects(subj):
            if str(pred).startswith(_APS_PREFIX) and isinstance(obj, Literal):
                props[str(pred)[len(_APS_PREFIX):]] = _py_value(obj)
        batch.append({"id": node_id, "props": props})

    if batch:
        session.run(
            f"UNWIND $batch AS row "
            f"MERGE (n:`{label}` {{id: row.id}}) SET n += row.props",
            batch=batch,
        )
    logger.debug("  %s: %d nodes (batched)", label, len(batch))
    return len(batch)


def _merge_relationships(session: Any, g: Graph) -> int:
    """MERGE all APS ObjectProperty triples as Neo4j relationships.

    Groups triples by relationship type, then sends one UNWIND Cypher
    call per rel type instead of one call per triple.
    Returns total relationship count merged.
    """
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for subj, pred, obj in g:
        # Only APS-namespaced subject → object triples
        if not isinstance(subj, URIRef) or not str(subj).startswith(_APS_PREFIX):
            continue
        if not isinstance(obj, URIRef) or not str(obj).startswith(_APS_PREFIX):
            continue
        pred_local = str(pred)[len(_APS_PREFIX):]
        rel_type = _REL_TYPE.get(pred_local)
        if not rel_type:
            continue
        grouped[rel_type].append({"a": _node_id(subj), "b": _node_id(obj)})

    count = 0
    for rel_type, pairs in grouped.items():
        session.run(
            f"UNWIND $pairs AS row "
            f"MATCH (a {{id: row.a}}), (b {{id: row.b}}) "
            f"MERGE (a)-[:`{rel_type}`]->(b)",
            pairs=pairs,
        )
        count += len(pairs)
        logger.debug("  %s: %d relationships (batched)", rel_type, len(pairs))

    logger.debug("  relationships total: %d", count)
    return count
