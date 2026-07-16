"""APS OWL TBox: class hierarchy, object properties, and ontology graph singleton.

Pipeline role: defines the schema that rdf_converter.py populates with ABox triples,
which rdf_validator.py then reasons over before Neo4j import.
"""

from functools import lru_cache

from rdflib import BNode, Graph, Literal
from rdflib.collection import Collection
from rdflib.namespace import OWL, RDF, RDFS, XSD

from .data_props import add_data_properties
from .namespace import APS, ONTOLOGY_URI

# ── Class definitions ─────────────────────────────────────────────────────────

_CLASSES = [
    # (local_name, subclass_of_or_None, label_en, label_ko)
    ("Item",          None,         "Item",                "품목"),
    ("Product",       "Item",       "Product",             "완제품"),
    ("SemiProduct",   "Item",       "Semi-Product",        "반제품"),
    ("RawMaterial",   "Item",       "Raw Material",        "원자재"),
    ("BOM",           None,         "Bill of Materials",   "자재명세"),
    # Intermediate node carrying quantity per BOM line (avoids qty on BOM directly)
    ("BOMComponent",  None,         "BOM Component Line",  "BOM 구성 행"),
    ("WorkCenter",    None,         "Work Center",         "작업장"),
    ("Routing",       None,         "Routing",             "공정 경로"),
    ("Operation",     None,         "Operation",           "공정"),
    ("Demand",        None,         "Demand",              "수요"),
    ("Calendar",      None,         "Calendar",            "캘린더"),
    ("CalendarShift", None,         "Calendar Shift",      "근무 교대"),
    # Enum classes — replace free-text string fields
    ("ProcessType",   None,         "Process Type",        "공정 유형"),
    ("RoutingType",   None,         "Routing Type",        "경로 유형"),
    ("DemandStatus",  None,         "Demand Status",       "수요 상태"),
    ("DayOfWeek",     None,         "Day of Week",         "요일"),
]

# ── Named individuals (enums) ─────────────────────────────────────────────────

# ProcessType values — from G-System field procGb (confirm with Lead for full list)
_PROCESS_TYPE_INDIVIDUALS = [
    # (local_name, label_en, label_ko)
    ("VirtualProcess",    "Virtual Process",    "가상"),
    ("InternalProcess",   "Internal Process",   "사내"),
    ("OutsourceProcess",  "Outsource Process",  "외주"),
]

# RoutingType and DemandStatus individuals: pending confirmation from Lead (Q_enum1, Q_enum2)

_DAY_OF_WEEK_INDIVIDUALS = [
    # (local_name, label_en, label_ko)
    ("Monday",    "Monday",    "월요일"),
    ("Tuesday",   "Tuesday",   "화요일"),
    ("Wednesday", "Wednesday", "수요일"),
    ("Thursday",  "Thursday",  "목요일"),
    ("Friday",    "Friday",    "금요일"),
    ("Saturday",  "Saturday",  "토요일"),
    ("Sunday",    "Sunday",    "일요일"),
]

# ── Object property definitions ───────────────────────────────────────────────

_OBJECT_PROPS = [
    # (local_name, domain, range, label_en)
    # Core flow: Demand → Item → Routing/BOM
    ("demandsItem",        "Demand",       "Item",          "Demands Item"),
    ("plannedRouting",     "Demand",       "Routing",       "Planned Routing For Demand"),  # optional; chain axiom enforces same item
    ("hasBOM",             "Item",         "BOM",           "Has BOM"),
    ("producesItem",       "BOM",          "Item",          "Produces Item"),       # inverse of hasBOM
    # BOM → BOMComponent → Item
    ("hasBOMComponent",    "BOM",          "BOMComponent",  "Has BOM Component"),
    ("belongsToBOM",       "BOMComponent", "BOM",           "Belongs To BOM"),      # inverse of hasBOMComponent
    ("componentItem",      "BOMComponent", "Item",          "Component Item"),
    # Item → Routing → Operation → WorkCenter → Calendar
    ("hasRouting",         "Item",         "Routing",       "Has Routing"),         # InverseFunctional — see below
    ("routingOfItem",      "Routing",      "Item",          "Routing Of Item"),     # inverse of hasRouting
    ("hasOperation",       "Routing",      "Operation",     "Has Operation"),
    ("belongsToRouting",   "Operation",    "Routing",       "Belongs To Routing"),  # inverse of hasOperation
    ("immediatelyPrecedes","Operation",    "Operation",     "Immediately Precedes"),# explicit sequence edge
    ("usesWorkCenter",     "Operation",    "WorkCenter",    "Uses Work Center"),
    ("hasCalendar",        "WorkCenter",   "Calendar",      "Has Calendar"),
    ("hasShift",           "Calendar",     "CalendarShift", "Has Shift"),
    # Enum ObjectProperties (replace free-text string fields)
    ("hasProcessType",     "Operation",    "ProcessType",   "Has Process Type"),
    ("hasRoutingType",     "Routing",      "RoutingType",   "Has Routing Type"),
    ("hasDemandStatus",    "Demand",       "DemandStatus",  "Has Demand Status"),
    ("hasShiftDay",        "CalendarShift","DayOfWeek",     "Has Shift Day"),
]


