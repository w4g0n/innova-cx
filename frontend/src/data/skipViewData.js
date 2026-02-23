export function isSkipToken(token) {
  return String(token || "").startsWith("skip-token-");
}

export const skipEmployeeTickets = [
  {
    ticketId: "CX-EMP-1001",
    subject: "Printer not working on floor 2",
    priority: "Medium",
    status: "Assigned",
    issueDate: "2026-02-22",
    respond_time_left_seconds: 4200,
    resolve_time_left_seconds: 19800,
  },
  {
    ticketId: "CX-EMP-1002",
    subject: "Air conditioning leak in meeting room",
    priority: "High",
    status: "In Progress",
    issueDate: "2026-02-23",
    respond_time_left_seconds: 900,
    resolve_time_left_seconds: 8100,
  },
  {
    ticketId: "CX-EMP-1003",
    subject: "Lighting issue in corridor",
    priority: "Low",
    status: "Resolved",
    issueDate: "2026-02-21",
    respond_time_left_seconds: 0,
    resolve_time_left_seconds: 0,
  },
];

export const skipManagerComplaints = [
  {
    id: "CX-MGR-2001",
    subject: "Server room access card broken",
    priority: "high",
    priorityText: "High",
    status: "Assigned",
    assignee: "Maha Ali",
    issueDate: "23/02/2026",
    respondTime: "1 Hour left",
    resolveTime: "5 Hours left",
    action: "Reassign",
  },
  {
    id: "CX-MGR-2002",
    subject: "Water dispenser maintenance overdue",
    priority: "medium",
    priorityText: "Medium",
    status: "Unassigned",
    assignee: "—",
    issueDate: "22/02/2026",
    respondTime: "2 Hours left",
    resolveTime: "1 Day left",
    action: "Assign",
  },
  {
    id: "CX-MGR-2003",
    subject: "Elevator alarm false trigger",
    priority: "critical",
    priorityText: "Critical",
    status: "Overdue",
    assignee: "Omar Khan",
    issueDate: "20/02/2026",
    respondTime: "0 Minutes left",
    resolveTime: "0 Minutes left",
    action: "Reassign",
  },
];

export const skipManagerEmployees = [
  { id: "EMP-001", name: "Maha Ali", role: "Employee", completed: 22, inProgress: 3 },
  { id: "EMP-002", name: "Omar Khan", role: "Employee", completed: 18, inProgress: 4 },
  { id: "EMP-003", name: "Lina Noor", role: "Employee", completed: 27, inProgress: 2 },
];

export const skipManagerKpis = {
  open_complaints: 14,
  in_progress: 7,
  resolved_today: 5,
  active_employees: 3,
  pending_approvals: 2,
};
