"""APS RDF ABox builder — Phase 02 of the APS pipeline.

Reads from the APS Local DB (SQLAlchemy session) and converts each entity
into RDF ABox triples added to the provided TBox Graph.

Previously blocked links now resolved:
  - Routing → Item  (via aps_routing_item join table)
  - Routing → Operation → WorkCenter  (via aps_routing_step.routing_id FK)
  - Operation.immediatelyPrecedes chain  (derived from process_seq ordering)
  - WorkCenter → Calendar  (shared calendar from aps_calendar)

Usage:
    from app.services.ontology.tbox import get_ontology_graph
    from app.services.ontology.abox_builder import build_abox
    from app.db.database import SessionLocal

    g = get_ontology_graph()
    with SessionLocal() as session:
        build_abox(session, g)
"""

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF, XSD
from sqlalchemy.orm import Session

from app.config import get_logger
from app.models import BOMComponent, CalendarEntry, Demand, Item, RoutingStep, Routing, WorkCenter
from app.models import BOM

from .namespace import (
    APS,
    bom_component_uri, bom_uri, calendar_entry_shift_uri, calendar_uri,
    demand_uri, item_uri, operation_db_uri, routing_db_uri, workcenter_uri,
)

logger = get_logger(__name__)

# Shared calendar IRI — all WorkCenters reference the same cm_calendar
_SHARED_CALENDAR_URI = calendar_uri("shared")

# Python weekday() index → DayOfWeek NamedIndividual
_DOW = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


# ── Private builders ──────────────────────────────────────────────────────────

def _build_items(session: Session, g: Graph) -> dict[int, URIRef]:
    """Add Item instances. Returns db_id → URI index used by BOM and Demand."""
    index: dict[int, URIRef] = {}
    items = session.query(Item).all()
    for item in items:
        subclass = item.asset_type or "RawMaterial"
        uri = item_uri(item.item_no)
        g.add((uri, RDF.type, APS[subclass]))
        g.add((uri, APS["itemNo"],   Literal(item.item_no, datatype=XSD.string)))
        if item.item_name:
            g.add((uri, APS["itemName"], Literal(item.item_name, datatype=XSD.string)))
        if item.spec:
            g.add((uri, APS["spec"],     Literal(item.spec, datatype=XSD.string)))
        index[item.id] = uri
    logger.info("build_items: %d items", len(items))
    return index


def _build_bom(session: Session, g: Graph, item_by_id: dict[int, URIRef]) -> None:
    """Add BOM headers and BOMComponent lines."""
    bom_count = 0
    for bom in session.query(BOM).all():
        parent_uri = item_by_id.get(bom.parent_item_id)
        if not parent_uri:
            continue
        bom_u = bom_uri(session.get(Item, bom.parent_item_id).item_no)
        g.add((bom_u, RDF.type, APS["BOM"]))
        g.add((bom_u, APS["producesItem"], parent_uri))
        g.add((parent_uri, APS["hasBOM"], bom_u))
        for comp in session.query(BOMComponent).filter_by(bom_id=bom.id).all():
            comp_item_uri = item_by_id.get(comp.component_item_id)
            if not comp_item_uri:
                continue
            comp_u = bom_component_uri(
                session.get(Item, bom.parent_item_id).item_no, comp.component_item_id
            )
            g.add((comp_u, RDF.type, APS["BOMComponent"]))
            g.add((comp_u, APS["belongsToBOM"], bom_u))
            g.add((bom_u, APS["hasBOMComponent"], comp_u))
            g.add((comp_u, APS["componentItem"], comp_item_uri))
            if comp.quantity is not None:
                g.add((comp_u, APS["quantity"], Literal(float(comp.quantity), datatype=XSD.decimal)))
            if comp.bom_seq is not None:
                g.add((comp_u, APS["bomSeq"], Literal(comp.bom_seq, datatype=XSD.integer)))
        bom_count += 1
    logger.info("build_bom: %d BOM headers", bom_count)