def _build_ontology() -> Graph:
    """Construct the APS TBox graph (classes + properties + named individuals)."""
    g = Graph()
    g.bind("aps", APS)
    g.bind("owl", OWL)
    g.bind("rdfs", RDFS)

    # Ontology declaration
    g.add((ONTOLOGY_URI, RDF.type, OWL.Ontology))
    g.add((ONTOLOGY_URI, RDFS.label, Literal("APS Manufacturing Ontology", lang="en")))

    # Classes
    for name, parent, label_en, label_ko in _CLASSES:
        cls = APS[name]
        g.add((cls, RDF.type, OWL.Class))
        g.add((cls, RDFS.label, Literal(label_en, lang="en")))
        g.add((cls, RDFS.label, Literal(label_ko, lang="ko")))
        if parent:
            g.add((cls, RDFS.subClassOf, APS[parent]))

    # Named individuals for ProcessType enum
    for name, label_en, label_ko in _PROCESS_TYPE_INDIVIDUALS:
        ind = APS[name]
        g.add((ind, RDF.type, OWL.NamedIndividual))
        g.add((ind, RDF.type, APS["ProcessType"]))
        g.add((ind, RDFS.label, Literal(label_en, lang="en")))
        g.add((ind, RDFS.label, Literal(label_ko, lang="ko")))

    # Named individuals for DayOfWeek enum
    for name, label_en, label_ko in _DAY_OF_WEEK_INDIVIDUALS:
        ind = APS[name]
        g.add((ind, RDF.type, OWL.NamedIndividual))
        g.add((ind, RDF.type, APS["DayOfWeek"]))
        g.add((ind, RDFS.label, Literal(label_en, lang="en")))
        g.add((ind, RDFS.label, Literal(label_ko, lang="ko")))

    # Object properties
    for name, domain, range_, label_en in _OBJECT_PROPS:
        prop = APS[name]
        g.add((prop, RDF.type, OWL.ObjectProperty))
        g.add((prop, RDFS.domain, APS[domain]))
        g.add((prop, RDFS.range, APS[range_]))
        g.add((prop, RDFS.label, Literal(label_en, lang="en")))

    # producesItem is inverse of hasBOM (bidirectional declaration)
    g.add((APS["producesItem"], OWL.inverseOf, APS["hasBOM"]))
    g.add((APS["hasBOM"], OWL.inverseOf, APS["producesItem"]))

    # belongsToRouting is inverse of hasOperation
    g.add((APS["belongsToRouting"], OWL.inverseOf, APS["hasOperation"]))

    # belongsToBOM is inverse of hasBOMComponent
    g.add((APS["belongsToBOM"], OWL.inverseOf, APS["hasBOMComponent"]))

    # routingOfItem is inverse of hasRouting
    g.add((APS["routingOfItem"], OWL.inverseOf, APS["hasRouting"]))

    # hasRouting is InverseFunctional: one Routing IRI can only attach to one Item
    g.add((APS["hasRouting"], RDF.type, OWL.InverseFunctionalProperty))

    # componentItem and immediatelyPrecedes are Irreflexive + Asymmetric
    g.add((APS["immediatelyPrecedes"], RDF.type, OWL.IrreflexiveProperty))
    g.add((APS["immediatelyPrecedes"], RDF.type, OWL.AsymmetricProperty))

    # Property chain: plannedRouting o routingOfItem => demandsItem
    # Ensures a Demand's plannedRouting must belong to the same Item as demandsItem.
    # OWL 2 RDF mapping: superProperty owl:propertyChainAxiom (p1 p2)
    chain_list = BNode()
    Collection(g, chain_list, [APS["plannedRouting"], APS["routingOfItem"]])
    g.add((APS["demandsItem"], OWL.propertyChainAxiom, chain_list))

    # Data properties (delegated to data_props module)
    add_data_properties(g)

    # OWL constraints
    _add_constraints(g)

    return g


