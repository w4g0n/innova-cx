import { useEffect, useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "../../components/Layout";
import PageHeader from "../../components/common/PageHeader";
import PillSearch from "../../components/common/PillSearch";
import PillSelect from "../../components/common/PillSelect";
import KpiCard from "../../components/common/KpiCard";
import PriorityPill from "../../components/common/PriorityPill";
import FilterPillButton from "../../components/common/FilterPillButton";
import { apiUrl } from "../../config/apiBase";
import { getToken, authHeader } from "../../utils/auth";
import "./CustomerHistory.css";

/* ─── Friendly priority explanations for customers ─── */
const PRIORITY_CONTEXT = {
  Critical: {
    color: "#dc2626",
    bg: "rgba(220, 38, 38, 0.07)",
    border: "rgba(220, 38, 38, 0.18)",
    icon: "🔴",
    headline: "Critical Priority",
    reason:
      "Our AI detected signs of high urgency or significant distress in your message. Your ticket has been placed at the very top of the queue for immediate attention.",
  },
  High: {
    color: "#ea580c",
    bg: "rgba(234, 88, 12, 0.07)",
    border: "rgba(234, 88, 12, 0.18)",
    icon: "🟠",
    headline: "High Priority",
    reason:
      "Your issue was flagged as important and time-sensitive. Our team will attend to it ahead of standard requests.",
  },
  Medium: {
    color: "#b45309",
    bg: "rgba(180, 83, 9, 0.07)",
    border: "rgba(180, 83, 9, 0.18)",
    icon: "🟡",
    headline: "Medium Priority",
    reason:
      "Your ticket has been placed in the standard queue. Our team is working through cases in order and will get to yours soon.",
  },
  Low: {
    color: "#16a34a",
    bg: "rgba(22, 163, 74, 0.07)",
    border: "rgba(22, 163, 74, 0.18)",
    icon: "🟢",
    headline: "Low Priority",
    reason:
      "Our AI identified this as a routine inquiry. It will be handled once higher-priority tickets are resolved.",
  },
};

function getPriorityContext(priority) {
  return PRIORITY_CONTEXT[String(priority || "")] || PRIORITY_CONTEXT.Medium;
}

function formatTicketSource(value) {
  return String(value || "user").toLowerCase() === "chatbot" ? "Chatbot" : "User";
}

const WORKFLOW_STAGES = [
  { id: "open", label: "Open", owner: "System" },
  { id: "assigned", label: "Assigned", owner: "Operator" },
  { id: "in_progress", label: "In Progress", owner: "Employee" },
  { id: "resolved", label: "Resolved", owner: "Employee" },
];

function getWorkflowState(status) {
  const value = String(status || "").trim().toLowerCase();
  if (value === "resolved") {
    return { stageIndex: 3, stageLabel: "Resolved", owner: "Employee", note: "Work is complete." };
  }
  if (value === "in progress") {
    return { stageIndex: 2, stageLabel: "In Progress", owner: "Employee", note: "A team member is working on this." };
  }
  if (value === "assigned" || value === "escalated") {
    return { stageIndex: 1, stageLabel: "Assigned", owner: "Operator", note: "Ticket is assigned and queued for action." };
  }
  return { stageIndex: 0, stageLabel: "Open", owner: "System", note: "Ticket was received and is pending assignment." };
}

function getSlaTargets(priority) {
  const value = String(priority || "").trim().toLowerCase();
  if (value === "critical") return { minResponse: "15 min", minResolve: "4 hrs" };
  if (value === "high") return { minResponse: "1 hr", minResolve: "8 hrs" };
  if (value === "low") return { minResponse: "8 hrs", minResolve: "72 hrs" };
  return { minResponse: "4 hrs", minResolve: "24 hrs" };
}

export default function CustomerHistory() {
  const navigate = useNavigate();

  const [query, setQuery] = useState("");
  const [type, setType] = useState("All");
  const [status, setStatus] = useState("All");

  const [historyItems, setHistoryItems] = useState([]);

  useEffect(() => {
    const fetchTickets = async () => {
      const token = getToken();
      if (!token) return;

      try {
        const res = await fetch(apiUrl("/api/customer/mytickets"), {
          headers: authHeader(),
        });

        if (!res.ok) throw new Error("Failed to fetch tickets");

        const data = await res.json();

        const mappedTickets = (data.tickets || []).map((t) => ({
          id: t.ticketId,
          title: t.subject,
          type: t.ticketType,
          source: formatTicketSource(t.ticketSource),
          status: t.status,
          date: t.issueDate,
          priority: t.priority,
        }));

        setHistoryItems(mappedTickets);
      } catch (e) {
        console.error(e);
        setHistoryItems([]);
      }
    };

    fetchTickets();
  }, []);

  const counts = useMemo(() => {
    const total = historyItems.length;
    const complaints = historyItems.filter((x) => x.type === "Complaint").length;
    const inquiries = historyItems.filter((x) => x.type === "Inquiry").length;
    return { total, complaints, inquiries };
  }, [historyItems]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();

    return historyItems.filter((item) => {
      const matchesQuery =
        !q || item.id.toLowerCase().includes(q) || item.title.toLowerCase().includes(q);
      const matchesType = type === "All" ? true : item.type === type;
      const matchesStatus = status === "All" ? true : item.status === status;
      return matchesQuery && matchesType && matchesStatus;
    });
  }, [historyItems, query, type, status]);

  const statusOptions = useMemo(() => {
    const orderedDefaults = ["Open", "In Progress", "Assigned", "Escalated", "Overdue", "Resolved", "Reopened"];
    const discovered = Array.from(new Set(historyItems.map((item) => item.status).filter(Boolean)));
    const merged = [...orderedDefaults, ...discovered.filter((value) => !orderedDefaults.includes(value))];
    return ["All", ...merged];
  }, [historyItems]);

  const ordered = useMemo(() => {
    const rank = { Open: 0, "In Progress": 1, Resolved: 2 };

    return filtered
      .map((item, idx) => ({ item, idx }))
      .sort((a, b) => {
        const ra = rank[a.item.status] ?? 999;
        const rb = rank[b.item.status] ?? 999;
        if (ra !== rb) return ra - rb;
        return a.idx - b.idx;
      })
      .map((x) => x.item);
  }, [filtered]);

  const clearFilters = () => {
    setQuery("");
    setType("All");
    setStatus("All");
  };

  return (
    <Layout role="customer">
      <div className="custHistory">
        <PageHeader
          title="My Tickets"
          subtitle="Review your inquiries and complaints."
          actions={
            <button
              type="button"
              className="custBackBtn"
              onClick={() => navigate("/customer")}
              aria-label="Back to landing page"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path
                  d="M15 6l-6 6 6 6"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </button>
          }
        />

        <div className="historyKpis">
          <KpiCard label="Total" value={counts.total} caption="All items" />
          <KpiCard label="Complaints" value={counts.complaints} caption="Submitted" />
          <KpiCard label="Inquiries" value={counts.inquiries} caption="Submitted" />
        </div>

        <div className="historyFilters">
          <PillSearch
            value={query}
            onChange={setQuery}
            placeholder="Search by ID or title..."
            ariaLabel="Search history"
            className="historySearch"
          />

          <PillSelect
            value={type}
            onChange={setType}
            ariaLabel="Filter by type"
            options={["All", "Complaint", "Inquiry"]}
            minWidth={180}
          />

          <PillSelect
            value={status}
            onChange={setStatus}
            ariaLabel="Filter by status"
            options={statusOptions}
            minWidth={180}
          />

          <div className="historyReset">
            <FilterPillButton onClick={clearFilters} label="Reset" />
          </div>
        </div>

        <section className="historyList">
          {filtered.length === 0 ? (
            <div className="historyEmpty">
              <h3 className="historyEmptyTitle">No results found</h3>
              <p className="historyEmptySub">Try adjusting your search or filters.</p>
            </div>
          ) : (
            ordered.map((item) => {
              const workflow = getWorkflowState(item.status);
              const sla = getSlaTargets(item.priority);
              const ctx = getPriorityContext(item.priority);
              return (
                <article
                  key={item.id}
                  className="historyCard historyCard--click"
                  onClick={() => navigate(`/customer/ticket/${item.id}`)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      navigate(`/customer/ticket/${item.id}`);
                    }
                  }}
                >
                  <div className="historyCardLeft">
                    <div className="historyMeta">
                      <span className="historyId">{item.id}</span>
                      <span className="historyDot">•</span>
                      <span className="historyType">{item.type}</span>
                      <span className="historyDot">•</span>
                      <span className="historyType">{item.source}</span>
                      <span className="historyDot">•</span>
                      <span className={`historyStatus status-${item.status.replace(" ", "")}`}>
                        {item.status}
                      </span>
                    </div>

                    <h3 className="historyTitle">{item.title}</h3>

                    <div className="historyFooter">
                      <span className="historyDate">{item.date}</span>
                      <span className="historyDot">•</span>
                      <div className="historyPriorityWrap">
                        <span className="historyPriorityLabel">Priority:</span>
                        <PriorityPill priority={item.priority} />
                      </div>
                    </div>

                <div className="historySlaRow">
                  <span className="historySlaItem">
                    <b>Min response:</b> {sla.minResponse}
                  </span>

                  <span className="historySlaDot">•</span>

                  <span className="historySlaItem">
                    <b>Min resolve:</b> {sla.minResolve}
                  </span>
                </div>

                <div className="historyWorkflow">
                  <div className="historyWorkflowHeader">
                    <span className="historyWorkflowTitle">Workflow Stage</span>
                    <span className={`historyWorkflowOwner owner-${workflow.owner.toLowerCase()}`}>
                      {workflow.owner}
                    </span>
                  </div>

                  <div className="historyWorkflowCurrent">{workflow.stageLabel}</div>

                  <div
                    className="historyWorkflowTrack"
                    aria-label={`Workflow stage ${workflow.stageIndex + 1} of ${WORKFLOW_STAGES.length}`}
                  >
                    {WORKFLOW_STAGES.map((stage, index) => (
                      <div
                        key={stage.id}
                        className={`historyWorkflowDot ${
                          index <= workflow.stageIndex ? "is-done" : ""
                        } ${index === workflow.stageIndex ? "is-current" : ""}`}
                        title={`${stage.label} (${stage.owner})`}
                      />
                    ))}
                  </div>

                  <p className="historyWorkflowNote">{workflow.note}</p>
                </div>

                {/* Friendly priority context */}
                <div
                  className="historyPriorityContext"
                  style={{ background: ctx.bg, borderColor: ctx.border }}
                >
                  <span className="historyPriorityCtxIcon">{ctx.icon}</span>

                  <div>
                    <div
                      className="historyPriorityCtxHeadline"
                      style={{ color: ctx.color }}
                    >
                      {ctx.headline}
                    </div>

                    <p className="historyPriorityCtxReason">{ctx.reason}</p>
                  </div>
                </div>                  
                  </div>

                  <div className="historyCardRight">
                    <button
                      type="button"
                      className="primaryPillBtn"
                      onClick={(e) => {
                        e.stopPropagation();
                        navigate(`/customer/ticket/${item.id}`);
                      }}
                    >
                      View
                    </button>
                  </div>
                </article>
              );
            })
          )}
        </section>
      </div>
    </Layout>
  );
}
