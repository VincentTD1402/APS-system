"""APS SHACL validation shapes.

Complements tbox.py (OWL TBox) with data-level constraints that OWL alone
cannot enforce under the Open World Assumption.

Usage:
    from app.services.ontology.shacl_shapes import get_shacl_graph
    shapes_graph = get_shacl_graph()
    # pass to pyshacl.validate(data_graph, shacl_graph=shapes_graph)
"""

from functools import lru_cache

from rdflib import RDF, RDFS, Graph, Literal, Namespace, URIRef
from rdflib.namespace import SH, XSD

from .namespace import APS, ONTOLOGY_URI

_SH = SH  # alias to avoid shadowing built-in


def _build_shacl_graph() -> Graph:
    g = Graph()
    g.bind("aps", APS)
    g.bind("sh", SH)
    g.bind("xsd", XSD)

    # ── Shape 1: plannedRouting must belong to the demanded item ─────────────
    # If Demand has plannedRouting → that Routing must be linked from demandsItem via hasRouting
    _add_sparql_shape(
        g,
        shape_uri=APS["DemandWithRoutingShape"],
        target_class=APS["Demand"],
        message="plannedRouting must be a routing of the demanded item (via hasRouting).",
        sparql="""
            PREFIX aps: <http://example.org/aps#>
            SELECT $this WHERE {
                $this aps:plannedRouting ?r .
                $this aps:demandsItem ?i .
                FILTER NOT EXISTS { ?i aps:hasRouting ?r . }
            }
        """,
        comment="If plannedRouting is set, it must be one of the item's hasRouting values.",
    )

    # ── Shape 2: procSeq required, integer, unique per routing ───────────────
    _add_property_shape(
        g,
        shape_uri=APS["OperationProcSeqShape"],
        target_class=APS["Operation"],
        path=APS["procSeq"],
        datatype=XSD.integer,
        min_count=1,
        max_count=1,
        name="procSeq",
        comment="procSeq required, integer, exactly one per Operation.",
    )
    # Uniqueness: no two operations in the same routing share a procSeq
    _add_sparql_shape(
        g,
        shape_uri=APS["OperationSequenceUniquenessShape"],
        target_class=APS["Operation"],
        message="Duplicate procSeq within the same routing.",
        sparql="""
            PREFIX aps: <http://example.org/aps#>
            SELECT $this WHERE {
                $this aps:belongsToRouting ?route .
                $this aps:procSeq ?seq .
                ?other aps:belongsToRouting ?route .
                ?other aps:procSeq ?seq .
                FILTER ( ?other != $this )
            }
        """,
        comment="procSeq must be unique per Routing.",
    )

    # ── Shape 3: immediatelyPrecedes — same routing, seq diff = 1 ────────────
    _add_sparql_shape(
        g,
        shape_uri=APS["ImmediatePrecedenceSameRoutingShape"],
        target_class=APS["Operation"],
        message="immediatelyPrecedes: both operations must belong to the same routing.",
        sparql="""
            PREFIX aps: <http://example.org/aps#>
            SELECT $this WHERE {
                $this aps:immediatelyPrecedes ?next .
                $this aps:belongsToRouting ?r1 .
                ?next aps:belongsToRouting ?r2 .
                FILTER ( ?r1 != ?r2 )
            }
        """,
        comment="immediatelyPrecedes must link operations within the same Routing.",
    )
    _add_sparql_shape(
        g,
        shape_uri=APS["ImmediatePrecedenceSeqShape"],
        target_class=APS["Operation"],
        message="immediatelyPrecedes: successor procSeq must be strictly greater than predecessor procSeq.",
        sparql="""
            PREFIX aps: <http://example.org/aps#>
            SELECT $this WHERE {
                $this aps:immediatelyPrecedes ?next .
                $this aps:procSeq ?s1 .
                ?next aps:procSeq ?s2 .
                FILTER ( ?s2 <= ?s1 )
            }
        """,
        comment=(
            "immediatelyPrecedes must respect increasing procSeq ordering. "
            "G-System numbers steps in gaps (10, 20, 30...) to allow inserting "
            "steps later, so only strict ordering is enforced, not a fixed +1 delta."
        ),
    )

    # ── Shape 4: BOMComponent quantity must be strictly positive ─────────────
    _add_property_shape(
        g,
        shape_uri=APS["BOMQuantityShape"],
        target_class=APS["BOMComponent"],
        path=APS["quantity"],
        min_exclusive=0,
        name="quantity",
        comment="BOM component quantity must be > 0 when stated.",
    )

    # ── Shape 5: Demand planQty must be strictly positive ────────────────────
    _add_sparql_shape(
        g,
        shape_uri=APS["DemandPlanQtyShape"],
        target_class=APS["Demand"],
        message="planQty must be greater than zero when present.",
        sparql="""
            PREFIX aps: <http://example.org/aps#>
            PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
            SELECT $this WHERE {
                $this aps:planQty ?q .
                FILTER ( ?q <= 0 )
            }
        """,
        comment="Scheduling a zero or negative quantity is meaningless.",
    )

    return g


# ── Internal helpers ──────────────────────────────────────────────────────────

def _add_sparql_shape(
    g: Graph,
    shape_uri: URIRef,
    target_class: URIRef,
    message: str,
    sparql: str,
    comment: str,
) -> None:
    from rdflib import BNode
    g.add((shape_uri, RDF.type, SH.NodeShape))
    g.add((shape_uri, RDFS.comment, Literal(comment, lang="en")))
    g.add((shape_uri, SH.targetClass, target_class))

    constraint = BNode()
    g.add((shape_uri, SH.sparql, constraint))
    g.add((constraint, RDF.type, SH.SPARQLConstraint))
    g.add((constraint, SH.message, Literal(message, lang="en")))
    g.add((constraint, SH.select, Literal(sparql.strip())))


def _add_property_shape(
    g: Graph,
    shape_uri: URIRef,
    target_class: URIRef,
    path: URIRef,
    name: str,
    comment: str,
    datatype=None,
    min_count: int | None = None,
    max_count: int | None = None,
    min_exclusive=None,
) -> None:
    from rdflib import BNode
    g.add((shape_uri, RDF.type, SH.NodeShape))
    g.add((shape_uri, RDFS.comment, Literal(comment, lang="en")))
    g.add((shape_uri, SH.targetClass, target_class))

    prop = BNode()
    g.add((shape_uri, SH.property, prop))
    g.add((prop, SH.path, path))
    g.add((prop, SH.name, Literal(name, lang="en")))
    if datatype is not None:
        g.add((prop, SH.datatype, datatype))
    if min_count is not None:
        g.add((prop, SH.minCount, Literal(min_count, datatype=XSD.integer)))
    if max_count is not None:
        g.add((prop, SH.maxCount, Literal(max_count, datatype=XSD.integer)))
    if min_exclusive is not None:
        g.add((prop, SH.minExclusive, Literal(min_exclusive, datatype=XSD.decimal)))


@lru_cache(maxsize=1)
def get_shacl_graph() -> Graph:
    """Return singleton SHACL shapes graph (built once, cached)."""
    return _build_shacl_graph()