def _add_constraints(g: Graph) -> None:
    """Add OWL axioms: functional properties + cardinality restrictions + business rules."""

    # Business key data properties: Functional (each individual has at most one value)
    key_props = ["itemNo", "workshopCd", "routingNo", "procNo", "planNo", "calendarId"]
    for prop in key_props:
        g.add((APS[prop], RDF.type, OWL.FunctionalProperty))

    # ── Cardinality: BOM ──────────────────────────────────────────────────────

    # BOM must belong to exactly one Item (not null, not shared)
    r_bom_item = BNode()
    g.add((r_bom_item, RDF.type, OWL.Restriction))
    g.add((r_bom_item, OWL.onProperty, APS["producesItem"]))
    g.add((r_bom_item, OWL.cardinality, Literal(1, datatype=XSD.nonNegativeInteger)))
    g.add((APS["BOM"], RDFS.subClassOf, r_bom_item))

    # ── Cardinality: BOMComponent ─────────────────────────────────────────────

    # BOMComponent must belong to exactly one BOM (no orphan components)
    r_comp_bom = BNode()
    g.add((r_comp_bom, RDF.type, OWL.Restriction))
    g.add((r_comp_bom, OWL.onProperty, APS["belongsToBOM"]))
    g.add((r_comp_bom, OWL.cardinality, Literal(1, datatype=XSD.nonNegativeInteger)))
    g.add((APS["BOMComponent"], RDFS.subClassOf, r_comp_bom))

    # BOMComponent must link to exactly one Item
    r_comp_item = BNode()
    g.add((r_comp_item, RDF.type, OWL.Restriction))
    g.add((r_comp_item, OWL.onProperty, APS["componentItem"]))
    g.add((r_comp_item, OWL.cardinality, Literal(1, datatype=XSD.nonNegativeInteger)))
    g.add((APS["BOMComponent"], RDFS.subClassOf, r_comp_item))

    # BOMComponent must have exactly one quantity
    r_comp_qty = BNode()
    g.add((r_comp_qty, RDF.type, OWL.Restriction))
    g.add((r_comp_qty, OWL.onProperty, APS["quantity"]))
    g.add((r_comp_qty, OWL.cardinality, Literal(1, datatype=XSD.nonNegativeInteger)))
    g.add((APS["BOMComponent"], RDFS.subClassOf, r_comp_qty))

    # ── Disjoint classes ──────────────────────────────────────────────────────

    # Item subclasses are mutually exclusive
    g.add((APS["Product"],     OWL.disjointWith, APS["SemiProduct"]))
    g.add((APS["Product"],     OWL.disjointWith, APS["RawMaterial"]))
    g.add((APS["SemiProduct"], OWL.disjointWith, APS["RawMaterial"]))

    # Top-level classes are completely disjoint from each other and from Item hierarchy
    top_level = [
        "BOM", "BOMComponent", "WorkCenter", "Routing", "Operation",
        "Demand", "Calendar", "CalendarShift", "ProcessType", "RoutingType", "DemandStatus", "DayOfWeek",
    ]
    for i, a in enumerate(top_level):
        for b in top_level[i + 1:]:
            g.add((APS[a], OWL.disjointWith, APS[b]))
            g.add((APS[b], OWL.disjointWith, APS[a]))  # explicit bidirectional for complete TTL output
        g.add((APS[a], OWL.disjointWith, APS["Item"]))
        g.add((APS["Item"], OWL.disjointWith, APS[a]))

    # ── Existential restrictions (someValuesFrom) ─────────────────────────────

    # BOM must have at least one BOMComponent (empty BOM is meaningless)
    r_bom = BNode()
    g.add((r_bom, RDF.type, OWL.Restriction))
    g.add((r_bom, OWL.onProperty, APS["hasBOMComponent"]))
    g.add((r_bom, OWL.someValuesFrom, APS["BOMComponent"]))
    g.add((APS["BOM"], RDFS.subClassOf, r_bom))

    # Routing must have at least one Operation
    r_routing = BNode()
    g.add((r_routing, RDF.type, OWL.Restriction))
    g.add((r_routing, OWL.onProperty, APS["hasOperation"]))
    g.add((r_routing, OWL.someValuesFrom, APS["Operation"]))
    g.add((APS["Routing"], RDFS.subClassOf, r_routing))

    # Demand must reference at least one Item (data-level checks handled by SHACL)
    r_demand = BNode()
    g.add((r_demand, RDF.type, OWL.Restriction))
    g.add((r_demand, OWL.onProperty, APS["demandsItem"]))
    g.add((r_demand, OWL.someValuesFrom, APS["Item"]))
    g.add((APS["Demand"], RDFS.subClassOf, r_demand))

    # Operation must have at least one WorkCenter (no machine = cannot schedule)
    r_operation = BNode()
    g.add((r_operation, RDF.type, OWL.Restriction))
    g.add((r_operation, OWL.onProperty, APS["usesWorkCenter"]))
    g.add((r_operation, OWL.someValuesFrom, APS["WorkCenter"]))
    g.add((APS["Operation"], RDFS.subClassOf, r_operation))

    # Operation must belong to at least one Routing (orphan operation is invalid)
    r_op_routing = BNode()
    g.add((r_op_routing, RDF.type, OWL.Restriction))
    g.add((r_op_routing, OWL.onProperty, APS["belongsToRouting"]))
    g.add((r_op_routing, OWL.someValuesFrom, APS["Routing"]))
    g.add((APS["Operation"], RDFS.subClassOf, r_op_routing))

    # Operation must have exactly one procSeq (sequence is required for scheduling order)
    r_op_seq = BNode()
    g.add((r_op_seq, RDF.type, OWL.Restriction))
    g.add((r_op_seq, OWL.onProperty, APS["procSeq"]))
    g.add((r_op_seq, OWL.cardinality, Literal(1, datatype=XSD.nonNegativeInteger)))
    g.add((APS["Operation"], RDFS.subClassOf, r_op_seq))

    # Product and SemiProduct must have at least one Routing (manufactured items need a production route)
    # RawMaterial is excluded: purchased materials have no in-plant routing
    for manufactured_class in ("Product", "SemiProduct"):
        r_mfg = BNode()
        g.add((r_mfg, RDF.type, OWL.Restriction))
        g.add((r_mfg, OWL.onProperty, APS["hasRouting"]))
        g.add((r_mfg, OWL.someValuesFrom, APS["Routing"]))
        g.add((APS[manufactured_class], RDFS.subClassOf, r_mfg))

    # WorkCenter must have at least one Calendar (no calendar = cannot schedule)
    r_wc = BNode()
    g.add((r_wc, RDF.type, OWL.Restriction))
    g.add((r_wc, OWL.onProperty, APS["hasCalendar"]))
    g.add((r_wc, OWL.someValuesFrom, APS["Calendar"]))
    g.add((APS["WorkCenter"], RDFS.subClassOf, r_wc))

    # ── Irreflexive + Asymmetric: componentItem ───────────────────────────────
    # An item cannot be a component of itself (prevents direct circular BOM)
    g.add((APS["componentItem"], RDF.type, OWL.IrreflexiveProperty))
    g.add((APS["componentItem"], RDF.type, OWL.AsymmetricProperty))


@lru_cache(maxsize=1)
def get_ontology_graph() -> Graph:
    """Return the singleton APS TBox graph (built once, cached)."""
    return _build_ontology()
