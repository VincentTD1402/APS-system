"""APS ontology namespace and URI builder helpers.

Shared by tbox.py (TBox) and rdf_converter.py (ABox / instance data).
"""

from urllib.parse import quote
from rdflib import Namespace, URIRef

# Primary APS namespace
APS = Namespace("http://example.org/aps#")

# Ontology document URI
ONTOLOGY_URI = URIRef("http://example.org/aps/ontology")


def _slug(value: str) -> str:
    """URL-encode a string for safe use in a URI path segment.

    Encodes spaces, Korean characters, and other non-ASCII chars.
    Example: "THIN XIN CHAO HIHI" → "THIN%20XIN%20CHAO%20HIHI"
    """
    return quote(str(value), safe="-._~")


def item_uri(item_no: str) -> URIRef:
    return APS[f"Item/{_slug(item_no)}"]


def item_id_uri(gsystem_id: int) -> URIRef:
    """Fallback URI when only G-System internal id is available (BOM downitemId, Demand itemId)."""
    return APS[f"Item/id/{gsystem_id}"]


def bom_uri(up_item_no: str) -> URIRef:
    """BOM header URI — identified by parent itemNo."""
    return APS[f"BOM/{_slug(up_item_no)}"]


def bom_component_uri(up_item_no: str, down_item_id: int) -> URIRef:
    """BOMComponent (line) URI — one per child item in a BOM."""
    return APS[f"BOMComponent/{_slug(up_item_no)}/{down_item_id}"]


def workcenter_uri(workshop_cd: str) -> URIRef:
    return APS[f"WorkCenter/{_slug(workshop_cd)}"]


def routing_uri(routing_no: str) -> URIRef:
    return APS[f"Routing/{routing_no}"]


def operation_uri(proc_no: str) -> URIRef:
    return APS[f"Operation/{proc_no}"]


def demand_uri(plan_no: str) -> URIRef:
    return APS[f"Demand/{plan_no}"]


def calendar_uri(calendar_id: str) -> URIRef:
    return APS[f"Calendar/{calendar_id}"]


def calendar_shift_uri(calendar_id: str, shift_name: str) -> URIRef:
    return APS[f"Calendar/{calendar_id}/shift/{shift_name}"]


# ── DB-backed URI builders (Phase 01 Local DB → Phase 02 ABox) ───────────────

def routing_db_uri(gsystem_id: int, routing_no: str | None = None) -> URIRef:
    """Routing URI using routing_no when available, gsystem_id as fallback.

    routing_no is nullable in G-System (many routings have no business key).
    """
    key = routing_no if routing_no else f"id/{gsystem_id}"
    return APS[f"Routing/{key}"]


def operation_db_uri(routing_gsystem_id: int, process_seq: int) -> URIRef:
    """Operation URI using composite (routing_id, seq) — globally unique."""
    return APS[f"Operation/{routing_gsystem_id}/{process_seq}"]


def calendar_entry_shift_uri(work_date) -> URIRef:
    """CalendarShift URI for a single work date (one entry per day)."""
    return APS[f"Calendar/shared/shift/{work_date.isoformat()}"]
