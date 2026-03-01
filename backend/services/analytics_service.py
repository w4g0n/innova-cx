# backend/services/analytics_service.py
# =============================================================================
# InnovaCX – Analytics Service
# =============================================================================
# All analytics queries go here. They read ONLY from the materialized views:
#   mv_ticket_base, mv_daily_volume, mv_employee_daily, mv_acceptance_daily
#
# Rules:
#   - Never import from fastapi here (no HTTPException, no Depends)
#   - Never touch base transactional tables (tickets, users, etc.) directly
#   - Accept Python primitives as params (dates, strings)
#   - Return plain dicts/lists — the route handler shapes them into responses
#
# Imported by main.py like:
#   from services.analytics_service import get_trends_data, refresh_mvs
# =============================================================================

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# fetch_one / fetch_all / db_connect are injected at runtime to avoid
# circular imports (main.py defines them, then passes them in).
# Call  analytics_service.init(fetch_one_fn, fetch_all_fn, db_connect_fn)
# once during startup.

_fetch_one   = None
_fetch_all   = None
_db_connect  = None


def init(fetch_one_fn, fetch_all_fn, db_connect_fn):
    """Call this once from main.py startup before serving any requests."""
    global _fetch_one, _fetch_all, _db_connect
    _fetch_one  = fetch_one_fn
    _fetch_all  = fetch_all_fn
    _db_connect = db_connect_fn


# ─── SLA targets (single source of truth, mirrors DB trigger) ────────────────
SLA_TARGETS = {
    "respond": {"Critical": 30,  "High": 60,   "Medium": 180, "Low": 360},
    "resolve": {"Critical": 360, "High": 1080, "Medium": 2880, "Low": 4320},
}


# =============================================================================
# REFRESH
# =============================================================================

def refresh_mvs() -> Dict[str, Any]:
    """
    Calls refresh_analytics_mvs() in Postgres.
    Returns the JSONB timing result from that function.
    """
    row = _fetch_one("SELECT refresh_analytics_mvs() AS result")
    return row["result"] if row else {"ok": False}


# =============================================================================
# HELPER: build WHERE clause + params from filter arguments
# =============================================================================

def _build_filters(
    period_start: datetime,
    period_end: datetime,
    department: str = "All Departments",
    priority: str = "All Priorities",
    table_alias: str = "",
    use_date_col: bool = False,   # True  → filter on created_day (DATE column)
                                  # False → filter on created_at  (TIMESTAMPTZ)
    skip_priority: bool = False,  # True  → omit priority filter (mv_employee_daily has no priority col)
) -> Tuple[str, List[Any]]:
    """
    Returns (where_clause, params_list).

    use_date_col=False (default): filters on created_at TIMESTAMPTZ
                                  → use for mv_ticket_base
    use_date_col=True:            filters on created_day DATE
                                  → use for mv_daily_volume, mv_employee_daily,
                                    mv_acceptance_daily
    """
    prefix = f"{table_alias}." if table_alias else ""

    if use_date_col:
        # DATE column — cast the datetimes to date for correct comparison
        filters = [
            f"{prefix}created_day >= %s::date",
            f"{prefix}created_day <  %s::date",
        ]
    else:
        # TIMESTAMPTZ column
        filters = [
            f"{prefix}created_at >= %s",
            f"{prefix}created_at <  %s",
        ]

    params: List[Any] = [period_start, period_end]

    if department and department != "All Departments":
        filters.append(f"{prefix}department_name = %s")
        params.append(department)

    priority_map = {
        "All Priorities":  None,
        "Low":             ["Low"],
        "Medium":          ["Medium"],
        "High":            ["High"],
        "Critical":        ["Critical"],
        "High & Critical": ["High", "Critical"],
        "Critical only":   ["Critical"],
        "Low & Medium":    ["Low", "Medium"],
    }
    pv = priority_map.get(priority)
    if pv and not skip_priority:
        filters.append(f"{prefix}priority = ANY(%s)")
        params.append(pv)

    return " AND ".join(filters), params


# =============================================================================
# SECTION A — COMPLAINT TRENDS
# =============================================================================

