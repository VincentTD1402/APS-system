"""APS RDF validator — Phase 03 of the APS pipeline.

Validates the merged TBox+ABox graph in two steps:
  1. owlrl.DeductiveClosure — OWL-RL reasoning + consistency check
  2. pyshacl.validate      — SHACL data-level constraints

Usage:
    from app.services.ontology.rdf_validator import validate
    result = validate(graph)
    if not result.valid:
        for msg in result.violations:
            print(msg)
"""

from dataclasses import dataclass, field

from rdflib import Graph

from app.config import get_logger

logger = get_logger(__name__)


@dataclass
class ValidationResult:
    valid: bool
    violations: list[str] = field(default_factory=list)


def validate(g: Graph, run_shacl: bool = True) -> ValidationResult:
    """Run OWL-RL reasoning + optional SHACL validation on *g*.

    Args:
        g: merged TBox+ABox graph (modified in-place by owlrl expansion)
        run_shacl: also run pyshacl validation (default True)

    Returns ValidationResult(valid, violations).
    """
    violations: list[str] = []

    # ── Step 1: OWL-RL reasoning ──────────────────────────────────────────────
    # Expands inferred triples (inverses, chains, subclass propagation).
    # Raises on class inconsistency (e.g. individual declared as two disjoint classes).
    try:
        import owlrl
        owlrl.DeductiveClosure(owlrl.OWLRL_Semantics).expand(g)
        logger.info("OWL-RL reasoning complete: %d triples total", len(g))
    except Exception as exc:
        violations.append(f"OWL-RL inconsistency: {exc}")
        logger.error("owlrl failed: %s", exc)

    # ── Step 2: SHACL validation ──────────────────────────────────────────────
    # Checks data-level constraints that OWL cannot enforce (Open World Assumption).
    # Runs AFTER owlrl so inferred triples (e.g. inverse properties) are available.
    if run_shacl:
        try:
            import pyshacl
            from .shacl_shapes import get_shacl_graph

            conforms, _, report_text = pyshacl.validate(
                g,
                shacl_graph=get_shacl_graph(),
                inference="none",       # already expanded above
                abort_on_first=False,   # collect all violations
                meta_shacl=False,
            )
            if not conforms:
                _parse_report(report_text, violations)
            logger.info("SHACL validation: conforms=%s", conforms)
        except Exception as exc:
            violations.append(f"SHACL error: {exc}")
            logger.error("pyshacl failed: %s", exc)

    return ValidationResult(valid=len(violations) == 0, violations=violations)


def _parse_report(report_text: str, out: list[str]) -> None:
    """Extract per-violation messages from pyshacl text report."""
    current: list[str] = []
    for line in report_text.splitlines():
        s = line.strip()
        if s.startswith("Constraint Violation"):
            if current:
                out.append(" | ".join(current))
            current = [s]
        elif s.startswith(("sh:resultMessage", "sh:focusNode", "sh:value")):
            current.append(s)
    if current:
        out.append(" | ".join(current))
    # fallback: full report if parser found nothing
    if not out:
        out.append(report_text.strip())