def _build_workcenters(session: Session, g: Graph) -> dict[int, URIRef]:
    """Add WorkCenter instances and link each to shared Calendar."""
    g.add((_SHARED_CALENDAR_URI, RDF.type, APS["Calendar"]))
    g.add((_SHARED_CALENDAR_URI, APS["calendarId"],   Literal("shared", datatype=XSD.string)))
    g.add((_SHARED_CALENDAR_URI, APS["calendarName"], Literal("Shared Work Calendar", datatype=XSD.string)))

    index: dict[int, URIRef] = {}
    for wc in session.query(WorkCenter).all():
        uri = workcenter_uri(wc.workcenter_no)
        g.add((uri, RDF.type, APS["WorkCenter"]))
        g.add((uri, APS["workshopCd"],   Literal(wc.workcenter_no, datatype=XSD.string)))
        if wc.workcenter_name:
            g.add((uri, APS["workshopName"], Literal(wc.workcenter_name, datatype=XSD.string)))
        if wc.std_capa is not None:
            g.add((uri, APS["hourlyCapacity"], Literal(float(wc.std_capa), datatype=XSD.decimal)))
        # Link every WorkCenter to the shared calendar
        g.add((uri, APS["hasCalendar"], _SHARED_CALENDAR_URI))
        index[wc.id] = uri
    logger.info("build_workcenters: %d workcenters", len(index))
    return index


def _build_calendar(session: Session, g: Graph) -> None:
    """Add CalendarShift instances (one per work date) to the shared Calendar."""
    entries = session.query(CalendarEntry).order_by(CalendarEntry.work_date).all()
    for entry in entries:
        shift_uri = calendar_entry_shift_uri(entry.work_date)
        dow_ind = APS[_DOW[entry.work_date.weekday()]]
        g.add((shift_uri, RDF.type, APS["CalendarShift"]))
        g.add((_SHARED_CALENDAR_URI, APS["hasShift"], shift_uri))
        g.add((shift_uri, APS["hasShiftDay"], dow_ind))
        g.add((shift_uri, APS["workDate"],  Literal(entry.work_date, datatype=XSD.date)))
        g.add((shift_uri, APS["workHours"], Literal(float(entry.work_hours), datatype=XSD.decimal)))
        g.add((shift_uri, APS["isHoliday"], Literal(entry.is_holiday, datatype=XSD.boolean)))
    logger.info("build_calendar: %d calendar entries", len(entries))


def _build_routings(session: Session, g: Graph, item_by_id: dict[int, URIRef]) -> None:
    """Add Routing instances and routing→item links (Q_routing_item resolved)."""
    for routing in session.query(Routing).all():
        uri = routing_db_uri(routing.gsystem_id, routing.routing_no)
        g.add((uri, RDF.type, APS["Routing"]))
        if routing.routing_no:
            g.add((uri, APS["routingNo"],   Literal(routing.routing_no, datatype=XSD.string)))
        if routing.routing_name:
            g.add((uri, APS["routingName"], Literal(routing.routing_name, datatype=XSD.string)))
        if routing.std_capa is not None:
            g.add((uri, APS["stdCapacity"], Literal(int(routing.std_capa), datatype=XSD.integer)))

        # Routing → Item links (previously blocked Q_routing_item, now resolved)
        for ri in routing.routing_items:
            item_uri_ref = item_by_id.get(ri.item_id)
            if item_uri_ref:
                g.add((item_uri_ref, APS["hasRouting"],  uri))
                g.add((uri, APS["routingOfItem"], item_uri_ref))
    logger.info("build_routings: %d routings", session.query(Routing).count())


