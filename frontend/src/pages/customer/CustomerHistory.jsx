import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "../../components/Layout";
import PageHeader from "../../components/common/PageHeader";
import PillSearch from "../../components/common/PillSearch";
import PillSelect from "../../components/common/PillSelect";
import KpiCard from "../../components/common/KpiCard";
import PriorityPill from "../../components/common/PriorityPill";
import FilterPillButton from "../../components/common/FilterPillButton";
import "./CustomerHistory.css";

export default function CustomerHistory() {
  const navigate = useNavigate();

  const [query, setQuery] = useState("");
  const [type, setType] = useState("All");
  const [status, setStatus] = useState("All");

  const historyItems = useMemo(
    () => [
      {
        id: "INC-1024",
        title: "Unable to access my account",
        type: "Inquiry",
        status: "Open",
        date: "Aug 16, 2025",
        priority: "Low",
      },
      {
        id: "CMP-2219",
        title: "Delivery was delayed and support did not respond",
        type: "Complaint",
        status: "In Progress",
        date: "Aug 12, 2025",
        priority: "High",
      },
      {
        id: "CMP-2144",
        title: "Incorrect billing amount on my invoice",
        type: "Complaint",
        status: "Resolved",
        date: "Aug 02, 2025",
        priority: "Medium",
      },
      {
        id: "INC-0997",
        title: "How can I update my email address?",
        type: "Inquiry",
        status: "Resolved",
        date: "Jul 28, 2025",
        priority: "Low",
      },
      {
        id: "CMP-2050",
        title: "App keeps crashing when I submit the form",
        type: "Complaint",
        status: "Open",
        date: "Jul 21, 2025",
        priority: "Critical",
      },
    ],
    []
  );

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
        !q ||
        item.id.toLowerCase().includes(q) ||
        item.title.toLowerCase().includes(q);

      const matchesType = type === "All" ? true : item.type === type;
      const matchesStatus = status === "All" ? true : item.status === status;

      return matchesQuery && matchesType && matchesStatus;
    });
  }, [historyItems, query, type, status]);


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
            options={["All", "Open", "In Progress", "Resolved"]}
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
            ordered.map((item) => (
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
            ))
          )}
        </section>
      </div>
    </Layout>
  );
}
