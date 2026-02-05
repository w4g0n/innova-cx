import Layout from "../../components/Layout";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import PageHeader from "../../components/common/PageHeader";
import PillSearch from "../../components/common/PillSearch";
import KpiCard from "../../components/common/KpiCard";

import "./ManagerViewEmployees.css";

export default function ManagerViewEmployees() {
  const employees = [
    { name: "Ahmed Hassan", id: "EMP-1023", role: "Senior Technician", completed: 34, inProgress: 3 },
    { name: "Maria Lopez", id: "EMP-1078", role: "Technician", completed: 28, inProgress: 5 },
    { name: "Omar Ali", id: "EMP-1150", role: "Assistant Technician", completed: 19, inProgress: 4 },
    { name: "Sara Ahmed", id: "EMP-1192", role: "Technician", completed: 22, inProgress: 2 },
    { name: "Bilal Khan", id: "EMP-1244", role: "HVAC Specialist", completed: 31, inProgress: 3 },
    { name: "Fatima Noor", id: "EMP-1290", role: "Coordinator", completed: 25, inProgress: 1 },
    { name: "Yousef Karim", id: "EMP-1331", role: "Maintenance Supervisor", completed: 40, inProgress: 6 },
    { name: "Khalid Musa", id: "EMP-1378", role: "Electrician", completed: 27, inProgress: 2 },
  ];

  const [query, setQuery] = useState("");

  const filteredEmployees = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return employees;

    return employees.filter(
      (e) =>
        e.name.toLowerCase().includes(q) ||
        e.id.toLowerCase().includes(q) ||
        e.role.toLowerCase().includes(q)
    );
  }, [employees, query]);

  const kpiEmployees = employees.length;
  const kpiCompleted = employees.reduce((sum, e) => sum + e.completed, 0);
  const kpiInProgress = employees.reduce((sum, e) => sum + e.inProgress, 0);
  const kpiAvg = kpiEmployees ? (kpiCompleted / kpiEmployees).toFixed(1) : "0.0";

  const topPerformer = employees.reduce(
    (best, e) => (e.completed > best.completed ? e : best),
    employees[0]
  );
  const lowestPerformer = employees.reduce(
    (worst, e) => (e.completed < worst.completed ? e : worst),
    employees[0]
  );

  return (
    <Layout role="manager">
      <main className="ve-main">
        <PageHeader
          title="View Employees"
          subtitle="Search employees and access their auto-generated reports."
        />

        <section className="ve-kpiRow">
          <KpiCard label="Employees" value={kpiEmployees} />
          <KpiCard label="Tickets Completed" value={kpiCompleted} />
          <KpiCard label="In Progress" value={kpiInProgress} />
          <KpiCard label="Avg Per Employee" value={kpiAvg} />
          <KpiCard label="Top Performer" value={topPerformer?.name} />
          <KpiCard label="Lowest Performer" value={lowestPerformer?.name} />
        </section>

        <section className="ve-searchRow">
          <PillSearch
            value={query}
            onChange={setQuery}
            placeholder="Search employees by name, ID, or role..."
          />
        </section>

        <section className="ve-tableWrapper">
          <table className="ve-table">
            <thead>
              <tr>
                <th>Employee Name</th>
                <th>Employee ID</th>
                <th>Role</th>
                <th>Tickets Completed</th>
                <th>In Progress</th>
                <th>Report</th>
              </tr>
            </thead>

            <tbody>
              {filteredEmployees.map((e) => (
                <tr key={e.id}>
                  <td className="ve-left">{e.name}</td>
                  <td className="ve-left">{e.id}</td>
                  <td className="ve-left">{e.role}</td>
                  <td>{e.completed}</td>
                  <td>{e.inProgress}</td>
                  <td>
                    <Link className="ve-reportBtn" to={`/manager/employees/${e.id}`}>
                      View report
                    </Link>
                  </td>
                </tr>
              ))}

              {filteredEmployees.length === 0 && (
                <tr>
                  <td className="ve-empty" colSpan={6}>
                    No employees match “{query}”.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </section>
      </main>
    </Layout>
  );
}