def _build_operations(session: Session, g: Graph, wc_by_id: dict[int, URIRef]) -> None:
    """Add Operation instances with routing and workcenter links.

    Also builds immediatelyPrecedes chain between consecutive ops in a routing.
    (Previously blocked Q_process_routing — now resolved via routing_id FK.)
    """
    added = 0
    for routing in session.query(Routing).all():
        routing_uri_ref = routing_db_uri(routing.gsystem_id, routing.routing_no)
        ops = sorted(routing.routing_steps, key=lambda o: o.process_seq)
        prev_uri: URIRef | None = None
        for op in ops:
            uri = operation_db_uri(routing.gsystem_id, op.process_seq)
            g.add((uri, RDF.type, APS["Operation"]))
            g.add((uri, APS["procSeq"], Literal(op.process_seq, datatype=XSD.integer)))
            if op.proc_no:
                g.add((uri, APS["procNo"], Literal(op.proc_no, datatype=XSD.string)))
            if op.proc_name:
                g.add((uri, APS["procName"], Literal(op.proc_name, datatype=XSD.string)))
            if op.work_time_hours is not None:
                g.add((uri, APS["workTime"],  Literal(float(op.work_time_hours), datatype=XSD.decimal)))
            if op.setup_time_hours is not None:
                g.add((uri, APS["setupTime"], Literal(float(op.setup_time_hours), datatype=XSD.decimal)))
            # Routing ↔ Operation links
            g.add((routing_uri_ref, APS["hasOperation"],    uri))
            g.add((uri, APS["belongsToRouting"], routing_uri_ref))
            # Operation → WorkCenter link
            if op.workcenter_id and op.workcenter_id in wc_by_id:
                g.add((uri, APS["usesWorkCenter"], wc_by_id[op.workcenter_id]))
            # Sequential chain
            if prev_uri:
                g.add((prev_uri, APS["immediatelyPrecedes"], uri))
            prev_uri = uri
            added += 1
    logger.info("build_operations: %d operations", added)


def _build_demands(session: Session, g: Graph, item_by_id: dict[int, URIRef]) -> None:
    """Add Demand instances with item links."""
    for demand in session.query(Demand).all():
        uri = demand_uri(demand.plan_no)
        g.add((uri, RDF.type, APS["Demand"]))
        g.add((uri, APS["planNo"], Literal(demand.plan_no, datatype=XSD.string)))
        if demand.plan_qty is not None:
            g.add((uri, APS["planQty"], Literal(float(demand.plan_qty), datatype=XSD.decimal)))
        if demand.plan_date:
            g.add((uri, APS["planDate"], Literal(demand.plan_date, datatype=XSD.date)))
        if demand.delivery_date:
            g.add((uri, APS["deliveryDate"], Literal(demand.delivery_date, datatype=XSD.date)))
        item_uri_ref = item_by_id.get(demand.item_id)
        if item_uri_ref:
            g.add((uri, APS["demandsItem"], item_uri_ref))
        if getattr(demand, "routing_id", None) and demand.routing_id is not None:
            r_obj = session.get(Routing, demand.routing_id)
            if r_obj:
                routing_uri_ref = routing_db_uri(r_obj.gsystem_id, r_obj.routing_no)
                g.add((uri, APS["plannedRouting"], routing_uri_ref))
    logger.info("build_demands: %d demands", session.query(Demand).count())


# ── Public entry point ────────────────────────────────────────────────────────

def build_abox(session: Session, g: Graph) -> Graph:
    """Build ABox triples from APS Local DB into *g* (TBox graph passed in).

    Args:
        session: SQLAlchemy session connected to APS Local DB
        g: TBox graph (from get_ontology_graph()) — ABox triples added in-place

    Returns the same graph with ABox triples merged in.
    """
    item_by_id = _build_items(session, g)
    wc_by_id   = _build_workcenters(session, g)
    _build_calendar(session, g)
    _build_routings(session, g, item_by_id)
    _build_operations(session, g, wc_by_id)
    _build_bom(session, g, item_by_id)
    _build_demands(session, g, item_by_id)
    return g
