import { useMemo, useState, useEffect, useRef } from "react";
import Layout from "../../components/Layout";
import PageHeader from "../../components/common/PageHeader";
import KpiCard from "../../components/common/KpiCard";
import PillSearch from "../../components/common/PillSearch";
import PillSelect from "../../components/common/PillSelect";
import FilterPillButton from "../../components/common/FilterPillButton";
import ConfirmDialog from "../../components/common/ConfirmDialog";
import PhoneInput from "react-phone-input-2";
import "react-phone-input-2/lib/style.css";
import { parsePhoneNumberFromString } from "libphonenumber-js";
import "./UsersManagement.css";

// ── Config ────────────────────────────────────────────────────────────────────
// Support both env names (your env uses VITE_API_BASE_URL)
const API_BASE = 'http://127.0.0.1:8000/api';

// ── Helpers ────────────────────────────────────────────────────────────────────
function authHeaders() {
  const token = localStorage.getItem("access_token");
  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

const ROLE_OPTIONS = ["Customer", "Employee", "Manager", "Operator"];

const DEPARTMENT_OPTIONS = [
  "Facilities Management",
  "Legal and Compliance",
  "Safety & Security",
  "HR",
  "Leasing",
  "Maintenance",
  "IT",
];

function matchesQuery(user, q) {
  const s = q.trim().toLowerCase();
  if (!s) return true;
  return (
    (user.fullName ?? "").toLowerCase().includes(s) ||
    (user.email ?? "").toLowerCase().includes(s) ||
    (user.id ?? "").toLowerCase().includes(s) ||
    (user.role ?? "").toLowerCase().includes(s) ||
    (user.status ?? "").toLowerCase().includes(s) ||
    (user.location ?? "").toLowerCase().includes(s) ||
    (user.department ?? "").toLowerCase().includes(s)
  );
}

function isValidEmail(email) {
  return /^\S+@\S+\.\S+$/.test(email);
}

// react-phone-input-2 stores digits without '+'
function toPhoneInputValue(e164) {
  if (!e164) return "";
  return e164.startsWith("+") ? e164.slice(1) : e164;
}
function fromPhoneInputValue(digits) {
  if (!digits) return "";
  return digits.startsWith("+") ? digits : `+${digits}`;
}
function countryFromE164(e164) {
  const p = parsePhoneNumberFromString(e164 || "");
  return (p?.country || "AE").toLowerCase();
}
function validateE164Phone(e164) {
  if (!e164) return "Phone is required.";
  const p = parsePhoneNumberFromString(e164);
  if (!p || !p.isValid()) return "Invalid phone number.";
  return "";
}

export default function UsersManagement() {
  const [users, setUsers] = useState([]);
  const [loadingUsers, setLoadingUsers] = useState(true);
  const [usersError, setUsersError] = useState("");

  const [query, setQuery] = useState("");
  const [roleFilter, setRoleFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");

  // 3-dot action menu
  const [openMenuId, setOpenMenuId] = useState(null);
  const [menuDropUp, setMenuDropUp] = useState(false);
  const menuRef = useRef(null);

  // MANAGE modal state
  const [openManageModal, setOpenManageModal] = useState(false);
  const [selectedId, setSelectedId] = useState(null);
  const [edit, setEdit] = useState({
    fullName: "",
    email: "",
    phoneE164: "",
    phoneCountry: "ae",
    location: "",
    department: "",
    role: "customer",
    status: "active",
    password: "",
    confirmPassword: "",
  });

  // CREATE modal state
  const [openCreateModal, setOpenCreateModal] = useState(false);
  const [create, setCreate] = useState({
    fullName: "",
    email: "",
    phoneE164: "",
    phoneCountry: "ae",
    location: "",
    department: "",
    role: "customer",
    status: "active",
    password: "",
    confirmPassword: "",
  });

  const [errors, setErrors] = useState({});
  const [toast, setToast] = useState({ type: "", message: "" });

  // Password visibility toggles
  const [showEditPwd, setShowEditPwd] = useState(false);
  const [showEditConfirmPwd, setShowEditConfirmPwd] = useState(false);
  const [showCreatePwd, setShowCreatePwd] = useState(false);
  const [showCreateConfirmPwd, setShowCreateConfirmPwd] = useState(false);

  // CONFIRM DIALOG state
  const [confirm, setConfirm] = useState({
    open: false,
    icon: null,
    title: "",
    message: "",
    variant: "danger",
    onConfirm: null,
  });
  const closeConfirm = () => setConfirm((c) => ({ ...c, open: false }));

  // Auto-dismiss toast after 4 seconds
  useEffect(() => {
    if (!toast.message) return;
    const t = setTimeout(() => setToast({ type: "", message: "" }), 4000);
    return () => clearTimeout(t);
  }, [toast]);

  // Close 3-dot menu on outside click
  useEffect(() => {
    const handler = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setOpenMenuId(null);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  // -------------------------
  // API: LOAD USERS
  // -------------------------
  const fetchUsers = async () => {
    setLoadingUsers(true);
    setUsersError("");
    try {
      const res = await fetch(`${API_BASE}/operator/users`, {
        method: "GET",
        headers: authHeaders(),
      });

      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        const msg = data?.detail ?? `Failed to load users (HTTP ${res.status}).`;
        setUsersError(msg);
        setUsers([]);
        return;
      }

      const list = Array.isArray(data) ? data : [];
      const normalized = list.map((u) => ({
        id: u.id ?? u.userId ?? u.user_id ?? "",
        fullName: u.fullName ?? u.full_name ?? u.name ?? "",
        email: u.email ?? "",
        phone: u.phone ?? "",
        location: u.location ?? "",
        department: u.department ?? "",
        role: (u.role ?? "customer").toLowerCase(),
        status: (u.status ?? "active").toLowerCase(),
        createdAt: u.createdAt ?? u.created_at ?? "",
        lastLogin: u.lastLogin ?? u.last_login ?? "—",
      }));
      setUsers(normalized);
    } catch {
      setUsersError("Failed to load users. Check the backend and network.");
      setUsers([]);
    } finally {
      setLoadingUsers(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  // -------------------------
  // DERIVED DATA
  // -------------------------
  const filtered = useMemo(() => {
    return users.filter((u) => {
      if (!matchesQuery(u, query)) return false;
      if (roleFilter !== "all" && u.role !== roleFilter) return false;
      if (statusFilter !== "all" && u.status !== statusFilter) return false;
      return true;
    });
  }, [users, query, roleFilter, statusFilter]);

  const stats = useMemo(() => {
    const total = users.length;
    const active = users.filter((u) => u.status === "active").length;
    const inactive = users.filter((u) => u.status === "inactive").length;
    const customers = users.filter((u) => u.role === "customer").length;
    const staff = total - customers;
    return { total, active, inactive, customers, staff };
  }, [users]);

  const resetFilters = () => {
    setQuery("");
    setRoleFilter("all");
    setStatusFilter("all");
  };

  // -------------------------
  // MANAGE USER
  // -------------------------
  const openManage = (user) => {
    setToast({ type: "", message: "" });
    setErrors({});
    setSelectedId(user.id);

    const existingPhone = user.phone ?? "";
    setEdit({
      fullName: user.fullName ?? "",
      email: user.email ?? "",
      phoneE164: existingPhone,
      phoneCountry: countryFromE164(existingPhone),
      location: user.location ?? "",
      department: user.department ?? "",
      role: (user.role ?? "customer").toLowerCase(),
      status: (user.status ?? "active").toLowerCase(),
      password: "",
      confirmPassword: "",
    });

    setOpenManageModal(true);
    setOpenCreateModal(false);
  };

  const closeManage = () => {
    setOpenManageModal(false);
    setSelectedId(null);
  };

  const onEditChange = (e) => {
    const { name, value } = e.target;

    // If role becomes customer, clear department automatically
    if (name === "role" && value === "customer") {
      setEdit((p) => ({ ...p, role: value, department: "" }));
      setErrors((prev) => {
        const { department: _department, ...rest } = prev;
        return rest;
      });
      return;
    }

    setEdit((p) => ({ ...p, [name]: value }));
  };

  const validateEdit = () => {
    const e = {};
    if (!edit.fullName.trim()) e.fullName = "Full name is required.";
    if (!edit.email.trim()) e.email = "Email is required.";
    if (edit.email && !isValidEmail(edit.email)) e.email = "Invalid email format.";

    const phoneErr = validateE164Phone(edit.phoneE164);
    if (phoneErr) e.phone = phoneErr;

    if (!edit.location.trim()) e.location = "Location is required.";

    if (edit.role !== "customer" && !edit.department.trim()) {
      e.department = "Department is required for non-customer roles.";
    }

    if (edit.password || edit.confirmPassword) {
      if (!edit.password) e.password = "Password is required.";
      if (edit.password && edit.password.length < 8) e.password = "Min 8 characters.";
      if (edit.confirmPassword !== edit.password) e.confirmPassword = "Passwords do not match.";
    }

    return e;
  };

  const saveChanges = async () => {
    const e = validateEdit();
    setErrors(e);
    if (Object.keys(e).length) {
      setToast({ type: "error", message: "Fix the highlighted fields." });
      return;
    }

    const payload = {
      fullName: edit.fullName.trim(),
      email: edit.email.trim(),
      phone: edit.phoneE164, // E.164
      location: edit.location.trim(),
      role: edit.role,
      status: edit.status,
    };

    if (edit.role !== "customer") payload.department = edit.department.trim();
    if (edit.password) payload.password = edit.password;

    try {
      const res = await fetch(`${API_BASE}/operator/users/${selectedId}`, {
        method: "PUT",
        headers: authHeaders(),
        body: JSON.stringify(payload),
      });

      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        const msg = data?.detail ?? `Failed to update user (HTTP ${res.status}).`;
        setToast({ type: "error", message: msg });
        return;
      }

      setToast({ type: "success", message: data?.message ?? "User updated successfully." });
      closeManage();
      await fetchUsers();
    } catch {
      setToast({ type: "error", message: "Failed to update user. Check the backend and network." });
    }
  };

  // -------------------------
  // CREATE USER
  // -------------------------
  const openCreate = () => {
    setToast({ type: "", message: "" });
    setErrors({});
    setCreate({
      fullName: "",
      email: "",
      phoneE164: "",
      phoneCountry: "ae",
      location: "",
      department: "",
      role: "customer",
      status: "active",
      password: "",
      confirmPassword: "",
    });
    setOpenCreateModal(true);
    setOpenManageModal(false);
  };

  const closeCreate = () => setOpenCreateModal(false);

  const onCreateChange = (e) => {
    const { name, value } = e.target;

    // If role becomes customer, clear department automatically
    if (name === "role" && value === "customer") {
      setCreate((p) => ({ ...p, role: value, department: "" }));
      setErrors((prev) => {
        const { department: _department, ...rest } = prev;
        return rest;
      });
      return;
    }

    setCreate((p) => ({ ...p, [name]: value }));
  };

  const validateCreate = () => {
    const e = {};
    if (!create.fullName.trim()) e.fullName = "Full name is required.";
    if (!create.email.trim()) e.email = "Email is required.";
    if (create.email && !isValidEmail(create.email)) e.email = "Invalid email format.";

    const phoneErr = validateE164Phone(create.phoneE164);
    if (phoneErr) e.phone = phoneErr;

    if (!create.location.trim()) e.location = "Location is required.";

    if (create.role !== "customer" && !create.department.trim()) {
      e.department = "Department is required for non-customer roles.";
    }

    if (!create.password) e.password = "Password is required.";
    if (create.password && create.password.length < 8) e.password = "Min 8 characters.";
    if (create.confirmPassword !== create.password) e.confirmPassword = "Passwords do not match.";

    return e;
  };

  const createUser = async () => {
    const e = validateCreate();
    setErrors(e);
    if (Object.keys(e).length) {
      setToast({ type: "error", message: "Fix the highlighted fields." });
      return;
    }

    const payload = {
      fullName: create.fullName.trim(),
      email: create.email.trim(),
      phone: create.phoneE164, // E.164
      location: create.location.trim(),
      password: create.password,
      role: create.role,
      status: create.status,
      ...(create.role !== "customer" ? { department: create.department.trim() } : {}),
    };

    try {
      const res = await fetch(`${API_BASE}/operator/user-creation`, {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify(payload),
      });

      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        const msg =
          data?.detail ??
          (res.status === 409
            ? "A user with that email already exists."
            : `Failed to create user (HTTP ${res.status}).`);
        setToast({ type: "error", message: msg });
        return;
      }

      setToast({ type: "success", message: data?.message ?? "User created successfully." });
      closeCreate();
      await fetchUsers();
    } catch {
      setToast({ type: "error", message: "Failed to create user. Check the backend and network." });
    }
  };

  // -------------------------
  // ACTIVATE / DEACTIVATE (API)
  // -------------------------
  const toggleActive = (id) => {
    const user = users.find((u) => u.id === id);
    const isActive = user?.status === "active";

    setConfirm({
      open: true,
      icon: isActive ? "⚠️" : "✅",
      title: isActive ? "Deactivate User" : "Activate User",
      message: isActive
        ? `Deactivate "${user?.fullName}"? They will lose system access.`
        : `Activate "${user?.fullName}"? They will regain system access.`,
      variant: isActive ? "warning" : "success",
      onConfirm: async () => {
        try {
          const res = await fetch(`${API_BASE}/operator/users/${id}/status`, {
            method: "PATCH",
            headers: authHeaders(),
            body: JSON.stringify({ status: isActive ? "inactive" : "active" }),
          });
          const data = await res.json().catch(() => ({}));
          if (!res.ok) {
            setToast({
              type: "error",
              message: data?.detail ?? `Failed to update status (HTTP ${res.status}).`,
            });
            closeConfirm();
            return;
          }
          setToast({
            type: "success",
            message: data?.message ?? `User ${isActive ? "deactivated" : "activated"}.`,
          });
          closeConfirm();
          await fetchUsers();
        } catch {
          setToast({ type: "error", message: "Failed to update user status. Check backend/network." });
          closeConfirm();
        }
      },
    });
  };

  // -------------------------
  // DELETE (API)
  // -------------------------
  const deleteUser = (id) => {
    const user = users.find((u) => u.id === id);

    setConfirm({
      open: true,
      icon: "🗑️",
      title: "Delete User",
      message: `Permanently delete "${user?.fullName}"? This cannot be undone.`,
      variant: "danger",
      onConfirm: async () => {
        try {
          const res = await fetch(`${API_BASE}/operator/users/${id}`, {
            method: "DELETE",
            headers: authHeaders(),
          });
          const data = await res.json().catch(() => ({}));
          if (!res.ok) {
            setToast({
              type: "error",
              message: data?.detail ?? `Failed to delete user (HTTP ${res.status}).`,
            });
            closeConfirm();
            return;
          }
          setToast({ type: "success", message: data?.message ?? "User deleted." });
          closeConfirm();
          await fetchUsers();
        } catch {
          setToast({ type: "error", message: "Failed to delete user. Check backend/network." });
          closeConfirm();
        }
      },
    });
  };

  // -------------------------
  // RENDER
  // -------------------------
  return (
    <Layout role="operator">
      <div className="umPage">
        <PageHeader
          title="User Management"
          subtitle="View, search, filter, and manage all users — customers, employees, managers, and operators."
          actions={
            <button className="filterPillBtn" onClick={openCreate}>
              + Create New User
            </button>
          }
        />

        {/* Load/Error banner */}
        {loadingUsers && (
          <div style={{ marginTop: 12, padding: 12, borderRadius: 12, background: "rgba(0,0,0,0.04)" }}>
            Loading users…
          </div>
        )}
        {!loadingUsers && usersError && (
          <div style={{ marginTop: 12, padding: 12, borderRadius: 12, background: "rgba(255,0,0,0.06)" }}>
            {usersError}
            <button
              onClick={fetchUsers}
              style={{ marginLeft: 10, background: "transparent", border: "none", textDecoration: "underline", cursor: "pointer" }}
            >
              Retry
            </button>
          </div>
        )}

        {/* Toast */}
        {toast.message && (
          <div className={`umToast ${toast.type === "success" ? "success" : "error"}`}>
            {toast.message}
          </div>
        )}

        {/* KPI Cards — 5 KPIs */}
        <section className="umKpis">
          <KpiCard label="Total Users" value={stats.total} />
          <KpiCard label="Active" value={stats.active} />
          <KpiCard label="Inactive" value={stats.inactive} />
          <KpiCard label="Customers" value={stats.customers} />
          <KpiCard label="Staff" value={stats.staff} />
        </section>

        {/* Search + Filters */}
        <div className="umSearchRow">
          <PillSearch
            value={query}
            onChange={(v) => (typeof v === "string" ? setQuery(v) : setQuery(v?.target?.value ?? ""))}
            placeholder="Search by name, email, ID, role, department, or location…"
          />
        </div>

        <div className="umFilters">
          <PillSelect
            value={statusFilter}
            onChange={setStatusFilter}
            ariaLabel="Filter by status"
            options={[
              { value: "all", label: "All Status" },
              { value: "active", label: "Active" },
              { value: "inactive", label: "Inactive" },
            ]}
          />
          <PillSelect
            value={roleFilter}
            onChange={setRoleFilter}
            ariaLabel="Filter by role"
            options={[
              { value: "all", label: "All Roles" },
              { value: "customer", label: "Customer" },
              { value: "employee", label: "Employee" },
              { value: "manager", label: "Manager" },
              { value: "operator", label: "Operator" },
            ]}
          />
          <FilterPillButton onClick={resetFilters} label="Reset" />
        </div>

        {/* Table */}
        <div className="umTableCard">
          <div className="umTableScroll">
            <table className="umTable">
              <thead>
                <tr>
                  <th>User ID</th>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Role</th>
                  <th>Status</th>
                  <th>Department</th>
                  <th>Location</th>
                  <th className="umRight">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="umEmpty">
                      No users match your current filters.
                    </td>
                  </tr>
                ) : (
                  filtered.map((u) => (
                    <tr key={u.id}>
                      <td className="umLinkish">{u.id}</td>
                      <td className="umNameCell">{u.fullName}</td>
                      <td className="umMuted">{u.email}</td>
                      <td>
                        <span className={`umPill role-${u.role}`}>{u.role}</span>
                      </td>
                      <td>
                        <span className={`umPill status-${u.status}`}>{u.status}</span>
                      </td>
                      <td className="umMuted">{u.department || "—"}</td>
                      <td className="umMuted">{u.location}</td>
                      <td className="umRight">
                        {/* 3-dot dropdown menu */}
                        <div className="umMenuWrap" ref={openMenuId === u.id ? menuRef : null}>
                          <button
                            className="umMenuBtn"
                            aria-label="Actions"
                            title="Actions"
                            onClick={(e) => {
                              e.stopPropagation();
                              const rect = e.currentTarget.getBoundingClientRect();
                              setMenuDropUp(window.innerHeight - rect.bottom < 150);
                              setOpenMenuId((prev) => (prev === u.id ? null : u.id));
                            }}
                          >
                            ⋮
                          </button>

                          {openMenuId === u.id && (
                            <div className={`umMenuDropdown${menuDropUp ? " umMenuDropdown--up" : ""}`}>
                              <button
                                className="umMenuItem"
                                onClick={() => {
                                  setOpenMenuId(null);
                                  openManage(u);
                                }}
                              >
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                                Manage
                              </button>

                              <button
                                className={`umMenuItem ${u.status === "active" ? "warning" : ""}`}
                                onClick={() => {
                                  setOpenMenuId(null);
                                  toggleActive(u.id);
                                }}
                              >
                                {u.status === "active"
                                  ? <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="8" y1="12" x2="16" y2="12"/></svg>
                                  : <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
                                }
                                {u.status === "active" ? "Deactivate" : "Activate"}
                              </button>

                              <button
                                className="umMenuItem danger"
                                onClick={() => {
                                  setOpenMenuId(null);
                                  deleteUser(u.id);
                                }}
                              >
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/></svg>
                                Delete
                              </button>
                            </div>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* CREATE MODAL */}
        {openCreateModal && (
          <div className="umModalOverlay" onMouseDown={closeCreate}>
            <div className="umModal" onMouseDown={(e) => e.stopPropagation()}>
              <div className="umModalTop">
                <div>
                  <div className="umModalTitle">Create New User</div>
                  <div className="umModalSub">Fill in the details below to add a new user to the system.</div>
                </div>
                <button className="umX" type="button" onClick={closeCreate}>
                  ✕
                </button>
              </div>

              <div className="umModalGrid">
                <div className="umField">
                  <label>Full Name *</label>
                  <input name="fullName" value={create.fullName} onChange={onCreateChange} placeholder="e.g. Hana Ayad" />
                  {errors.fullName && <span className="umErr">{errors.fullName}</span>}
                </div>

                <div className="umField">
                  <label>Email *</label>
                  <input name="email" value={create.email} onChange={onCreateChange} placeholder="e.g. hana@company.com" />
                  {errors.email && <span className="umErr">{errors.email}</span>}
                </div>

                <div className="umField">
                  <label>Phone *</label>
                  <div className="umPhoneWrap">
                    <PhoneInput
                      country={create.phoneCountry}
                      value={toPhoneInputValue(create.phoneE164)}
                      onChange={(digits, countryData) => {
                      let cleanDigits = digits || "";
                      const dialCode = countryData?.dialCode || "";
                      if (cleanDigits.startsWith(dialCode + "0")) {
                        cleanDigits = dialCode + cleanDigits.slice(dialCode.length + 1);
                      }
                      const e164 = cleanDigits ? `+${cleanDigits}` : "";
                      setCreate((p) => ({
                        ...p,
                        phoneE164: e164,
                        phoneCountry: (countryData?.countryCode || "ae").toLowerCase(),
                      }));
                      setErrors((prev) => {
                        const { phone: _phone, ...rest } = prev;
                        return rest;
                      });
                    }}
                      enableSearch
                      autoFormat={false}
                      countryCodeEditable={false}
                      inputProps={{ name: "phone", required: true }}
                    />
                  </div>
                  {errors.phone && <span className="umErr">{errors.phone}</span>}
                </div>

                <div className="umField">
                  <label>Location *</label>
                  <input name="location" value={create.location} onChange={onCreateChange} placeholder="e.g. Dubai, UAE" />
                  {errors.location && <span className="umErr">{errors.location}</span>}
                </div>

                <div className="umField">
                  <label>Role *</label>
                  <select name="role" value={create.role} onChange={onCreateChange}>
                    {ROLE_OPTIONS.map((r) => (
                      <option key={r} value={r.toLowerCase()}>
                        {r}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="umField">
                  <label>Status</label>
                  <select name="status" value={create.status} onChange={onCreateChange}>
                    <option value="active">Active</option>
                    <option value="inactive">Inactive</option>
                  </select>
                </div>

                {/* Department only for non-customer */}
                {create.role !== "customer" && (
                  <div className="umField">
                    <label>Department *</label>
                    <select name="department" value={create.department} onChange={onCreateChange}>
                      <option value="">Select department…</option>
                      {DEPARTMENT_OPTIONS.map((d) => (
                        <option key={d} value={d}>{d}</option>
                      ))}
                    </select>
                    {errors.department && <span className="umErr">{errors.department}</span>}
                  </div>
                )}

                <div className="umDivider" />

                <div className="umField">
                  <label>Password *</label>
                  <div className="umPwdWrap">
                    <input type={showCreatePwd ? "text" : "password"} name="password" value={create.password} onChange={onCreateChange} placeholder="Minimum 8 characters" />
                    <button type="button" className="umEyeBtn" onClick={() => setShowCreatePwd(v => !v)} tabIndex={-1}>
                      {showCreatePwd
                        ? <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/><path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
                        : <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                      }
                    </button>
                  </div>
                  {errors.password && <span className="umErr">{errors.password}</span>}
                </div>

                <div className="umField">
                  <label>Confirm Password *</label>
                  <div className="umPwdWrap">
                    <input type={showCreateConfirmPwd ? "text" : "password"} name="confirmPassword" value={create.confirmPassword} onChange={onCreateChange} placeholder="Re-enter password" />
                    <button type="button" className="umEyeBtn" onClick={() => setShowCreateConfirmPwd(v => !v)} tabIndex={-1}>
                      {showCreateConfirmPwd
                        ? <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/><path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
                        : <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                      }
                    </button>
                  </div>
                  {errors.confirmPassword && <span className="umErr">{errors.confirmPassword}</span>}
                </div>
              </div>

              <div className="umModalActions">
                <button className="umBtnGhost" type="button" onClick={closeCreate}>
                  Cancel
                </button>
                <button className="filterPillBtn" type="button" onClick={createUser}>
                  Create User
                </button>
              </div>
            </div>
          </div>
        )}

        {/* MANAGE MODAL */}
        {openManageModal && (
          <div className="umModalOverlay" onMouseDown={closeManage}>
            <div className="umModal" onMouseDown={(e) => e.stopPropagation()}>
              <div className="umModalTop">
                <div>
                  <div className="umModalTitle">Manage User</div>
                  <div className="umModalSub">Edit details, role, and status. Leave password blank to keep unchanged.</div>
                </div>
                <button className="umX" type="button" onClick={closeManage}>
                  ✕
                </button>
              </div>

              <div className="umModalGrid">
                <div className="umField">
                  <label>Full Name *</label>
                  <input name="fullName" value={edit.fullName} onChange={onEditChange} />
                  {errors.fullName && <span className="umErr">{errors.fullName}</span>}
                </div>

                <div className="umField">
                  <label>Email *</label>
                  <input name="email" value={edit.email} onChange={onEditChange} />
                  {errors.email && <span className="umErr">{errors.email}</span>}
                </div>

                <div className="umField">
                  <label>Phone *</label>
                  <div className="umPhoneWrap">
                    <PhoneInput
                      country={edit.phoneCountry}
                      value={toPhoneInputValue(edit.phoneE164)}
                      onChange={(digits, countryData) => {
                        const e164 = fromPhoneInputValue(digits);
                        setEdit((p) => ({
                          ...p,
                          phoneE164: e164,
                          phoneCountry: (countryData?.countryCode || "ae").toLowerCase(),
                        }));
                        setErrors((prev) => {
                          const { phone: _phone, ...rest } = prev;
                          return rest;
                        });
                      }}
                      enableSearch
                      autoFormat={false}
                      countryCodeEditable={false}
                      inputProps={{ name: "phone", required: true }}
                    />
                  </div>
                  {errors.phone && <span className="umErr">{errors.phone}</span>}
                </div>

                <div className="umField">
                  <label>Location *</label>
                  <input name="location" value={edit.location} onChange={onEditChange} />
                  {errors.location && <span className="umErr">{errors.location}</span>}
                </div>

                <div className="umField">
                  <label>Role *</label>
                  <select name="role" value={edit.role} onChange={onEditChange}>
                    {ROLE_OPTIONS.map((r) => (
                      <option key={r} value={r.toLowerCase()}>
                        {r}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="umField">
                  <label>Status</label>
                  <select name="status" value={edit.status} onChange={onEditChange}>
                    <option value="active">Active</option>
                    <option value="inactive">Inactive</option>
                  </select>
                </div>

                {/* Department only for non-customer */}
                {edit.role !== "customer" && (
                  <div className="umField">
                    <label>Department *</label>
                    <select name="department" value={edit.department} onChange={onEditChange}>
                      <option value="">Select department…</option>
                      {DEPARTMENT_OPTIONS.map((d) => (
                        <option key={d} value={d}>{d}</option>
                      ))}
                    </select>
                    {errors.department && <span className="umErr">{errors.department}</span>}
                  </div>
                )}

                <div className="umDivider" />

                <div className="umField">
                  <label>New Password (optional)</label>
                  <div className="umPwdWrap">
                    <input type={showEditPwd ? "text" : "password"} name="password" value={edit.password} onChange={onEditChange} placeholder="Leave empty to keep current" />
                    <button type="button" className="umEyeBtn" onClick={() => setShowEditPwd(v => !v)} tabIndex={-1}>
                      {showEditPwd
                        ? <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/><path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
                        : <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                      }
                    </button>
                  </div>
                  {errors.password && <span className="umErr">{errors.password}</span>}
                </div>

                <div className="umField">
                  <label>Confirm New Password</label>
                  <div className="umPwdWrap">
                    <input
                      type={showEditConfirmPwd ? "text" : "password"}
                      name="confirmPassword"
                      value={edit.confirmPassword}
                      onChange={onEditChange}
                      placeholder="Re-enter new password"
                    />
                    <button type="button" className="umEyeBtn" onClick={() => setShowEditConfirmPwd(v => !v)} tabIndex={-1}>
                      {showEditConfirmPwd
                        ? <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/><path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
                        : <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                      }
                    </button>
                  </div>
                  {errors.confirmPassword && <span className="umErr">{errors.confirmPassword}</span>}
                </div>
              </div>

              <div className="umModalActions">
                <button className="umBtnGhost" type="button" onClick={closeManage}>
                  Cancel
                </button>
                <button className="filterPillBtn" type="button" onClick={saveChanges}>
                  Save Changes
                </button>
              </div>
            </div>
          </div>
        )}

        {/* CONFIRM DIALOG */}
        <ConfirmDialog
          open={confirm.open}
          icon={confirm.icon}
          title={confirm.title}
          message={confirm.message}
          variant={confirm.variant}
          confirmLabel={confirm.variant === "danger" ? "Yes, Delete" : "Confirm"}
          onConfirm={confirm.onConfirm}
          onCancel={closeConfirm}
        />
      </div>
    </Layout>
  );
}
