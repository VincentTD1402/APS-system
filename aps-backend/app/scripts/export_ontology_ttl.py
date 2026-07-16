"""Export APS TBox ontology (OWL + SHACL) to Turtle (.ttl) file for visualization."""

import sys
from pathlib import Path

from rdflib.term import BNode

# Allow running from project root: uv run python app/scripts/export_ontology_ttl.py
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from rdflib import Graph
from rdflib.namespace import OWL, RDF, SH

from app.services.ontology.tbox import get_ontology_graph
from app.services.ontology.shacl_shapes import get_shacl_graph

OUTPUT = Path(__file__).parent.parent.parent / "ontology" / "aps_tbox.ttl"


def _copy_bnode_closure(g_src: Graph, g_dst: Graph, bnode: BNode) -> None:
    """Recursively copy all triples reachable from a blank node into g_dst.

    Handles nested RDF lists (owl:propertyChainAxiom) and OWL restriction chains
    that are more than one level deep.
    """
    for bp, bo in g_src.predicate_objects(bnode):
        g_dst.add((bnode, bp, bo))
        if isinstance(bo, BNode):
            _copy_bnode_closure(g_src, g_dst, bo)


def _sorted_turtle(g: Graph) -> str:
    """Serialize graph to Turtle with logical section order:
    prefixes → ontology declaration → classes → object props → data props → individuals → SHACL.
    rdflib default is alphabetical which mixes all types together.
    """
    # Collect subjects by type
    classes     = set(g.subjects(RDF.type, OWL.Class))
    obj_props   = set(g.subjects(RDF.type, OWL.ObjectProperty))
    dat_props   = set(g.subjects(RDF.type, OWL.DatatypeProperty))
    individuals = set(g.subjects(RDF.type, OWL.NamedIndividual))
    shacl_shapes = set(g.subjects(RDF.type, SH.NodeShape))

    sections = [
        ("# ── Classes ──────────────────────────────────────────────────────────────────", classes),
        ("# ── Object Properties ────────────────────────────────────────────────────────", obj_props),
        ("# ── Data Properties ──────────────────────────────────────────────────────────", dat_props),
        ("# ── Named Individuals (Enums) ────────────────────────────────────────────────", individuals),
        ("# ── SHACL Shapes ─────────────────────────────────────────────────────────────", shacl_shapes),
    ]

    lines = [
        "@prefix aps: <http://example.org/aps#> .",
        "@prefix owl: <http://www.w3.org/2002/07/owl#> .",
        "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
        "@prefix sh: <http://www.w3.org/ns/shacl#> .",
        "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
        "",
        "# ── Ontology Declaration ──────────────────────────────────────────────────────",
        "<http://example.org/aps/ontology> a owl:Ontology ;",
        '    rdfs:label "APS Manufacturing Ontology"@en .',
        "",
    ]

    for header, subjects in sections:
        if not subjects:
            continue
        lines.append(header)
        # Serialize each subject as its own mini-graph for clean block output
        for subj in sorted(subjects, key=str):
            mini = Graph()
            mini.bind("aps", "http://example.org/aps#")
            mini.bind("owl", str(OWL))
            mini.bind("rdfs", "http://www.w3.org/2000/01/rdf-schema#")
            mini.bind("sh", str(SH))
            mini.bind("xsd", "http://www.w3.org/2001/XMLSchema#")
            for p, o in g.predicate_objects(subj):
                mini.add((subj, p, o))
                # Recursively include all nested blank node triples
                # (handles OWL restrictions, RDF lists for propertyChainAxiom, SHACL constraints)
                if isinstance(o, BNode):
                    _copy_bnode_closure(g, mini, o)
            block = mini.serialize(format="turtle")
            # Strip prefix lines — already at top
            body = "\n".join(
                ln for ln in block.splitlines()
                if not ln.startswith("@prefix") and ln.strip()
            )
            lines.append(body)
        lines.append("")

    return "\n".join(lines)


# ── Build combined graph (OWL TBox + SHACL shapes) ───────────────────────────

tbox = get_ontology_graph()
shacl = get_shacl_graph()

# Merge both graphs into one for export
g = tbox + shacl

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(_sorted_turtle(g))

classes_count   = len(list(g.subjects(RDF.type, OWL.Class)))
obj_props_count = len(list(g.subjects(RDF.type, OWL.ObjectProperty)))
dat_props_count = len(list(g.subjects(RDF.type, OWL.DatatypeProperty)))
shacl_count     = len(list(g.subjects(RDF.type, SH.NodeShape)))

print(f"Exported: {OUTPUT}")
print(f"  {classes_count} classes | {obj_props_count} object props | {dat_props_count} data props | {shacl_count} SHACL shapes | {len(g)} triples")