def get_section_a(
    period_start: datetime,
    period_end: datetime,
    department: str,
    priority: str,
) -> Dict[str, Any]:

    where, params = _build_filters(period_start, period_end, department, priority, use_date_col=True)

    # ── A1: Complaint vs Inquiry daily volumes ────────────────────────────
    raw = _fetch_all(
        f"""
        SELECT created_day AS day, ticket_type, SUM(total) AS count
        FROM mv_daily_volume
        WHERE {where}
        GROUP BY created_day, ticket_type
        ORDER BY created_day
        """,
        params,
    )
    cid_map: Dict[str, dict] = {}
    for r in raw:
        key = r["day"].isoformat()
        if key not in cid_map:
            cid_map[key] = {"day": key, "complaints": 0, "inquiries": 0}
        if r["ticket_type"] == "Complaint":
            cid_map[key]["complaints"] = int(r["count"])
        else:
            cid_map[key]["inquiries"] = int(r["count"])
    complaint_vs_inquiry = sorted(cid_map.values(), key=lambda x: x["day"])

    # ── A2: Daily volume with 7-day rolling average ───────────────────────
    daily_raw = _fetch_all(
        f"""
        SELECT
            day,
            count,
            ROUND(AVG(count) OVER (ORDER BY day ROWS BETWEEN 6 PRECEDING AND CURRENT ROW), 1)
                AS rolling_avg
        FROM (
            SELECT created_day AS day, SUM(total) AS count
            FROM mv_daily_volume
            WHERE {where}
            GROUP BY created_day
        ) sub
        ORDER BY day
        """,
        params,
    )
    daily_volume = [
        {
            "day":        r["day"].isoformat(),
            "count":      int(r["count"]),
            "rollingAvg": float(r["rolling_avg"]) if r["rolling_avg"] is not None else 0,
        }
        for r in daily_raw
    ]

    # ── A3: Recurring heatmap (dept × priority) ───────────────────────────
    # mv_ticket_base has created_at (TIMESTAMPTZ) — use use_date_col=False
    where_base, params_base = _build_filters(period_start, period_end, department, priority, use_date_col=False)
    recurring_heatmap = _fetch_all(
        f"""
        SELECT department_name AS department, priority, COUNT(*) AS count
        FROM mv_ticket_base
        WHERE {where_base}
          AND created_by_user_id IN (
              SELECT created_by_user_id
              FROM mv_ticket_base
              WHERE created_by_user_id IS NOT NULL
              GROUP BY created_by_user_id, department_name
              HAVING COUNT(*) > 1
          )
        GROUP BY department_name, priority
        ORDER BY department_name, priority
        """,
        params_base,
    )

    return {
        "complaintVsInquiry": complaint_vs_inquiry,
        "dailyVolume":        daily_volume,
        "recurringHeatmap":   recurring_heatmap,
    }


# =============================================================================
# SECTION B — SLA PERFORMANCE
# =============================================================================

