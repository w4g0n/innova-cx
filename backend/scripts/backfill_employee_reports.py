#!/usr/bin/env python3
"""
backfill_employee_reports.py
============================
Generates and repairs employee monthly performance reports for ALL employees.

DESIGN PRINCIPLES
-----------------
1. DEMO MONTHS GUARANTEED — Every active employee always gets reports for:
     January 2026, February 2026, March 2026, April 2026
   Enforced regardless of whether MV data exists for that employee/month.
   Zero-activity months produce a valid report showing 0 resolved, 0% closure.

2. FORWARD-COMPATIBLE — Any month NEWER than April 2026 where an employee has
   MV data is also included automatically. May 2026, June 2026, etc. appear
   as data accumulates, without requiring code changes.

3. 2025 NEVER REGENERATED — Absolute year guard (year < 2026) enforces this.
   Any surviving pre-2026 rows are deleted in Step 0.

4. FULL MATRIX — All employees x all required months are processed, not just
   combinations that happen to exist in mv_employee_daily.

5. IDEMPOTENT — GENERATES missing, REPAIRS incomplete (rc_count=0), SKIPS OK.

RUN:
    docker cp backend/scripts/backfill_employee_reports.py \
        innovacx-backend:/tmp/backfill_employee_reports.py
    docker exec -it innovacx-backend \
        python /tmp/backfill_employee_reports.py
"""
from __future__ import annotations
import logging
import os
import re
import sys
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import OperationalError

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("backfill")

# Fixed demo months — every employee guaranteed these 4
DEMO_MONTHS: List[Tuple[int,int]] = [(2026,1),(2026,2),(2026,3),(2026,4)]
MIN_YEAR = 2026  # absolute floor — no reports below this year

# ── DB helpers ──────────────────────────────────────────────────────────────
def _get_dsn() -> str:
    if os.getenv("DATABASE_URL"): return os.environ["DATABASE_URL"]
    return (f"postgresql://{os.getenv('DB_USER','innovacx_app')}:"
            f"{os.getenv('DB_PASSWORD','changeme123')}@"
            f"{os.getenv('DB_HOST','localhost')}:"
            f"{os.getenv('DB_PORT','5432')}/"
            f"{os.getenv('DB_NAME','complaints_db')}")

def _conn():
    try: return psycopg2.connect(_get_dsn())
    except OperationalError as e:
        logger.error("DB connection failed: %s", e); sys.exit(1)

def fetch_one(sql, params=None):
    with _conn() as c:
        with c.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params or ())
            r = cur.fetchone(); return dict(r) if r else None

def fetch_all(sql, params=None):
    with _conn() as c:
        with c.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params or ())
            return [dict(r) for r in cur.fetchall()]

def execute(sql, params=None):
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(sql, params or ()); return cur.rowcount

# ── Constants ───────────────────────────────────────────────────────────────
_ML = {1:"January",2:"February",3:"March",4:"April",5:"May",6:"June",
       7:"July",8:"August",9:"September",10:"October",11:"November",12:"December"}
_MA = {1:"jan",2:"feb",3:"mar",4:"apr",5:"may",6:"jun",
       7:"jul",8:"aug",9:"sep",10:"oct",11:"nov",12:"dec"}

