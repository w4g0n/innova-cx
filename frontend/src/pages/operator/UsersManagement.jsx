import { useMemo, useState, useEffect, useRef } from "react";
import Layout from "../../components/Layout";
import PageHeader from "../../components/common/PageHeader";
import KpiCard from "../../components/common/KpiCard";
import PillSearch from "../../components/common/PillSearch";
import PillSelect from "../../components/common/PillSelect";
import ConfirmDialog from "../../components/common/ConfirmDialog";
import "../../components/common/FilterPillButton.css";
import "./UsersManagement.css";

const ROLE_OPTIONS = ["Customer", "Employee", "Manager", "Operator"];

const MOCK_USERS = [
  {
    id: "U-1001",
    fullName: "Hana Ayad",
    email: "hana@innovacx.com",
    phone: "+971 50 123 4567",
    location: "Dubai, UAE",
    role: "operator",
    status: "active",
    createdAt: "2026-02-10",
    lastLogin: "2026-02-14",
  },
  {
    id: "U-1002",
    fullName: "Mariam Ali",
    email: "mariam@innovacx.com",
    phone: "+971 55 888 1010",
    location: "Sharjah, UAE",
    role: "employee",
    status: "active",
    createdAt: "2026-02-09",
    lastLogin: "2026-02-13",
  },
  {
    id: "U-1003",
    fullName: "Omar Hassan",
    email: "omar@innovacx.com",
    phone: "+971 52 333 2222",
    location: "Abu Dhabi, UAE",
    role: "manager",
    status: "inactive",
    createdAt: "2026-02-01",
    lastLogin: "—",
  },
  {
    id: "U-1004",
    fullName: "Salma Mohamed",
    email: "salma@gmail.com",
    phone: "+971 50 999 7777",
    location: "Dubai, UAE",
    role: "customer",
    status: "active",
    createdAt: "2026-01-28",
    lastLogin: "2026-02-12",
  },
];

function matchesQuery(user, q) {
  const s = q.trim().toLowerCase();
  if (!s) return true;
  return (
    user.fullName.toLowerCase().includes(s) ||
    user.email.toLowerCase().includes(s) ||
    user.id.toLowerCase().includes(s) ||
    user.role.toLowerCase().includes(s) ||
    user.status.toLowerCase().includes(s) ||
    user.location.toLowerCase().includes(s)
  );
}

function isValidEmail(email) {
  return /^\S+@\S+\.\S+$/.test(email);
}

function genUserId(existingUsers) {
  const base = 1000 + existingUsers.length + Math.floor(Math.random() * 400);
  return `U-${base}`;
}

