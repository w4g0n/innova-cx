from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from datetime import date
from collections import defaultdict
from calendar import month_name
import os

# -----------------------------
# Database Connection
# -----------------------------
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://innovacx_admin:changeme123@localhost:5433/complaints_db"
)
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# -----------------------------
# FastAPI App
# -----------------------------
app = FastAPI(title="InnovaCX API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace with your frontend URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# Helpers
# -----------------------------
def _title_or_none(value):
    return str(value).replace("_", " ").title() if value else None

def _status_to_ui(status):
    mapping = {
        "submitted": "Unassigned",
        "unassigned": "Unassigned",
        "assigned": "Assigned",
        "in_progress": "Assigned",
        "escalated": "Escalated",
        "overdue": "Overdue",
        "resolved": "Resolved"
    }
    return mapping.get(str(status).lower(), _title_or_none(status) if status else "")

def _format_minutes(minutes):
    if not minutes or minutes <= 0:
        return ""
    minutes = int(round(minutes))
    if minutes < 60:
        return f"{minutes} Minutes"
    return f"{minutes // 60}h {minutes % 60}m" if minutes % 60 else f"{minutes // 60} Hours"

# -----------------------------
# 0) Employee Tickets (All)
# -----------------------------
@app.get("/api/employee/{employee_id}/tickets/all")
def get_employee_tickets_all(employee_id: str):
    """Returns all tickets assigned to an employee in frontend-friendly shape."""
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT t.ticket_id, t.subject, t.priority, t.status,
                       t.submitted_at, t.resolved_at,
                       s.respond_due_at, s.resolve_due_at
                FROM cms.ticket t
                LEFT JOIN cms.ticket_sla s ON s.ticket_id = t.ticket_id
                WHERE t.employee_id = :id
                ORDER BY t.submitted_at DESC
            """),
            {"id": employee_id}
        ).fetchall()

        tickets = []
        for row in rows:
            submitted_at = row.submitted_at
            resolved_at = row.resolved_at

            response_minutes = (row.respond_due_at - submitted_at).total_seconds() / 60 \
                if submitted_at and row.respond_due_at else None
            resolution_minutes = (resolved_at - submitted_at).total_seconds() / 60 \
                if submitted_at and resolved_at else None

            tickets.append({
                "ticketId": row.ticket_id,
                "subject": row.subject,
                "priority": _title_or_none(row.priority),
                "status": _status_to_ui(row.status),
                "issueDate": submitted_at.date().isoformat() if submitted_at else "",
                "responseTime": _format_minutes(response_minutes),
                "resolutionTime": _format_minutes(resolution_minutes),
            })

        return {"tickets": tickets}

# -----------------------------
# 1) Monthly Employee Report
# -----------------------------
@app.get("/api/employee/{employee_id}/monthly-report")
def get_employee_monthly_report(employee_id: str, year: int = date.today().year, month: int = date.today().month):
    """Returns a full monthly report for an employee: tickets, KPIs, summary, ratingComponents, weekly, notes."""
    with engine.connect() as conn:
        # -----------------------------
        # Employee Info
        # -----------------------------
        emp_row = conn.execute(
            text("SELECT employee_id, full_name, department_id FROM cms.employee WHERE employee_id = :id"),
            {"id": employee_id}
        ).fetchone()
        if not emp_row:
            raise HTTPException(status_code=404, detail="Employee not found")
        employee = dict(emp_row._mapping)

        # -----------------------------
        # Tickets for Month
        # -----------------------------
        tickets_rows = conn.execute(
            text("""
                SELECT t.ticket_id, t.title, t.priority, t.status, t.submitted_at, t.resolved_at, t.department,
                       s.respond_due_at, s.resolve_due_at, s.respond_breached_at, s.resolve_breached_at,
                       a.attachment_id, a.file_name
                FROM cms.ticket t
                LEFT JOIN cms.ticket_sla s ON s.ticket_id = t.ticket_id
                LEFT JOIN cms.ticket_attachment a ON a.ticket_id = t.ticket_id
                WHERE t.employee_id = :id
                  AND EXTRACT(YEAR FROM t.submitted_at) = :year
                  AND EXTRACT(MONTH FROM t.submitted_at) = :month
                ORDER BY t.submitted_at DESC
            """),
            {"id": employee_id, "year": year, "month": month}
        ).fetchall()

        # Organize tickets with attachments
        tickets_dict = {}
        for row in tickets_rows:
            t_id = row.ticket_id
            if t_id not in tickets_dict:
                tickets_dict[t_id] = {
                    "ticketId": t_id,
                    "title": row.title,
                    "priority": row.priority,
                    "status": row.status,
                    "department": row.department,
                    "submittedAt": row.submitted_at,
                    "resolvedAt": row.resolved_at,
                    "sla": {
                        "respondDue": row.respond_due_at,
                        "resolveDue": row.resolve_due_at,
                        "respondBreached": row.respond_breached_at,
                        "resolveBreached": row.resolve_breached_at
                    },
                    "attachments": [],
                    "aiResults": None,
                    "workLogs": [],
                    "approvals": []
                }
            if row.attachment_id:
                tickets_dict[t_id]["attachments"].append({
                    "attachmentId": row.attachment_id,
                    "filename": row.file_name,
                    "fileUrl": f"/attachments/{row.attachment_id}"
                })

        tickets_list = list(tickets_dict.values())
        total_tickets = len(tickets_list)
        resolved_count = sum(1 for t in tickets_list if t["status"] == "resolved")
        in_progress_count = sum(1 for t in tickets_list if t["status"] == "in_progress")
        critical_count = sum(1 for t in tickets_list if str(t["priority"]).lower() == "high")
        overdue_count = sum(1 for t in tickets_list if t["status"] == "overdue")

        # -----------------------------
        # KPIs
        # -----------------------------
        response_times = [(t["resolvedAt"] - t["submittedAt"]).total_seconds() / 60
                          for t in tickets_list if t["submittedAt"] and t["resolvedAt"]]
        avg_response_time = f"{round(sum(response_times)/len(response_times))} mins" if response_times else "N/A"

        kpis = {
            "rating": f"{round((resolved_count / total_tickets * 100) if total_tickets else 0)} / 100",
            "resolved": resolved_count,
            "sla": f"{round(((total_tickets - overdue_count) / total_tickets * 100) if total_tickets else 100)}%",
            "avgResponse": avg_response_time
        }

        # -----------------------------
        # Summary
        # -----------------------------
        summary = [
            {"label": "Total Tickets Assigned", "value": total_tickets},
            {"label": "Resolved Tickets", "value": resolved_count},
            {"label": "Pending / In Progress", "value": in_progress_count},
            {"label": "Overdue Tickets", "value": overdue_count},
            {"label": "Critical & High Priority", "value": critical_count},
            {"label": "Low & Medium Priority", "value": total_tickets - critical_count},
            {"label": "First Contact Resolution", "value": "N/A"},
            {"label": "Customer Follow-ups Needed", "value": "N/A"}
        ]

        # -----------------------------
        # Rating Components
        # -----------------------------
        total_response = sum(response_times) if response_times else 0
        ratingComponents = [
            {"name": "Resolution Speed", "score": round(resolved_count / total_tickets * 10, 1) if total_tickets else 0,
             "pct": round((resolved_count / total_tickets * 100) if total_tickets else 0)},
            {"name": "Response Time", "score": round(total_response / total_tickets, 1) if total_tickets else 0,
             "pct": round((total_tickets - overdue_count) / total_tickets * 100 if total_tickets else 0)},
            {"name": "SLA Compliance",
             "score": round((total_tickets - overdue_count) / total_tickets * 10 if total_tickets else 10, 1),
             "pct": round((total_tickets - overdue_count) / total_tickets * 100 if total_tickets else 100)},
            {"name": "Escalations", "score": sum(1 for t in tickets_list if t["status"] == "escalated"), "pct": 100},
            {"name": "Reopen Rate", "score": sum(1 for t in tickets_list if t.get("reopened", False)), "pct": 100}
        ]

        # -----------------------------
        # Weekly Breakdown
        # -----------------------------
        weekly_data = defaultdict(lambda: {"assigned": 0, "resolved": 0, "sla": 0, "avg": 0})
        for t in tickets_list:
            week_no = ((t["submittedAt"].day - 1) // 7) + 1
            wd = weekly_data[f"Week {week_no}"]
            wd["assigned"] += 1
            if t["status"] == "resolved":
                wd["resolved"] += 1
            wd["sla"] += 1 if t["status"] != "overdue" else 0
            if t["submittedAt"] and t["resolvedAt"]:
                wd["avg"] += (t["resolvedAt"] - t["submittedAt"]).total_seconds() / 60

        weekly = []
        prev_resolved = None
        for i in range(1, 5):
            wd = weekly_data[f"Week {i}"]
            assigned = wd["assigned"]
            resolved = wd["resolved"]
            sla_pct = f"{int((wd['sla']/assigned)*100) if assigned else 0}%"
            avg_resp = f"{round(wd['avg']/assigned) if assigned else 0} mins"
            delta_text = "Baseline" if prev_resolved is None else \
                (f"+{resolved - prev_resolved} resolved" if resolved > prev_resolved else
                 f"{resolved - prev_resolved} resolved" if resolved < prev_resolved else "Stable")
            delta_type = "neutral" if prev_resolved is None else \
                "positive" if resolved > prev_resolved else "negative" if resolved < prev_resolved else "neutral"
            prev_resolved = resolved

            weekly.append({
                "week": f"Week {i}",
                "assigned": assigned,
                "resolved": resolved,
                "sla": sla_pct,
                "avg": avg_resp,
                "delta": {"type": delta_type, "text": delta_text}
            })

        # -----------------------------
        # Notes
        # -----------------------------
        notes = [
            "Performance summary based on current ticket activity.",
            "Focus on critical tickets to improve SLA and ratings.",
            "Ensure timely resolution to maintain high average rating."
        ]

        # -----------------------------
        # Return Report
        # -----------------------------
        month_display = month_name[month]
        report_id = f"{month_display[:3].lower()}-{year}"

        return {
            "id": report_id,
            "month": month_display,
            "subtitle": "Auto-generated summary of your complaints, SLA performance, and activity for this month.",
            "employee": {
                "id": employee["employee_id"],
                "name": employee["full_name"],
                "department": employee["department_id"]
            },
            "kpis": kpis,
            "summary": summary,
            "ratingComponents": ratingComponents,
            "weekly": weekly,
            "notes": notes,
            "tickets": tickets_list
        }

# -----------------------------
# 2) Employee Dashboard (combined)
# -----------------------------
@app.get("/api/employee/dashboard/{employee_id}")
def get_employee_dashboard(employee_id: str):
    """Returns full employee dashboard data: info, KPIs, all tickets, current month report."""
    with engine.connect() as conn:
        # -----------------------------
        # Employee info
        # -----------------------------
        emp_row = conn.execute(
            text("SELECT employee_id, full_name, department_id FROM cms.employee WHERE employee_id = :id"),
            {"id": employee_id}
        ).fetchone()
        if not emp_row:
            raise HTTPException(status_code=404, detail="Employee not found")
        employee = dict(emp_row._mapping)

        # -----------------------------
        # 1) Current Month Report
        # -----------------------------
        today = date.today()
        year, month = today.year, today.month

        tickets_rows = conn.execute(
            text("""
                SELECT t.ticket_id, t.title, t.priority, t.status, t.submitted_at, t.resolved_at, t.department,
                       s.respond_due_at, s.resolve_due_at
                FROM cms.ticket t
                LEFT JOIN cms.ticket_sla s ON s.ticket_id = t.ticket_id
                WHERE t.employee_id = :id
                  AND EXTRACT(YEAR FROM t.submitted_at) = :year
                  AND EXTRACT(MONTH FROM t.submitted_at) = :month
                ORDER BY t.submitted_at DESC
            """),
            {"id": employee_id, "year": year, "month": month}
        ).fetchall()

        tickets_list = []
        resolved_count = 0
        in_progress_count = 0
        critical_count = 0
        overdue_count = 0

        for row in tickets_rows:
            submitted_at = row.submitted_at
            resolved_at = row.resolved_at

            response_minutes = (row.respond_due_at - submitted_at).total_seconds() / 60 \
                if submitted_at and row.respond_due_at else None
            resolution_minutes = (resolved_at - submitted_at).total_seconds() / 60 \
                if submitted_at and resolved_at else None

            status_ui = _status_to_ui(row.status)
            tickets_list.append({
                "ticketId": row.ticket_id,
                "subject": row.title,
                "priority": _title_or_none(row.priority),
                "status": status_ui,
                "issueDate": submitted_at.date().isoformat() if submitted_at else "",
                "responseTime": _format_minutes(response_minutes),
                "resolutionTime": _format_minutes(resolution_minutes)
            })

            resolved_count += 1 if status_ui.lower() == "resolved" else 0
            in_progress_count += 1 if status_ui.lower() in ["assigned", "in progress"] else 0
            critical_count += 1 if str(row.priority).lower() == "high" else 0
            overdue_count += 1 if status_ui.lower() == "overdue" else 0

        total_tickets = len(tickets_list)

        # -----------------------------
        # KPIs
        # -----------------------------
        kpis = {
            "ticketsAssigned": total_tickets,
            "inProgress": in_progress_count,
            "resolvedThisMonth": resolved_count,
            "critical": critical_count,
            "overdue": overdue_count,
            "newToday": sum(1 for t in tickets_list if t["issueDate"] == today.isoformat())
        }

        # -----------------------------
        # Current Month Report
        # -----------------------------
        month_display = month_name[month]
        report_id = f"{month_display[:3].lower()}-{year}"
        reports = [{"month": month_display, "reportId": report_id}]

        # -----------------------------
        # Return dashboard
        # -----------------------------
        return {
            "employee": {
                "id": employee["employee_id"],
                "name": employee["full_name"],
                "department": employee["department_id"]
            },
            "kpis": kpis,
            "tickets": tickets_list,
            "reports": reports
        }