# ── Core report generator (mirrors main.py _generate_employee_report) ────────
def generate_report(user_id: str, year: int, month: int) -> Optional[str]:
    if year < MIN_YEAR: return None

    period_start = date(year, month, 1)
    period_end   = date(year+1,1,1) if month==12 else date(year,month+1,1)

    slug_row = fetch_one("SELECT split_part(email,'@',1) AS s FROM users WHERE id=%s::uuid",(user_id,)) or {}
    raw = str(slug_row.get("s") or "").strip().lower()
    slug = re.sub(r"[^a-z0-9]","",raw)[:12] or re.sub(r"[^a-z0-9]","",user_id.replace("-",""))[:8]

    code  = f"{_MA[month]}-{year}-{slug}"
    label = f"{_ML[month]} {year}"

    k = fetch_one("""
        SELECT COALESCE(SUM(total),0) AS total, COALESCE(SUM(resolved),0) AS resolved,
               COALESCE(SUM(breached),0) AS breached, COALESCE(SUM(escalated),0) AS escalated,
               ROUND(COALESCE(SUM(total-breached),0)::numeric/NULLIF(SUM(total),0)*100,1) AS sla_pct,
               ROUND(SUM(avg_respond_mins*total)/NULLIF(SUM(total),0),1) AS avg_resp
        FROM mv_employee_daily
        WHERE employee_id=%s::uuid AND created_day>=%s AND created_day<%s""",
        (user_id, period_start, period_end)) or {}

    total=int(k.get("total") or 0); resolved=int(k.get("resolved") or 0)
    breached=int(k.get("breached") or 0); escalated=int(k.get("escalated") or 0)
    sla=float(k.get("sla_pct") or 0); avg=k.get("avg_resp")
    avgf=float(avg) if avg is not None else None
    rrate=round(resolved/total*100,1) if total else 0.0
    erate=round(escalated/total*100,1) if total else 0.0
    rating_num=round((rrate*0.5)+(sla*0.5),1)
    if rating_num>=90:   rlabel=f"{rating_num}% · Excellent"
    elif rating_num>=75: rlabel=f"{rating_num}% · Good"
    elif rating_num>=50: rlabel=f"{rating_num}% · Needs Improvement"
    else:                rlabel=f"{rating_num}% · Poor"
    sla_s=f"{sla}%"; avg_s=f"{round(avgf)} min" if avgf is not None else "N/A"
    subtitle=f"{resolved} of {total} tickets resolved · {sla}% SLA compliance"

    ex=fetch_one("SELECT id FROM employee_reports WHERE report_code=%s AND employee_user_id=%s::uuid",(code,user_id))
    if ex:
        execute("""UPDATE employee_reports SET month_label=%s,subtitle=%s,kpi_rating=%s,
                   kpi_resolved=%s,kpi_sla=%s,kpi_avg_response=%s,created_at=NOW() WHERE id=%s""",
                (label,subtitle,rlabel,resolved,sla_s,avg_s,ex["id"]))
        rid=ex["id"]
    else:
        row=fetch_one("""INSERT INTO employee_reports(employee_user_id,report_code,month_label,
                         subtitle,kpi_rating,kpi_resolved,kpi_sla,kpi_avg_response)
                         VALUES(%s::uuid,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                      (user_id,code,label,subtitle,rlabel,resolved,sla_s,avg_s))
        if not row: return None
        rid=row["id"]

    # summary
    acc=fetch_one("""SELECT SUM(total) AS t, SUM(accepted) AS a FROM mv_acceptance_daily
                     WHERE employee_id=%s::uuid AND created_day>=%s AND created_day<%s""",
                  (user_id,period_start,period_end)) or {}
    at=int(acc.get("t") or 0); ac=int(acc.get("a") or 0)
    ar=round(ac/at*100,1) if at>0 else None

    execute("DELETE FROM employee_report_summary_items WHERE report_id=%s",(rid,))
    for lbl,val in [("Tickets Assigned",str(total)),("Tickets Resolved",str(resolved)),
                    ("SLA Compliance",sla_s),("Avg First Response",avg_s),
                    ("AI Acceptance Rate",f"{ar}%" if ar is not None else "N/A"),
                    ("Escalated",str(escalated))]:
        execute("INSERT INTO employee_report_summary_items(report_id,label,value_text) VALUES(%s,%s,%s)",(rid,lbl,val))

    # rating components
    spd=round(max(0.0,100.0-(avgf/480.0*100.0)),1) if avgf is not None else 0.0
    noesc=round(max(0.0,100.0-erate),1)
    execute("DELETE FROM employee_report_rating_components WHERE report_id=%s",(rid,))
    for n,s,p in [("Closure Rate",rrate,rrate),("SLA Compliance",sla,sla),
                  ("Response Speed",spd,spd),("No Escalations",noesc,noesc)]:
        execute("INSERT INTO employee_report_rating_components(report_id,name,score,pct) VALUES(%s,%s,%s,%s)",
                (rid,n,round(s,1),round(p,1)))

    # weekly rows
    wrows=fetch_all("""
        SELECT date_trunc('week',created_day)::date AS wm,
               SUM(total) AS a, SUM(resolved) AS r,
               ROUND(SUM(total-breached)::numeric/NULLIF(SUM(total),0)*100,1) AS sp,
               ROUND(SUM(avg_respond_mins*total)/NULLIF(SUM(total),0),1) AS ar
        FROM mv_employee_daily WHERE employee_id=%s::uuid
          AND created_day>=%s AND created_day<%s
        GROUP BY date_trunc('week',created_day)::date ORDER BY wm""",
        (user_id,period_start,period_end))
    execute("DELETE FROM employee_report_weekly WHERE report_id=%s",(rid,))
    prev=None
    for i,wr in enumerate(wrows,1):
        wa=int(wr.get("a") or 0); wr2=int(wr.get("r") or 0)
        ws=float(wr.get("sp") or 0); wa2=wr.get("ar")
        was=f"{round(float(wa2))} min" if wa2 is not None else "N/A"
        if prev is None: dt,dx="neutral","—"
        elif wr2>prev: dt,dx="positive",f"+{wr2-prev} resolved"
        elif wr2<prev: dt,dx="neutral",f"{wr2-prev} resolved"
        else: dt,dx="neutral","No change"
        prev=wr2
        wm=wr.get("wm")
        wl=f"Week {i} ({wm.strftime('%b %-d')})" if wm else f"Week {i}"
        execute("""INSERT INTO employee_report_weekly(report_id,week_label,assigned,resolved,
                   sla,avg_response,delta_type,delta_text) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)""",
                (rid,wl,wa,wr2,f"{ws}%",was,dt,dx))

    # notes
    notes=[]
    if total>0:
        notes.append(f"You handled {total} ticket{'s' if total!=1 else ''} in {label}, "
                     f"resolving {resolved} ({rrate}% closure rate).")
    else:
        notes.append(f"No tickets were assigned in {label}.")
    if total>0:
        if sla>=90: notes.append(f"Excellent SLA performance: {sla}% within agreed timeframes.")
        elif sla>=70: notes.append(f"Good SLA performance at {sla}%. {breached} breach{'es' if breached!=1 else ''}.")
        else: notes.append(f"SLA compliance was {sla}% — {breached} breach{'es' if breached!=1 else ''}. Focus on earlier responses.")
    if avgf is not None:
        if avgf<=30: notes.append(f"Outstanding response speed: avg first response {round(avgf)} min.")
        elif avgf<=120: notes.append(f"Average first response {round(avgf)} min — healthy range.")
        else: notes.append(f"Average first response {round(avgf)} min. Reducing this improves your rating.")
    if total>0:
        if escalated>0: notes.append(f"{escalated} ticket{'s' if escalated!=1 else ''} escalated ({erate}% rate).")
        else: notes.append("No tickets escalated — great self-resolution.")
    if ar is not None:
        if ar>=70: notes.append(f"AI resolutions accepted {ar}% — strong alignment.")
        else: notes.append(f"AI resolutions accepted {ar}%.")

    execute("DELETE FROM employee_report_notes WHERE report_id=%s",(rid,))
    for n in notes:
        execute("INSERT INTO employee_report_notes(report_id,note) VALUES(%s,%s)",(rid,n))

    return code


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    logger.info("=== backfill_employee_reports starting ===")
    logger.info("Demo months: %s", [f"{_ML[m]} {y}" for y,m in DEMO_MONTHS])
    logger.info("Year floor: %d (pre-%d reports never generated)", MIN_YEAR, MIN_YEAR)

    # Step 0: delete ALL pre-2026 reports (any format, idempotent)
    deleted = execute("""
        DELETE FROM employee_reports
        WHERE month_label LIKE '%%2025' OR month_label LIKE '%%2024'
           OR (report_code SIMILAR TO '[a-z]{3}-[0-9]{4}-[a-z0-9]+'
               AND split_part(report_code,'-',2)::int < 2026)
           OR report_code NOT SIMILAR TO '[a-z]{3}-[0-9]{4}-[a-z0-9]+'""")
    logger.info("Step 0: Deleted %d legacy/pre-2026 rows (sub-tables cascade)", deleted)

    # Step 1: get all active employees
    employees = fetch_all("""
        SELECT u.id::text AS user_id, u.email, up.full_name
        FROM users u JOIN user_profiles up ON up.user_id=u.id
        WHERE u.role='employee' AND u.is_active=TRUE
        ORDER BY up.full_name""")
    if not employees: logger.error("No active employees found."); sys.exit(1)
    logger.info("Active employees: %d", len(employees))

    # Step 2: build required month set
    demo_set=set(DEMO_MONTHS)
    last_y,last_m=max(DEMO_MONTHS)
    cutoff=date(last_y,last_m,1)
    newer=fetch_all("""
        SELECT DISTINCT EXTRACT(YEAR FROM created_month)::int AS yr,
                        EXTRACT(MONTH FROM created_month)::int AS mo
        FROM mv_employee_daily
        WHERE created_month>%s AND EXTRACT(YEAR FROM created_month)::int>=%s
        ORDER BY yr,mo""",(cutoff,MIN_YEAR))
    newer_set={(int(r["yr"]),int(r["mo"])) for r in newer if int(r["yr"])>=MIN_YEAR}
    all_req=sorted(demo_set|newer_set)
    logger.info("Required months (%d): %s", len(all_req),
                [f"{_ML[m]} {y}" for y,m in all_req])

    gen=rep=skip=err=0

    for emp in employees:
        uid=str(emp["user_id"]); name=str(emp.get("full_name") or emp.get("email") or uid)
        raw=str(emp.get("email","")).split("@")[0].strip().lower()
        slug=re.sub(r"[^a-z0-9]","",raw)[:12] or re.sub(r"[^a-z0-9]","",uid.replace("-",""))[:8]

        for year,month in all_req:
            if year<MIN_YEAR: continue
            code=f"{_MA[month]}-{year}-{slug}"
            tag="[DEMO]" if (year,month) in demo_set else "[NEW] "
            ex=fetch_one("""SELECT er.id,
                (SELECT COUNT(*) FROM employee_report_rating_components WHERE report_id=er.id) AS rc
                FROM employee_reports er
                WHERE er.report_code=%s AND er.employee_user_id=%s::uuid""",(code,uid))
            try:
                if not ex:
                    r=generate_report(uid,year,month)
                    if r:
                        logger.info("  GENERATED %s %-24s %s (%s %d)",tag,code,name,_ML[month],year)
                        gen+=1
                    else:
                        logger.warning("  FAILED    %-24s %s",code,name)
                        err+=1
                elif int(ex.get("rc") or 0)==0:
                    r=generate_report(uid,year,month)
                    if r:
                        logger.info("  REPAIRED  %-24s %s (%s %d)",code,name,_ML[month],year)
                        rep+=1
                    else:
                        logger.warning("  REPAIR FAILED %-24s %s",code,name)
                        err+=1
                else:
                    logger.info("  OK        %-24s %s (%s %d)",code,name,_ML[month],year)
                    skip+=1
            except Exception as exc:
                logger.error("  ERROR     %-24s %s: %s",code,name,exc)
                err+=1

    # Step 4: verification
    missing=False
    for emp in employees:
        uid=str(emp["user_id"])
        name=str(emp.get("full_name") or emp.get("email") or uid)
        raw=str(emp.get("email","")).split("@")[0].strip().lower()
        slug=re.sub(r"[^a-z0-9]","",raw)[:12] or re.sub(r"[^a-z0-9]","",uid.replace("-",""))[:8]
        for year,month in DEMO_MONTHS:
            code=f"{_MA[month]}-{year}-{slug}"
            row=fetch_one("""SELECT (SELECT COUNT(*) FROM employee_report_rating_components
                             WHERE report_id=er.id) AS rc FROM employee_reports er
                             WHERE er.report_code=%s AND er.employee_user_id=%s::uuid""",(code,uid))
            if not row or int(row.get("rc") or 0)==0:
                logger.warning("  MISSING/INCOMPLETE %-24s %s (%s %d)",code,name,_ML[month],year)
                missing=True

    pre=fetch_one("SELECT COUNT(*) AS c FROM employee_reports WHERE month_label LIKE '%%2025' OR month_label LIKE '%%2024'") or {}
    pre_cnt=int(pre.get("c") or 0)

    logger.info("")
    logger.info("=== backfill_employee_reports complete ===")
    logger.info("  Generated : %d", gen)
    logger.info("  Repaired  : %d", rep)
    logger.info("  Skipped   : %d  (already fully populated)", skip)
    logger.info("  Errors    : %d", err)
    logger.info("  Pre-2026 remaining : %d  (expected 0)", pre_cnt)
    logger.info("  Coverage gaps      : %s", "NONE ✓" if not missing else "SEE WARNINGS ABOVE")

    if err or missing or pre_cnt>0:
        logger.error("Backfill completed with issues. Check warnings above.")
        sys.exit(1)
    logger.info("All reports fully populated.")

if __name__=="__main__":
    main()