export default function UsersManagement() {
  const [users, setUsers] = useState(MOCK_USERS);

  const [query, setQuery]           = useState("");
  const [roleFilter, setRoleFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");

  // 3-dot action menu
  const [openMenuId, setOpenMenuId]     = useState(null);
  const [menuDropUp, setMenuDropUp]     = useState(false);
  const menuRef = useRef(null);

  // MANAGE modal state
  const [openManageModal, setOpenManageModal] = useState(false);
  const [selectedId, setSelectedId] = useState(null);
  const [edit, setEdit] = useState({
    fullName: "", email: "", phone: "", location: "",
    role: "customer", status: "active", password: "", confirmPassword: "",
  });

  // CREATE modal state
  const [openCreateModal, setOpenCreateModal] = useState(false);
  const [create, setCreate] = useState({
    fullName: "", email: "", phone: "", location: "",
    role: "customer", status: "active", password: "", confirmPassword: "",
  });

  const [errors, setErrors] = useState({});
  const [toast, setToast] = useState({ type: "", message: "" });

  // CONFIRM DIALOG state
  const [confirm, setConfirm] = useState({
    open: false, icon: null, title: "", message: "", variant: "danger", onConfirm: null,
  });
  const closeConfirm = () => setConfirm((c) => ({ ...c, open: false }));

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
    const total     = users.length;
    const active    = users.filter((u) => u.status === "active").length;
    const inactive  = users.filter((u) => u.status === "inactive").length;
    const customers = users.filter((u) => u.role === "customer").length;
    const staff     = total - customers;
    return { total, active, inactive, customers, staff };
  }, [users]);

  const resetFilters = () => {
    setQuery("");
    setRoleFilter("all");
    setStatusFilter("all");
  };

  // -------------------------
  // MANAGE USER (EDIT) LOGIC
  // -------------------------
  const openManage = (user) => {
    setToast({ type: "", message: "" });
    setErrors({});
    setSelectedId(user.id);
    setEdit({
      fullName: user.fullName, email: user.email, phone: user.phone,
      location: user.location, role: user.role, status: user.status,
      password: "", confirmPassword: "",
    });
    setOpenManageModal(true);
    setOpenCreateModal(false);
  };

  const closeManage = () => { setOpenManageModal(false); setSelectedId(null); };

  const onEditChange = (e) => {
    const { name, value } = e.target;
    setEdit((p) => ({ ...p, [name]: value }));
  };

  const validateEdit = () => {
    const e = {};
    if (!edit.fullName.trim()) e.fullName = "Full name is required.";
    if (!edit.email.trim()) e.email = "Email is required.";
    if (edit.email && !isValidEmail(edit.email)) e.email = "Invalid email format.";
    if (!edit.phone.trim()) e.phone = "Phone is required.";
    if (!edit.location.trim()) e.location = "Location is required.";
    if (edit.password || edit.confirmPassword) {
      if (!edit.password) e.password = "Password is required.";
      if (edit.password && edit.password.length < 8) e.password = "Min 8 characters.";
      if (edit.confirmPassword !== edit.password) e.confirmPassword = "Passwords do not match.";
    }
    return e;
  };

  const saveChanges = () => {
    const e = validateEdit();
    setErrors(e);
    if (Object.keys(e).length) { setToast({ type: "error", message: "Fix the highlighted fields." }); return; }
    setUsers((prev) =>
      prev.map((u) => {
        if (u.id !== selectedId) return u;
        return { ...u, fullName: edit.fullName, email: edit.email, phone: edit.phone,
          location: edit.location, role: edit.role, status: edit.status,
          lastPasswordChange: edit.password ? new Date().toISOString().slice(0, 10) : u.lastPasswordChange };
      })
    );
    setToast({ type: "success", message: "User updated successfully." });
    closeManage();
  };

  // -------------------------
  // CREATE USER LOGIC
  // -------------------------
  const openCreate = () => {
    setToast({ type: "", message: "" });
    setErrors({});
    setCreate({ fullName: "", email: "", phone: "", location: "", role: "customer", status: "active", password: "", confirmPassword: "" });
    setOpenCreateModal(true);
    setOpenManageModal(false);
  };

  const closeCreate = () => setOpenCreateModal(false);

  const onCreateChange = (e) => {
    const { name, value } = e.target;
    setCreate((p) => ({ ...p, [name]: value }));
  };

  const validateCreate = () => {
    const e = {};
    if (!create.fullName.trim()) e.fullName = "Full name is required.";
    if (!create.email.trim()) e.email = "Email is required.";
    if (create.email && !isValidEmail(create.email)) e.email = "Invalid email format.";
    if (!create.phone.trim()) e.phone = "Phone is required.";
    if (!create.location.trim()) e.location = "Location is required.";
    if (!create.password) e.password = "Password is required.";
    if (create.password && create.password.length < 8) e.password = "Min 8 characters.";
    if (create.confirmPassword !== create.password) e.confirmPassword = "Passwords do not match.";
    return e;
  };

  const createUser = () => {
    const e = validateCreate();
    setErrors(e);
    if (Object.keys(e).length) { setToast({ type: "error", message: "Fix the highlighted fields." }); return; }
    const newUser = {
      id: genUserId(users), fullName: create.fullName, email: create.email,
      phone: create.phone, location: create.location, role: create.role,
      status: create.status, createdAt: new Date().toISOString().slice(0, 10), lastLogin: "—",
    };
    setUsers((prev) => [newUser, ...prev]);
    setToast({ type: "success", message: "User created successfully." });
    closeCreate();
  };

  // -------------------------
  // DELETE / TOGGLE ACTIVE
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
      onConfirm: () => {
        setUsers((prev) => prev.map((u) => u.id === id ? { ...u, status: isActive ? "inactive" : "active" } : u));
        setToast({ type: "success", message: `User ${isActive ? "deactivated" : "activated"}.` });
        closeConfirm();
      },
    });
  };

  const deleteUser = (id) => {
    const user = users.find((u) => u.id === id);
    setConfirm({
      open: true, icon: "🗑️", title: "Delete User",
      message: `Permanently delete "${user?.fullName}"? This cannot be undone.`,
      variant: "danger",
      onConfirm: () => {
        setUsers((prev) => prev.filter((u) => u.id !== id));
        setToast({ type: "success", message: "User deleted." });
        closeConfirm();
      },
    });
  };

  // -------------------------
  // RENDER
  // -------------------------
  return (
    <Layout role="operator">
      <div className="umPage">

        {/* Header */}
        <PageHeader
          title="User Management"
          subtitle="View, search, filter, and manage all users — customers, employees, managers, and operators."
          actions={
            <button className="filterPillBtn" onClick={openCreate}>
              + Create New User
            </button>
          }
        />

        {/* Toast */}
        {toast.message && (
          <div className={`umToast ${toast.type === "success" ? "success" : "error"}`}>
            {toast.message}
          </div>
        )}

        {/* KPI Cards — 5 KPIs, always one row */}
        <section className="umKpis">
          <KpiCard label="Total Users" value={stats.total} />
          <KpiCard label="Active"      value={stats.active} />
          <KpiCard label="Inactive"    value={stats.inactive} />
          <KpiCard label="Customers"   value={stats.customers} />
          <KpiCard label="Staff"       value={stats.staff} />
        </section>

        {/* Search + Filters */}
        <div className="umSearchRow">
          <PillSearch
            value={query}
            onChange={(v) => typeof v === "string" ? setQuery(v) : setQuery(v?.target?.value ?? "")}
            placeholder="Search by name, email, ID, role, or location…"
          />
        </div>

        <div className="umFilters">
          <PillSelect
            value={statusFilter}
            onChange={setStatusFilter}
            ariaLabel="Filter by status"
            options={[
              { value: "all",      label: "All Status" },
              { value: "active",   label: "Active" },
              { value: "inactive", label: "Inactive" },
            ]}
          />
          <PillSelect
            value={roleFilter}
            onChange={setRoleFilter}
            ariaLabel="Filter by role"
            options={[
              { value: "all",      label: "All Roles" },
              { value: "customer", label: "Customer" },
              { value: "employee", label: "Employee" },
              { value: "manager",  label: "Manager" },
              { value: "operator", label: "Operator" },
            ]}
          />
          <button className="filterPillBtn" onClick={resetFilters}>
            ↺ Reset
          </button>
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
                <th>Location</th>
                <th className="umRight">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={7} className="umEmpty">
                    No users match your current filters.
                  </td>
                </tr>
              ) : (
                filtered.map((u) => (
                  <tr key={u.id}>
                    <td className="umLinkish">{u.id}</td>
                    <td className="umNameCell">{u.fullName}</td>
                    <td className="umMuted">{u.email}</td>
                    <td><span className={`umPill role-${u.role}`}>{u.role}</span></td>
                    <td><span className={`umPill status-${u.status}`}>{u.status}</span></td>
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
                              onClick={() => { setOpenMenuId(null); openManage(u); }}
                            >
                              ✏️ Manage
                            </button>
                            <button
                              className={`umMenuItem ${u.status === "active" ? "warning" : ""}`}
                              onClick={() => { setOpenMenuId(null); toggleActive(u.id); }}
                            >
                              {u.status === "active" ? "⚠️ Deactivate" : "✅ Activate"}
                            </button>
                            <button
                              className="umMenuItem danger"
                              onClick={() => { setOpenMenuId(null); deleteUser(u.id); }}
                            >
                              🗑️ Delete
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
          </div>{/* /umTableScroll */}
        </div>

        {/* ==================== */}
        {/* CREATE MODAL         */}
        {/* ==================== */}
        {openCreateModal && (
          <div className="umModalOverlay" onMouseDown={closeCreate}>
            <div className="umModal" onMouseDown={(e) => e.stopPropagation()}>
              <div className="umModalTop">
                <div>
                  <div className="umModalTitle">Create New User</div>
                  <div className="umModalSub">Fill in the details below to add a new user to the system.</div>
                </div>
                <button className="umX" type="button" onClick={closeCreate}>✕</button>
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
                  <input name="phone" value={create.phone} onChange={onCreateChange} placeholder="e.g. +971 50 123 4567" />
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
                      <option key={r} value={r.toLowerCase()}>{r}</option>
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
                <div className="umDivider" />
                <div className="umField">
                  <label>Password *</label>
                  <input type="password" name="password" value={create.password} onChange={onCreateChange} placeholder="Minimum 8 characters" />
                  {errors.password && <span className="umErr">{errors.password}</span>}
                </div>
                <div className="umField">
                  <label>Confirm Password *</label>
                  <input type="password" name="confirmPassword" value={create.confirmPassword} onChange={onCreateChange} placeholder="Re-enter password" />
                  {errors.confirmPassword && <span className="umErr">{errors.confirmPassword}</span>}
                </div>
              </div>

              <div className="umModalActions">
                <button className="umBtnGhost" type="button" onClick={closeCreate}>Cancel</button>
                <button className="filterPillBtn" type="button" onClick={createUser}>Create User</button>
              </div>
            </div>
          </div>
        )}

        {/* ==================== */}
        {/* MANAGE MODAL         */}
        {/* ==================== */}
        {openManageModal && (
          <div className="umModalOverlay" onMouseDown={closeManage}>
            <div className="umModal" onMouseDown={(e) => e.stopPropagation()}>
              <div className="umModalTop">
                <div>
                  <div className="umModalTitle">Manage User</div>
                  <div className="umModalSub">Edit details, role, and status. Leave password blank to keep unchanged.</div>
                </div>
                <button className="umX" type="button" onClick={closeManage}>✕</button>
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
                  <input name="phone" value={edit.phone} onChange={onEditChange} />
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
                      <option key={r} value={r.toLowerCase()}>{r}</option>
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
                <div className="umDivider" />
                <div className="umField">
                  <label>New Password (optional)</label>
                  <input type="password" name="password" value={edit.password} onChange={onEditChange} placeholder="Leave empty to keep current" />
                  {errors.password && <span className="umErr">{errors.password}</span>}
                </div>
                <div className="umField">
                  <label>Confirm New Password</label>
                  <input type="password" name="confirmPassword" value={edit.confirmPassword} onChange={onEditChange} placeholder="Re-enter new password" />
                  {errors.confirmPassword && <span className="umErr">{errors.confirmPassword}</span>}
                </div>
              </div>

              <div className="umModalActions">
                <button className="umBtnGhost" type="button" onClick={closeManage}>Cancel</button>
                <button className="filterPillBtn" type="button" onClick={saveChanges}>Save Changes</button>
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
