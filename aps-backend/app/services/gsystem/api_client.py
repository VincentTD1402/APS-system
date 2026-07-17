"""G-System API client — Phase 01 of the APS pipeline.

Fetches pending records from 9 entity endpoints, then pushes confirmation
so G-System can set ifRecvYn=true.

Config via app.config.settings:
    GSYSTEM_BASE_URL  — e.g. http://gsystem.internal
    GSYSTEM_API_KEY   — optional bearer / API key header value
    GSYSTEM_TIMEOUT   — seconds per request (default: 30)
    GSYSTEM_RETRIES   — retry attempts on failure (default: 3)
"""

import time
from dataclasses import dataclass
from typing import Any
import httpx

from app.config import get_logger

logger = get_logger(__name__)

_SUCCESS_CODE = "000"

# ── Endpoint registry ────────────────────────────────────────────────────────
# (path, ifType or None) — None means send empty body {}

_ENDPOINTS: dict[str, tuple[str, str | None]] = {
    "item":             ("/cm/item/aps/pending",                              "item"),
    "workshop":         ("/cm/workPlaceMng/aps/pending",                     "workshop"),
    "bom":              ("/cm/BOMMng/aps/pending",                           "bom"),
    "routing":          ("/pd/routingMng/aps/pending",                       "routing"),
    "process":          ("/pd/processMng/aps/pending",                       "process"),
    "prod_plan":        ("/pd/prodplan/aps/pending",                         "prodplan"),
    "routing_process":  ("/pd/routingMng/aps/routingProcess/pending",        None),
    "routing_item":     ("/pd/routingMng/aps/routingItem/pending",           None),
    "item_process":     ("/pd/itemProcess/aps/pending",                      None),
    "calendar":         ("/sy/calendar/aps/pending",                         "calendar"),
    "stock":            ("/lg/lgstock/aps/pending",                          None),
    "customer":         ("/cm/customerMng/aps/pending",                      "customer"),
    # skipped: equipment (/pd/equipmentMasterInfo) — not in APS
}

_PUSH_ENDPOINTS: dict[str, str] = {
    "item":             "/cm/item/aps/pushItemInterface",
    "workshop":         "/cm/workPlaceMng/aps/pushWorkshopInterface",
    "routing":          "/pd/routingMng/aps/pushRoutingInterface",
    "bom":              "/cm/BOMMng/aps/pushBomInterface",
    "process":          "/pd/processMng/aps/pushProcessInterface",
    "prod_plan":        "/pd/prodplan/aps/pushProdPlanInterface",
    "routing_process":  "/pd/routingMng/aps/routingProcess/pushRoutingProcessInterface",
    "routing_item":     "/pd/routingMng/aps/routingItem/pushRoutingItemInterface",
    "item_process":     "/pd/itemProcess/aps/pushItemProcessInterface",
    "calendar":         "/sy/calendar/aps/pushCalendarInterface",
    "stock":            "/lg/lgstock/aps/pushStockInterface",
    "customer":         "/cm/customerMng/aps/pushCustomerInterface",
}


# ── Config ────────────────────────────────────────────────────────────────────

@dataclass
class GSystemConfig:
    base_url: str
    api_key: str = ""
    timeout: float = 30.0
    retries: int = 3
    all_data: bool = False  # testing only — adds allDataYn="Y" to every request body


# ── Client ────────────────────────────────────────────────────────────────────