def get_section_b(
    period_start: datetime,
    period_end: datetime,
    prev_start: datetime,
    department: str,
    priority: str,
) -> Dict[str, Any]:

    where, params           = _build_filters(period_start, period_end, department, priority, use_date_col=True)
    prev_where, prev_params = _build_filters(prev_start, period_start, department, priority, use_date_col=True)

    # ── B1: Overall SLA KPIs ──────────────────────────────────────────────
    sla_overall = _fetch_one(
        f"""
        SELECT
            SUM(total)                                  AS total,
            SUM(breached)                               AS breached,
            SUM(escalated)                              AS escalated,
            ROUND(AVG(avg_respond_mins)
                  FILTER (WHERE avg_respond_mins IS NOT NULL), 1) AS avg_respond_mins,
            ROUND(AVG(avg_resolve_mins)
                  FILTER (WHERE avg_resolve_mins IS NOT NULL), 1) AS avg_resolve_mins
        FROM mv_daily_volume
        WHERE {where}
        """,
        params,
    ) or {}

    total_t    = int(sla_overall.get("total")    or 0)
    breached_t = int(sla_overall.get("breached") or 0)
    escalated  = int(sla_overall.get("escalated") or 0)
    breach_rate     = round(breached_t / total_t * 100, 1) if total_t else 0
    escalation_rate = round(escalated  / total_t * 100, 1) if total_t else 0
    avg_respond_mins = float(sla_overall.get("avg_respond_mins") or 0)
    avg_resolve_mins = float(sla_overall.get("avg_resolve_mins") or 0)

    # ── B2: Previous period breach rate ───────────────────────────────────
    prev_sla = _fetch_one(
        f"""
        SELECT SUM(total) AS total, SUM(breached) AS breached
        FROM mv_daily_volume
        WHERE {prev_where}
        """,
        prev_params,
    ) or {}
    prev_total    = int(prev_sla.get("total")    or 0)
    prev_breached = int(prev_sla.get("breached") or 0)
    prev_breach_rate = round(prev_breached / prev_total * 100, 1) if prev_total else 0

    # ── B3: Breach by department + priority tier ──────────────────────────
    breach_by_dept_raw = _fetch_all(
        f"""
        SELECT
            department_name AS department,
            priority,
            SUM(total)    AS total,
            SUM(breached) AS breached
        FROM mv_daily_volume
        WHERE {where}
        GROUP BY department_name, priority
        ORDER BY department_name, priority
        """,
        params,
    )
    dept_breach_map: Dict[str, dict] = {}
    for r in breach_by_dept_raw:
        dept = r["department"]
        if dept not in dept_breach_map:
            dept_breach_map[dept] = {
                "department": dept, "total": 0, "breached": 0,
                "Critical": 0, "High": 0, "Medium": 0, "Low": 0,
                "Critical_total": 0, "High_total": 0, "Medium_total": 0, "Low_total": 0,
            }
        p = r["priority"]
        dept_breach_map[dept]["total"]   += int(r["total"])
        dept_breach_map[dept]["breached"] += int(r["breached"])
        if p in ("Critical", "High", "Medium", "Low"):
            dept_breach_map[dept][f"{p}_total"] += int(r["total"])
            dept_breach_map[dept][p]             += int(r["breached"])

    breach_by_dept_out = []
    for dept, v in dept_breach_map.items():
        breach_by_dept_out.append({
            "department": dept,
            "total":      v["total"],
            "breachRate": round(v["breached"] / v["total"] * 100, 1) if v["total"] else 0,
            "Critical":   round(v["Critical"] / v["Critical_total"] * 100, 1) if v["Critical_total"] else 0,
            "High":       round(v["High"]     / v["High_total"]     * 100, 1) if v["High_total"] else 0,
            "Medium":     round(v["Medium"]   / v["Medium_total"]   * 100, 1) if v["Medium_total"] else 0,
            "Low":        round(v["Low"]       / v["Low_total"]     * 100, 1) if v["Low_total"] else 0,
        })
    breach_by_dept_out.sort(key=lambda x: -x["breachRate"])

    # ── B4: Breach timeline — daily stacked by priority ───────────────────
    bt_raw = _fetch_all(
        f"""
        SELECT
            created_day AS day,
            priority,
            SUM(total)    AS total,
            SUM(breached) AS breached
        FROM mv_daily_volume
        WHERE {where}
        GROUP BY created_day, priority
        ORDER BY created_day, priority
        """,
        params,
    )
    bt_map: Dict[str, dict] = {}
    for r in bt_raw:
        key = r["day"].isoformat()
        if key not in bt_map:
            bt_map[key] = {"day": key, "total": 0, "Critical": 0, "High": 0, "Medium": 0, "Low": 0}
        bt_map[key]["total"] += int(r["total"])
        p = r["priority"]
        if p in ("Critical", "High", "Medium", "Low"):
            bt_map[key][p] += int(r["breached"])
    breach_timeline_out = sorted(bt_map.values(), key=lambda x: x["day"])

    # ── B5: Escalation by department ──────────────────────────────────────
    esc_raw = _fetch_all(
        f"""
        SELECT
            department_name AS department,
            SUM(total)     AS total,
            SUM(escalated) AS escalated
        FROM mv_daily_volume
        WHERE {where}
        GROUP BY department_name
        ORDER BY escalated DESC
        """,
        params,
    )
    escalation_by_dept_out = [
        {
            "department": r["department"],
            "total":      int(r["total"]),
            "escalated":  int(r["escalated"]),
            "rate":       round(int(r["escalated"]) / int(r["total"]) * 100, 1) if r["total"] else 0,
        }
        for r in esc_raw
    ]

    # ── B6: Avg response/resolve time by priority vs targets ──────────────
    time_raw = _fetch_all(
        f"""
        SELECT
            priority,
            ROUND(AVG(avg_respond_mins) FILTER (WHERE avg_respond_mins IS NOT NULL), 1) AS avg_respond,
            ROUND(AVG(avg_resolve_mins) FILTER (WHERE avg_resolve_mins IS NOT NULL), 1) AS avg_resolve,
            SUM(total) AS total
        FROM mv_daily_volume
        WHERE {where}
        GROUP BY priority
        ORDER BY
            CASE priority
                WHEN 'Critical' THEN 1
                WHEN 'High'     THEN 2
                WHEN 'Medium'   THEN 3
                ELSE 4
            END
        """,
        params,
    )
    time_by_priority_out = [
        {
            "priority":      r["priority"],
            "avgRespond":    float(r["avg_respond"] or 0),
            "avgResolve":    float(r["avg_resolve"] or 0),
            "targetRespond": SLA_TARGETS["respond"].get(r["priority"], 360),
            "targetResolve": SLA_TARGETS["resolve"].get(r["priority"], 4320),
            "total":         int(r["total"]),
        }
        for r in time_raw
    ]

    return {
        "kpis": {
            "totalTickets":    total_t,
            "breachRate":      breach_rate,
            "prevBreachRate":  prev_breach_rate,
            "breachDelta":     round(breach_rate - prev_breach_rate, 1),
            "escalationRate":  escalation_rate,
            "avgRespondMins":  round(avg_respond_mins, 1),
            "avgResolveMins":  round(avg_resolve_mins, 1),
            "avgRespondHrs":   round(avg_respond_mins / 60, 2),
            "avgResolveHrs":   round(avg_resolve_mins / 60, 2),
        },
        "breachByDept":     breach_by_dept_out,
        "breachTimeline":   breach_timeline_out,
        "escalationByDept": escalation_by_dept_out,
        "timeByPriority":   time_by_priority_out,
    }


