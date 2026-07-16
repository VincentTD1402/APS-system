"""APS OWL data property definitions.

Called once by tbox.py during TBox construction.
Each entity section adds (property, domain, xsd:range) triples.
"""

from rdflib import Graph, Literal
from rdflib.namespace import OWL, RDF, RDFS, XSD

from .namespace import APS


def _dp(graph: Graph, prop: str, domain_class: str, xsd_type, label: str) -> None:
    """Register one owl:DatatypeProperty triple set."""
    p = APS[prop]
    graph.add((p, RDF.type, OWL.DatatypeProperty))
    graph.add((p, RDFS.domain, APS[domain_class]))
    graph.add((p, RDFS.range, xsd_type))
    graph.add((p, RDFS.label, Literal(label, lang="en")))


def add_data_properties(graph: Graph) -> None:
    """Add all APS data properties to *graph* (TBox only)."""

    # ── Item ──────────────────────────────────────────────────────────────────
    # assetType removed: use subclass (Product/SemiProduct/RawMaterial) for semantic classification
    # bomYn removed: hasBOM ObjectProperty makes this redundant
    # useYn removed: boolean flags encode business logic; handle at application layer
    _dp(graph, "itemNo",   "Item", XSD.string, "Item Number")
    _dp(graph, "itemName", "Item", XSD.string, "Item Name")
    _dp(graph, "spec",     "Item", XSD.string, "Specification")

    # ── BOM (header — parent link expressed via Item --hasBOM--> BOM) ─────────
    # No data props on BOM header; line-level data lives on BOMComponent nodes

    # ── BOMComponent (one node per BOM line, carries qty + effectivity) ───────
    _dp(graph, "quantity",       "BOMComponent", XSD.decimal, "Required Quantity")
    _dp(graph, "bomSeq",         "BOMComponent", XSD.integer, "Sequence in BOM")
    _dp(graph, "revisionNo",     "BOMComponent", XSD.integer, "Revision Number")
    _dp(graph, "effectiveStart", "BOMComponent", XSD.date,    "Effective Start Date")
    _dp(graph, "effectiveEnd",   "BOMComponent", XSD.date,    "Effective End Date")

    # ── WorkCenter ────────────────────────────────────────────────────────────
    _dp(graph, "workshopCd",      "WorkCenter", XSD.string,  "Workshop Code")
    _dp(graph, "workshopName",    "WorkCenter", XSD.string,  "Workshop Name")
    _dp(graph, "workshopGroup",   "WorkCenter", XSD.string,  "Workshop Group Code")
    _dp(graph, "line",            "WorkCenter", XSD.integer, "Production Line Number")
    _dp(graph, "hourlyCapacity",  "WorkCenter", XSD.decimal, "Standard Hourly Capacity")

    # ── Routing ───────────────────────────────────────────────────────────────
    # workCalendar removed: replaced by usesCalendar ObjectProperty (Routing → Calendar)
    # routingType removed: replaced by hasRoutingType ObjectProperty (Routing → RoutingType)
    _dp(graph, "routingNo",   "Routing", XSD.string,  "Routing Number")
    _dp(graph, "routingName", "Routing", XSD.string,  "Routing Name")
    _dp(graph, "stdCapacity", "Routing", XSD.integer, "Standard Capacity")

    # ── Operation ─────────────────────────────────────────────────────────────
    # procType removed: replaced by hasProcessType ObjectProperty (Operation → ProcessType)
    # nextOperation removed: derive order via SPARQL ORDER BY procSeq
    # outsourceYn removed: use hasProcessType → OutsourceProcess instead
    _dp(graph, "procNo",    "Operation", XSD.string,  "Process Number")
    _dp(graph, "procName",  "Operation", XSD.string,  "Process Name")
    _dp(graph, "procSeq",   "Operation", XSD.integer, "Process Sequence")
    # Standard times in decimal hours (converted from G-System HHMM format)
    _dp(graph, "workTime",  "Operation", XSD.decimal, "Standard Work Time (hours)")
    _dp(graph, "setupTime", "Operation", XSD.decimal, "Standard Setup Time (hours)")

    # ── Demand ────────────────────────────────────────────────────────────────
    # itemId removed: demandsItem ObjectProperty links directly to Item node
    # statusCode removed: replaced by hasDemandStatus ObjectProperty (Demand → DemandStatus)
    _dp(graph, "planNo",       "Demand", XSD.string,  "Production Plan Number")
    _dp(graph, "planQty",      "Demand", XSD.decimal, "Planned Quantity")
    _dp(graph, "planDate",     "Demand", XSD.date,    "Plan Date")
    _dp(graph, "deliveryDate", "Demand", XSD.date,    "Delivery Date")

    # ── Calendar (APS-internal, no G-System source) ───────────────────────────
    # shiftDay removed: replaced by hasShiftDay ObjectProperty (CalendarShift → DayOfWeek)
    _dp(graph, "calendarId",   "Calendar",      XSD.string,  "Calendar ID")
    _dp(graph, "calendarName", "Calendar",      XSD.string,  "Calendar Name")
    _dp(graph, "shiftStart",   "CalendarShift", XSD.time,    "Shift Start Time")
    _dp(graph, "shiftEnd",     "CalendarShift", XSD.time,    "Shift End Time")
    # Date-level fields populated from cm_calendar (G-System work calendar)
    _dp(graph, "workDate",     "CalendarShift", XSD.date,    "Work Date")
    _dp(graph, "workHours",    "CalendarShift", XSD.decimal, "Available Work Hours")
    _dp(graph, "isHoliday",    "CalendarShift", XSD.boolean, "Is Holiday")