class GSystemClient:
    """Synchronous HTTP client for G-System APS endpoints.

    Usage:
        with GSystemClient(GSystemConfig(...)) as client:
            data = client.fetch_all()
    """

    def __init__(self, config: GSystemConfig) -> None:
        self._cfg = config
        headers: dict[str, str] = {"Accept": "application/json", "Content-Type": "application/json"}
        if config.api_key:
            headers["X-API-Key"] = config.api_key
        self._http = httpx.Client(
            base_url=config.base_url,
            headers=headers,
            timeout=config.timeout,
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "GSystemClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # ── Internal ──────────────────────────────────────────────────────────────

    def _post(self, key: str) -> list[dict[str, Any]]:
        """POST with exponential-backoff retry; returns result list."""
        path, body = _ENDPOINTS[key]
        if isinstance(body, str):
            body = {"type": body}

        if body is None:
            body = {}

        if self._cfg.all_data:
            body = {**body, "allDataYn": True}
        last_exc: Exception | None = None
        for attempt in range(1, self._cfg.retries + 1):
            try:
                r = self._http.post(path, json=body)
                r.raise_for_status()
                return _parse_envelope(r.json(), path)
            except Exception as exc:
                last_exc = exc
                logger.warning("attempt %d/%d failed for %s: %s", attempt, self._cfg.retries, path, exc)
                if attempt < self._cfg.retries:
                    time.sleep(2 ** (attempt - 1))
        raise RuntimeError(f"All {self._cfg.retries} attempts failed for {path}") from last_exc

    def _post_push(self, path: str, records: list[dict[str, Any]]) -> None:
        """Push raw records array back to G-System for confirmation (ifRecvYn=true)."""
        last_exc: Exception | None = None
        for attempt in range(1, self._cfg.retries + 1):
            try:
                r = self._http.post(path, json=records)
                r.raise_for_status()
                return
            except Exception as exc:
                last_exc = exc
                logger.warning("push attempt %d/%d failed for %s: %s", attempt, self._cfg.retries, path, exc)
                if attempt < self._cfg.retries:
                    time.sleep(2 ** (attempt - 1))
        raise RuntimeError(f"All {self._cfg.retries} push attempts failed for {path}") from last_exc

    def submit_purchase_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Submit a purchase order request to G-System (/pu/puOrderReq/aps/save)."""
        path = "/pu/puOrderReq/aps/save"
        last_exc: Exception | None = None
        for attempt in range(1, self._cfg.retries + 1):
            try:
                r = self._http.post(path, json=payload)
                r.raise_for_status()
                return r.json()
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "purchase order attempt %d/%d failed for %s: %s",
                    attempt,
                    self._cfg.retries,
                    path,
                    exc,
                )
                if attempt < self._cfg.retries:
                    time.sleep(2 ** (attempt - 1))
        raise RuntimeError(f"All {self._cfg.retries} purchase order attempts failed for {path}") from last_exc

    # ── Fetch methods — pending queue (delta sync) ────────────────────────────

    def fetch_items(self)            -> list[dict[str, Any]]: return self._post("item")
    def fetch_workcenters(self)      -> list[dict[str, Any]]: return self._post("workshop")
    def fetch_bom(self)              -> list[dict[str, Any]]: return self._post("bom")
    def fetch_routings(self)         -> list[dict[str, Any]]: return self._post("routing")
    def fetch_processes(self)        -> list[dict[str, Any]]: return self._post("process")
    def fetch_demands(self)          -> list[dict[str, Any]]: return self._post("prod_plan")
    def fetch_routing_processes(self)-> list[dict[str, Any]]: return self._post("routing_process")
    def fetch_routing_items(self)    -> list[dict[str, Any]]: return self._post("routing_item")
    def fetch_item_processes(self)   -> list[dict[str, Any]]: return self._post("item_process")

    def fetch_calendar(self)  -> list[dict[str, Any]]: return self._post("calendar")
    def fetch_stock(self)     -> list[dict[str, Any]]: return self._post("stock")
    def fetch_customers(self) -> list[dict[str, Any]]: return self._post("customer")

    # ── Fetch methods — by-routing lookup (full load, not pending-based) ──────

    def fetch_routing_process_list(self, routing_id: int) -> list[dict[str, Any]]:
        """Fetch all process steps for a routing (pd_if_aps_routing_process).

        Returns full list regardless of ifRecvYn status.
        Fields: routingId, processId, processSeq, workcenterId, procNm, useYn
        Note: no workTime at this level — use fetch_item_process_list_by_routing for item-level times.
        """
        path = "/pd/routingMng/aps/routingProcessList"
        last_exc: Exception | None = None
        for attempt in range(1, self._cfg.retries + 1):
            try:
                r = self._http.post(path, json={"routingId": routing_id})
                r.raise_for_status()
                return _parse_envelope(r.json(), path)
            except Exception as exc:
                last_exc = exc
                logger.warning("attempt %d/%d failed for %s routingId=%s: %s", attempt, self._cfg.retries, path, routing_id, exc)
                if attempt < self._cfg.retries:
                    time.sleep(2 ** (attempt - 1))
        raise RuntimeError(f"All {self._cfg.retries} attempts failed for {path} routingId={routing_id}") from last_exc

    def fetch_routing_item_list(self, routing_id: int) -> list[dict[str, Any]]:
        """Fetch all items assigned to a routing (pd_if_aps_routing_item).

        Returns full list regardless of ifRecvYn status.
        Fields: routingId, itemId, itemNo, itemNm, whId, whNm, useYn
        """
        path = "/pd/routingMng/aps/routingItemList"
        last_exc: Exception | None = None
        for attempt in range(1, self._cfg.retries + 1):
            try:
                r = self._http.post(path, json={"routingId": routing_id})
                r.raise_for_status()
                return _parse_envelope(r.json(), path)
            except Exception as exc:
                last_exc = exc
                logger.warning("attempt %d/%d failed for %s routingId=%s: %s", attempt, self._cfg.retries, path, routing_id, exc)
                if attempt < self._cfg.retries:
                    time.sleep(2 ** (attempt - 1))
        raise RuntimeError(f"All {self._cfg.retries} attempts failed for {path} routingId={routing_id}") from last_exc

    def fetch_item_process_list_by_routing(self, routing_id: int, item_id: int) -> list[dict[str, Any]]:
        """Fetch item-specific process steps for a routing×item pair (pd_if_aps_item_process).

        itemId must come from fetch_routing_item_list response.
        Fields: routingId, itemId, procId, procSno, procNm, makingGb, workTime (minutes), revNo
        Key value: workTime — item-level work duration, not available from pending endpoint.
        """
        path = "/pd/routingMng/aps/itemProcessListByRouting"
        last_exc: Exception | None = None
        for attempt in range(1, self._cfg.retries + 1):
            try:
                r = self._http.post(path, json={"routingId": routing_id, "itemId": item_id})
                r.raise_for_status()
                return _parse_envelope(r.json(), path)
            except Exception as exc:
                last_exc = exc
                logger.warning("attempt %d/%d failed for %s routingId=%s itemId=%s: %s", attempt, self._cfg.retries, path, routing_id, item_id, exc)
                if attempt < self._cfg.retries:
                    time.sleep(2 ** (attempt - 1))
        raise RuntimeError(f"All {self._cfg.retries} attempts failed for {path} routingId={routing_id} itemId={item_id}") from last_exc

    def fetch_equipment_by_workshop(self, workshop_id: int) -> list[dict[str, Any]]:
        """Fetch equipment for a workshop (GET /cm/workPlaceEquipmentMng?workshopId=).

        Unlike the /aps/* interface endpoints, this is a regular MES endpoint —
        GET with a query param, not POST. Records are time-versioned; the same
        equipmentId can appear multiple times (different validFrom/validTo).
        Key field: cycleFactor (ST conversion rate). Full field set includes
        capacity (*CapacityMin), lot (*LotQty), and rate (oeeRate, efficiencyRate,
        qualityFactor, availabilityRate, assignRate) groups.
        """
        path = "/cm/workPlaceEquipmentMng"
        last_exc: Exception | None = None
        for attempt in range(1, self._cfg.retries + 1):
            try:
                r = self._http.get(path, params={"workshopId": workshop_id})
                r.raise_for_status()
                return _parse_envelope(r.json(), path)
            except Exception as exc:
                last_exc = exc
                logger.warning("attempt %d/%d failed for %s workshopId=%s: %s", attempt, self._cfg.retries, path, workshop_id, exc)
                if attempt < self._cfg.retries:
                    time.sleep(2 ** (attempt - 1))
        raise RuntimeError(f"All {self._cfg.retries} attempts failed for {path} workshopId={workshop_id}") from last_exc

    def fetch_mps_plan(self, parea_id: int) -> list[dict[str, Any]]:
        """Fetch the master production schedule (GET /pd/prodPlanMpsMng?pareaId=).

        Richer than the pd/prodplan/aps/pending pending-queue feed synced into
        aps_demand — includes planStartDate/planEndDate, routingId, itemRev.
        Full list for the production area, not delta/pending-based.
        """
        path = "/pd/prodPlanMpsMng"
        last_exc: Exception | None = None
        for attempt in range(1, self._cfg.retries + 1):
            try:
                r = self._http.get(path, params={"pareaId": parea_id})
                r.raise_for_status()
                return _parse_envelope(r.json(), path)
            except Exception as exc:
                last_exc = exc
                logger.warning("attempt %d/%d failed for %s pareaId=%s: %s", attempt, self._cfg.retries, path, parea_id, exc)
                if attempt < self._cfg.retries:
                    time.sleep(2 ** (attempt - 1))
        raise RuntimeError(f"All {self._cfg.retries} attempts failed for {path} pareaId={parea_id}") from last_exc

    def fetch_item_routing(self, item_id: int) -> list[dict[str, Any]]:
        """Fetch 품목별라우팅입력 for an item (GET /pd/itemRoutingMng?itemId=).

        item_id is the G-System business id (Item.gsystem_id). One row per proc
        step (procSno). Passing revNo restricts/thins the result — intentionally
        omitted. Workcenter is returned as "oscustId"/"custNm" (NOT "workcenterId"/
        "workcenterNm" like other endpoints) — verified against live API response;
        `workTime` is present only on rows where it was actually entered upstream.
        """
        path = "/pd/itemRoutingMng"
        last_exc: Exception | None = None
        for attempt in range(1, self._cfg.retries + 1):
            try:
                r = self._http.get(path, params={"itemId": item_id})
                r.raise_for_status()
                return _parse_envelope(r.json(), path)
            except Exception as exc:
                last_exc = exc
                logger.warning("attempt %d/%d failed for %s itemId=%s: %s", attempt, self._cfg.retries, path, item_id, exc)
                if attempt < self._cfg.retries:
                    time.sleep(2 ** (attempt - 1))
        raise RuntimeError(f"All {self._cfg.retries} attempts failed for {path} itemId={item_id}") from last_exc

    def fetch_all(self) -> dict[str, list[dict[str, Any]]]:
        """Fetch all active entities in dependency-safe order."""
        return {
            "items":             self.fetch_items(),
            "workcenters":       self.fetch_workcenters(),
            "processes":         self.fetch_processes(),
            "routings":          self.fetch_routings(),
            "routing_items":     self.fetch_routing_items(),
            "routing_processes": self.fetch_routing_processes(),
            "bom":               self.fetch_bom(),
            "prod_plans":        self.fetch_demands(),
            "item_processes":    self.fetch_item_processes(),
            "calendar":          self.fetch_calendar(),
            "stock":             self.fetch_stock(),
            "customers":         self.fetch_customers(),
        }

    # ── Push confirmation ─────────────────────────────────────────────────────

    def push(self, entity: str, records: list[dict[str, Any]]) -> None:
        """Confirm receipt — POST raw records back so G-System sets ifRecvYn=true.

        Call after all DB writes are committed. Pass the original array received
        from the matching fetch_* call.
        """
        if not records:
            return
        path = _PUSH_ENDPOINTS[entity]
        self._post_push(path, records)
        logger.info("push confirmed: entity=%s records=%d", entity, len(records))


# ── Response parsing ──────────────────────────────────────────────────────────

def _parse_envelope(body: dict[str, Any], endpoint: str) -> list[dict[str, Any]]:
    """Validate G-System response envelope; raise on non-000 status."""
    code = body.get("statusCode")
    if code != _SUCCESS_CODE:
        msg = body.get("message", "")
        raise ValueError(f"{endpoint}: G-System returned statusCode={code!r} — {msg}")
    return body.get("result") or []


# ── Lookup index builders ─────────────────────────────────────────────────────

def build_item_id_to_no(items: list[dict[str, Any]]) -> dict[int, str]:
    """Map G-System integer itemId → itemNo string.

    Key is `itemId` (G-System business ID), NOT `id` (pending record ID).
    Used by abox_builder for BOM and Demand FK resolution.
    """
    index: dict[int, str] = {}
    for rec in items:
        item_id = rec.get("itemId")
        item_no = rec.get("itemNo")
        if item_id is not None and item_no:
            index[int(item_id)] = str(item_no)
        else:
            logger.warning("Item record missing itemId or itemNo — skipped: itemId=%s itemNo=%s", item_id, item_no)
    return index