# =============================================================================
# SECTION C — EMPLOYEE PERFORMANCE
# =============================================================================

def get_section_c(
    period_start: datetime,
    period_end: datetime,
    department: str,
    priority: str,
) -> Dict[str, Any]:

    # mv_employee_daily has created_day (DATE) → use_date_col=True
    # NOTE: mv_employee_daily aggregates across priorities — no priority column exists.
    # Priority filter is intentionally skipped here (skip_priority=True).
    where, params = _build_filters(
        period_start, period_end, department, priority, table_alias="e", use_date_col=True, skip_priority=True
    )

    # ── C1: Per-employee summary from mv_employee_daily ───────────────────
    emp_raw = _fetch_all(
        f"""
        SELECT
            employee_name                        AS name,
            employee_code                        AS emp_id,
            employee_role                        AS role,
            SUM(total)                           AS total,
            SUM(resolved)                        AS resolved,
            SUM(breached)                        AS breached,
            SUM(rescored)                        AS rescored,
            SUM(upscored)                        AS upscored,
            SUM(downscored)                      AS downscored,
            SUM(total_with_model)                AS total_with_model,
            ROUND(AVG(avg_respond_mins) FILTER (WHERE avg_respond_mins IS NOT NULL), 1) AS avg_respond_mins,
            ROUND(AVG(avg_resolve_mins) FILTER (WHERE avg_resolve_mins IS NOT NULL), 1) AS avg_resolve_mins
        FROM mv_employee_daily e
        WHERE {where}
        GROUP BY employee_name, employee_code, employee_role
        ORDER BY resolved DESC
        """,
        params,
    )

    # ── Company averages for comparison baseline ──────────────────────────
    # mv_ticket_base has created_at (TIMESTAMPTZ) → use_date_col=False
    where_base, params_base = _build_filters(period_start, period_end, department, priority, use_date_col=False)
    company_avg = _fetch_one(
        f"""
        SELECT
            ROUND(AVG(response_time_mins) FILTER (WHERE response_time_mins IS NOT NULL), 1) AS avg_respond,
            ROUND(AVG(resolve_time_mins)  FILTER (WHERE resolve_time_mins  IS NOT NULL), 1) AS avg_resolve,
            ROUND(
                COUNT(*) FILTER (WHERE any_breached)::NUMERIC
                / NULLIF(COUNT(*), 0) * 100, 1
            ) AS breach_rate
        FROM mv_ticket_base
        WHERE {where_base}
        """,
        params_base,
    ) or {}

    # ── C2: Acceptance rates from mv_acceptance_daily ─────────────────────
    # Filter by date only (no dept/priority filter on feedback table)
    acc_where = "created_month >= %s AND created_month < %s"
    acc_params = [
        date(period_start.year, period_start.month, 1),
        date(period_end.year,   period_end.month,   1),
    ]
    acc_raw = _fetch_all(
        f"""
        SELECT
            employee_name                               AS name,
            SUM(total)    AS total,
            SUM(accepted) AS accepted,
            SUM(declined) AS declined
        FROM mv_acceptance_daily
        WHERE {acc_where}
        GROUP BY employee_name
        """,
        acc_params,
    )
    acceptance_map = {
        r["name"]: {
            "total":    int(r["total"]),
            "accepted": int(r["accepted"]),
            "declined": int(r["declined"]),
            "rate":     round(int(r["accepted"]) / int(r["total"]) * 100, 1) if r["total"] else 0,
        }
        for r in acc_raw
    }

    # ── Assemble employee array ───────────────────────────────────────────
    co_breach  = float(company_avg.get("breach_rate") or 0)
    co_resolve = float(company_avg.get("avg_resolve") or 0)
    co_respond = float(company_avg.get("avg_respond") or 0)

    employee_out = []
    for e in emp_raw:
        name        = e["name"]
        total       = int(e["total"] or 0)
        brate       = round(int(e["breached"] or 0) / total * 100, 1) if total else 0
        twm         = int(e["total_with_model"] or 0)
        rescored    = int(e["rescored"] or 0)
        rescore_rate = round(rescored / twm * 100, 1) if twm else 0
        acc = acceptance_map.get(name, {"rate": None, "accepted": 0, "declined": 0, "total": 0})

        employee_out.append({
            "name":              name,
            "empId":             e["emp_id"],
            "role":              e["role"],
            "ticketsHandled":    total,
            "resolved":          int(e["resolved"] or 0),
            "breached":          int(e["breached"] or 0),
            "breachRate":        brate,
            "avgResolveMins":    float(e["avg_resolve_mins"] or 0),
            "avgRespondMins":    float(e["avg_respond_mins"] or 0),
            "companyBreachRate":  round(co_breach, 1),
            "companyResolveMins": round(co_resolve, 1),
            "companyRespondMins": round(co_respond, 1),
            "acceptanceRate":     acc["rate"],
            "acceptedCount":      acc["accepted"],
            "declinedCount":      acc["declined"],
            "rescoreRate":        rescore_rate,
            "upscored":           int(e["upscored"] or 0),
            "downscored":         int(e["downscored"] or 0),
            # Alert flags — same thresholds as before
            "alertLowVolume":     total < 5,
            "alertHighBreach":    brate > 10,
            "alertSlowResolve":   float(e["avg_resolve_mins"] or 0) > 480,
            "alertLowAcceptance": acc["rate"] is not None and acc["rate"] < 50,
            "alertHighRescore":   rescore_rate > 30,
        })

    team_accept_avg = (
        round(
            sum(e["acceptanceRate"] for e in employee_out if e["acceptanceRate"] is not None)
            / max(sum(1 for e in employee_out if e["acceptanceRate"] is not None), 1),
            1,
        )
    )

    return {
        "employees":         employee_out,
        "teamAcceptAvg":     team_accept_avg,
        "companyBreachRate": round(co_breach, 1),
    }


# =============================================================================
# LEGACY SHAPE — keeps ComplaintTrends.jsx working with no frontend changes
# =============================================================================

def get_legacy_kpis(
    period_start: datetime,
    period_end: datetime,
    department: str,
    priority: str,
    total_t: int,
    breach_rate: float,
    avg_respond_mins: float,
    avg_resolve_mins: float,
) -> Dict[str, Any]:

    # mv_daily_volume uses created_day (DATE)
    where, params = _build_filters(period_start, period_end, department, priority, use_date_col=True)

    # Top category by volume
    top_row = _fetch_one(
        f"""
        SELECT department_name AS name, SUM(total) AS count
        FROM mv_daily_volume
        WHERE {where}
        GROUP BY department_name
        ORDER BY count DESC
        LIMIT 1
        """,
        params,
    )
    top_category = top_row["name"] if top_row else "—"

    # Recurring submitters count — mv_ticket_base uses created_at (TIMESTAMPTZ)
    where_base, params_base = _build_filters(period_start, period_end, department, priority, use_date_col=False)
    repeat_row = _fetch_one(
        f"""
        SELECT COUNT(*) AS count FROM (
            SELECT created_by_user_id
            FROM mv_ticket_base
            WHERE {where_base}
            GROUP BY created_by_user_id
            HAVING COUNT(*) > 1
        ) r
        """,
        params_base,
    ) or {"count": 0}
    repeat_pct = round(int(repeat_row["count"]) / total_t * 100) if total_t else 0

    # Monthly bar chart
    bars_raw = _fetch_all(
        f"""
        SELECT
            to_char(created_day, 'Mon') AS label,
            created_month,
            SUM(total) AS value
        FROM mv_daily_volume
        WHERE {where}
        GROUP BY to_char(created_day, 'Mon'), created_month
        ORDER BY created_month
        """,
        params,
    )
    bars_legacy = [{"label": r["label"], "value": int(r["value"])} for r in bars_raw]

    # Categories pie
    cats_raw = _fetch_all(
        f"""
        SELECT
            department_name AS name,
            SUM(total) * 100.0 / NULLIF(SUM(SUM(total)) OVER (), 0) AS pct
        FROM mv_daily_volume
        WHERE {where}
        GROUP BY department_name
        """,
        params,
    )
    categories_legacy = [{"name": r["name"], "pct": float(r["pct"] or 0)} for r in cats_raw]

    # Monthly summary table
    table_raw = _fetch_all(
        f"""
        SELECT
            to_char(created_day, 'Month') AS month,
            created_month,
            SUM(total)    AS total,
            SUM(resolved) AS resolved,
            ROUND(SUM(resolved) * 100.0 / NULLIF(SUM(total), 0)) AS within_sla,
            ROUND(AVG(avg_respond_mins) FILTER (WHERE avg_respond_mins IS NOT NULL)) AS avg_response,
            ROUND(AVG(avg_resolve_mins) FILTER (WHERE avg_resolve_mins IS NOT NULL) / 1440.0, 1) AS avg_resolve
        FROM mv_daily_volume
        WHERE {where}
        GROUP BY to_char(created_day, 'Month'), created_month
        ORDER BY created_month
        """,
        params,
    )
    table_legacy = [
        {
            "month":       r["month"],
            "total":       int(r["total"] or 0),
            "resolved":    int(r["resolved"] or 0),
            "within_sla":  int(r["within_sla"] or 0),
            "avg_response": float(r["avg_response"] or 0),
            "avg_resolve":  float(r["avg_resolve"] or 0),
        }
        for r in table_raw
    ]

    return {
        "kpis": {
            "complaints":  total_t,
            "sla":         f"{100 - breach_rate}%",
            "response":    f"{round(avg_respond_mins)} mins",
            "resolve":     f"{round(avg_resolve_mins / 60, 1)} hrs",
            "topCategory": top_category,
            "repeat":      f"{repeat_pct}%",
        },
        "bars":       bars_legacy,
        "categories": categories_legacy,
        "table":      table_legacy,
    }


# =============================================================================
# MAIN ENTRY POINT — called by the /manager/trends route handler
# =============================================================================

def get_trends_data(
    period_start: datetime,
    period_end: datetime,
    prev_start: datetime,
    department: str = "All Departments",
    priority: str = "All Priorities",
) -> Dict[str, Any]:
    """
    Returns the complete payload for /manager/trends.
    Identical JSON shape to the original endpoint — zero frontend changes needed.
    """
    section_b = get_section_b(period_start, period_end, prev_start, department, priority)
    total_t          = section_b["kpis"]["totalTickets"]
    breach_rate      = section_b["kpis"]["breachRate"]
    avg_respond_mins = section_b["kpis"]["avgRespondMins"]
    avg_resolve_mins = section_b["kpis"]["avgResolveMins"]

    legacy = get_legacy_kpis(
        period_start, period_end, department, priority,
        total_t, breach_rate, avg_respond_mins, avg_resolve_mins,
    )

    return {
        # Legacy shape (ComplaintTrends.jsx reads these)
        **legacy,
        # New sections
        "sectionA": get_section_a(period_start, period_end, department, priority),
        "sectionB": section_b,
        "sectionC": get_section_c(period_start, period_end, department, priority),
    }