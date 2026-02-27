import { useMemo, useState } from "react";
import Layout from "../../components/Layout";
import "./UsersManagement.css";

const ROLE_OPTIONS = ["customer", "employee", "manager", "operator"];

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
  // make a simple unique id
  const base = 1000 + existingUsers.length + Math.floor(Math.random() * 400);
  return `U-${base}`;
}

export default function UsersManagement() {
  const [users, setUsers] = useState(MOCK_USERS);

  const [query, setQuery] = useState("");
  const [roleFilter, setRoleFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");

  // MANAGE modal state
  const [openManageModal, setOpenManageModal] = useState(false);
  const [selectedId, setSelectedId] = useState(null);

  const [edit, setEdit] = useState({
    fullName: "",
    email: "",
    phone: "",
    location: "",
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
    phone: "",
    location: "",
    role: "customer",
    status: "active",
    password: "",
    confirmPassword: "",
  });

  const [errors, setErrors] = useState({});
  const [toast, setToast] = useState({ type: "", message: "" });

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

  // -------------------------
  // MANAGE USER (EDIT) LOGIC
  // -------------------------
  const openManage = (user) => {
    setToast({ type: "", message: "" });
    setErrors({});
    setSelectedId(user.id);
    setEdit({
      fullName: user.fullName,
      email: user.email,
      phone: user.phone,
      location: user.location,
      role: user.role,
      status: user.status,
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
    setEdit((p) => ({ ...p, [name]: value }));
  };

  const validateEdit = () => {
    const e = {};
    if (!edit.fullName.trim()) e.fullName = "Full name is required.";
    if (!edit.email.trim()) e.email = "Email is required.";
    if (edit.email && !isValidEmail(edit.email)) e.email = "Invalid email format.";
    if (!edit.phone.trim()) e.phone = "Phone is required.";
    if (!edit.location.trim()) e.location = "Location is required.";
    if (!ROLE_OPTIONS.includes(edit.role)) e.role = "Invalid role.";

    // password change optional (only validate if typed)
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
    if (Object.keys(e).length) {
      setToast({ type: "error", message: "Fix the highlighted fields." });
      return;
    }

    setUsers((prev) =>
      prev.map((u) => {
        if (u.id !== selectedId) return u;

        const passwordChanged = !!edit.password;

        return {
          ...u,
          fullName: edit.fullName,
          email: edit.email,
          phone: edit.phone,
          location: edit.location,
          role: edit.role,
          status: edit.status,
          lastPasswordChange: passwordChanged
            ? new Date().toISOString().slice(0, 10)
            : u.lastPasswordChange,
        };
      })
    );

    console.log("UPDATE USER (frontend mock):", {
      id: selectedId,
      fullName: edit.fullName,
      email: edit.email,
      phone: edit.phone,
      location: edit.location,
      role: edit.role,
      status: edit.status,
      passwordChanged: !!edit.password,
    });

    setToast({ type: "success", message: "User updated (mock). Check console." });
    closeManage();
  };

  // -------------------------
  // CREATE USER LOGIC (MODAL)
  // -------------------------
  const openCreate = () => {
    setToast({ type: "", message: "" });
    setErrors({});
    setCreate({
      fullName: "",
      email: "",
      phone: "",
      location: "",
      role: "customer",
      status: "active",
      password: "",
      confirmPassword: "",
    });
    setOpenCreateModal(true);
    setOpenManageModal(false);
  };

  const closeCreate = () => {
    setOpenCreateModal(false);
  };

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
    if (!ROLE_OPTIONS.includes(create.role)) e.role = "Invalid role.";

    // password REQUIRED for create
    if (!create.password) e.password = "Password is required.";
    if (create.password && create.password.length < 8) e.password = "Min 8 characters.";
    if (create.confirmPassword !== create.password) e.confirmPassword = "Passwords do not match.";

    return e;
  };

  const createUser = () => {
    const e = validateCreate();
    setErrors(e);
    if (Object.keys(e).length) {
      setToast({ type: "error", message: "Fix the highlighted fields." });
      return;
    }

    const newUser = {
      id: genUserId(users),
      fullName: create.fullName,
      email: create.email,
      phone: create.phone,
      location: create.location,
      role: create.role,
      status: create.status,
      createdAt: new Date().toISOString().slice(0, 10),
      lastLogin: "—",
    };

    setUsers((prev) => [newUser, ...prev]);

    // FRONTEND ONLY: don't store raw password anywhere
    console.log("CREATE USER (frontend mock):", {
      ...newUser,
      passwordProvided: true,
    });

    setToast({ type: "success", message: "User created (mock). Check console." });
    closeCreate();
  };

  // -------------------------
  // OTHER ACTIONS
  // -------------------------
  const toggleActive = (id) => {
    setUsers((prev) =>
      prev.map((u) =>
        u.id === id ? { ...u, status: u.status === "active" ? "inactive" : "active" } : u
      )
    );
  };

  const deleteUser = (id) => {
    const ok = window.confirm("Delete this user? This is frontend-only for now.");
    if (!ok) return;

    setUsers((prev) => prev.filter((u) => u.id !== id));
    console.log("DELETE USER (frontend mock):", { id });
    setToast({ type: "success", message: "User deleted (mock)." });
  };

  return (
    <Layout role="operator">
      <div className="umPage">
        <div className="umTop">
          <div>
            <h1 className="umTitle">Users Viewer and Management</h1>
            <p className="umSub">
              View, search, filter, and manage all users (customers, employees, managers, operators).
            </p>
          </div>

          {/* ✅ now opens popup instead of navigating */}
          <button className="umBtnPrimary" onClick={openCreate}>
            Create New User
          </button>
        </div>

        {toast.message ? (
          <div className={`umToast ${toast.type === "success" ? "success" : "error"}`}>
            {toast.message}
          </div>
        ) : null}

        <div className="umKpis">
          <div className="umKpi">
            <div className="umKpiLabel">TOTAL USERS</div>
            <div className="umKpiValue">{stats.total}</div>
          </div>
          <div className="umKpi">
            <div className="umKpiLabel">ACTIVE</div>
            <div className="umKpiValue">{stats.active}</div>
          </div>
          <div className="umKpi">
            <div className="umKpiLabel">INACTIVE</div>
            <div className="umKpiValue">{stats.inactive}</div>
          </div>
          <div className="umKpi">
            <div className="umKpiLabel">CUSTOMERS</div>
            <div className="umKpiValue">{stats.customers}</div>
          </div>
          <div className="umKpi">
            <div className="umKpiLabel">STAFF</div>
            <div className="umKpiValue">{stats.staff}</div>
          </div>
        </div>

        <div className="umSearchBar">
          <span className="umSearchIcon">🔎</span>
          <input
            className="umSearchInput"
            placeholder="Search users by ID, name, email, role, location..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>

        <div className="umFilters">
          <select
            className="umSelect"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="all">All Status</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>

          <select
            className="umSelect"
            value={roleFilter}
            onChange={(e) => setRoleFilter(e.target.value)}
          >
            <option value="all">All Roles</option>
            <option value="customer">Customer</option>
            <option value="employee">Employee</option>
            <option value="manager">Manager</option>
            <option value="operator">Operator</option>
          </select>

          <button
            className="umBtnGhost"
            onClick={() => {
              setQuery("");
              setRoleFilter("all");
              setStatusFilter("all");
            }}
          >
            Reset
          </button>
        </div>

        <div className="umTableCard">
          <table className="umTable">
            <thead>
              <tr>
                <th>User ID</th>
                <th>Name</th>
                <th>Email</th>
                <th>Role</th>
                <th>Status</th>
                <th>Location</th>
                <th>Phone</th>
                <th className="umRight">Actions</th>
              </tr>
            </thead>

            <tbody>
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={8} className="umEmpty">
                    No users found.
                  </td>
                </tr>
              ) : (
                filtered.map((u) => (
                  <tr key={u.id}>
                    <td className="umLinkish">{u.id}</td>
                    <td>{u.fullName}</td>
                    <td>{u.email}</td>
                    <td>
                      <span className={`umPill role-${u.role}`}>{u.role}</span>
                    </td>
                    <td>
                      <span className={`umPill status-${u.status}`}>{u.status}</span>
                    </td>
                    <td>{u.location}</td>
                    <td>{u.phone}</td>
                    <td className="umRight">
                      <div className="umActions">
                        <button className="umBtnSmall" onClick={() => openManage(u)}>
                          Manage
                        </button>
                        <button
                          className="umBtnSmall secondary"
                          onClick={() => toggleActive(u.id)}
                        >
                          {u.status === "active" ? "Deactivate" : "Activate"}
                        </button>
                        <button
                          className="umBtnSmall danger"
                          onClick={() => deleteUser(u.id)}
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* --------------------- */}
        {/* CREATE MODAL */}
        {/* --------------------- */}
        {openCreateModal ? (
          <div className="umModalOverlay" onMouseDown={closeCreate}>
            <div className="umModal" onMouseDown={(e) => e.stopPropagation()}>
              <div className="umModalTop">
                <div>
                  <div className="umModalTitle">Create New User</div>
                  <div className="umModalSub">
                    Frontend-only for now. Your friend can connect backend later.
                  </div>
                </div>
                <button className="umX" onClick={closeCreate}>
                  ✕
                </button>
              </div>

              <div className="umModalGrid">
                <div className="umField">
                  <label>Full Name *</label>
                  <input name="fullName" value={create.fullName} onChange={onCreateChange} />
                  {errors.fullName ? <span className="umErr">{errors.fullName}</span> : null}
                </div>

                <div className="umField">
                  <label>Email *</label>
                  <input name="email" value={create.email} onChange={onCreateChange} />
                  {errors.email ? <span className="umErr">{errors.email}</span> : null}
                </div>

                <div className="umField">
                  <label>Phone *</label>
                  <input name="phone" value={create.phone} onChange={onCreateChange} />
                  {errors.phone ? <span className="umErr">{errors.phone}</span> : null}
                </div>

                <div className="umField">
                  <label>Location *</label>
                  <input name="location" value={create.location} onChange={onCreateChange} />
                  {errors.location ? <span className="umErr">{errors.location}</span> : null}
                </div>

                <div className="umField">
                  <label>Role *</label>
                  <select name="role" value={create.role} onChange={onCreateChange}>
                    {ROLE_OPTIONS.map((r) => (
                      <option key={r} value={r}>
                        {r}
                      </option>
                    ))}
                  </select>
                  {errors.role ? <span className="umErr">{errors.role}</span> : null}
                </div>

                <div className="umField">
                  <label>Status</label>
                  <select name="status" value={create.status} onChange={onCreateChange}>
                    <option value="active">active</option>
                    <option value="inactive">inactive</option>
                  </select>
                </div>

                <div className="umDivider" />

                <div className="umField">
                  <label>Password *</label>
                  <input
                    type="password"
                    name="password"
                    value={create.password}
                    onChange={onCreateChange}
                    placeholder="Minimum 8 characters"
                  />
                  {errors.password ? <span className="umErr">{errors.password}</span> : null}
                </div>

                <div className="umField">
                  <label>Confirm Password *</label>
                  <input
                    type="password"
                    name="confirmPassword"
                    value={create.confirmPassword}
                    onChange={onCreateChange}
                  />
                  {errors.confirmPassword ? (
                    <span className="umErr">{errors.confirmPassword}</span>
                  ) : null}
                </div>
              </div>

              <div className="umModalActions">
                <button className="umBtnGhost" onClick={closeCreate}>
                  Cancel
                </button>
                <button className="umBtnPrimary" onClick={createUser}>
                  Create User
                </button>
              </div>
            </div>
          </div>
        ) : null}

        {/* --------------------- */}
        {/* MANAGE MODAL */}
        {/* --------------------- */}
        {openManageModal ? (
          <div className="umModalOverlay" onMouseDown={closeManage}>
            <div className="umModal" onMouseDown={(e) => e.stopPropagation()}>
              <div className="umModalTop">
                <div>
                  <div className="umModalTitle">Manage User</div>
                  <div className="umModalSub">
                    Edit user details, role, status, and optionally change password.
                  </div>
                </div>
                <button className="umX" onClick={closeManage}>
                  ✕
                </button>
              </div>

              <div className="umModalGrid">
                <div className="umField">
                  <label>Full Name *</label>
                  <input name="fullName" value={edit.fullName} onChange={onEditChange} />
                  {errors.fullName ? <span className="umErr">{errors.fullName}</span> : null}
                </div>

                <div className="umField">
                  <label>Email *</label>
                  <input name="email" value={edit.email} onChange={onEditChange} />
                  {errors.email ? <span className="umErr">{errors.email}</span> : null}
                </div>

                <div className="umField">
                  <label>Phone *</label>
                  <input name="phone" value={edit.phone} onChange={onEditChange} />
                  {errors.phone ? <span className="umErr">{errors.phone}</span> : null}
                </div>

                <div className="umField">
                  <label>Location *</label>
                  <input name="location" value={edit.location} onChange={onEditChange} />
                  {errors.location ? <span className="umErr">{errors.location}</span> : null}
                </div>

                <div className="umField">
                  <label>Role *</label>
                  <select name="role" value={edit.role} onChange={onEditChange}>
                    {ROLE_OPTIONS.map((r) => (
                      <option key={r} value={r}>
                        {r}
                      </option>
                    ))}
                  </select>
                  {errors.role ? <span className="umErr">{errors.role}</span> : null}
                </div>

                <div className="umField">
                  <label>Status</label>
                  <select name="status" value={edit.status} onChange={onEditChange}>
                    <option value="active">active</option>
                    <option value="inactive">inactive</option>
                  </select>
                </div>

                <div className="umDivider" />

                <div className="umField">
                  <label>New Password (optional)</label>
                  <input
                    type="password"
                    name="password"
                    value={edit.password}
                    onChange={onEditChange}
                    placeholder="Leave empty to keep unchanged"
                  />
                  {errors.password ? <span className="umErr">{errors.password}</span> : null}
                </div>

                <div className="umField">
                  <label>Confirm New Password (optional)</label>
                  <input
                    type="password"
                    name="confirmPassword"
                    value={edit.confirmPassword}
                    onChange={onEditChange}
                  />
                  {errors.confirmPassword ? (
                    <span className="umErr">{errors.confirmPassword}</span>
                  ) : null}
                </div>
              </div>

              <div className="umModalActions">
                <button className="umBtnGhost" onClick={closeManage}>
                  Cancel
                </button>
                <button className="umBtnPrimary" onClick={saveChanges}>
                  Save Changes
                </button>
              </div>
            </div>
          </div>
        ) : null}
      </div>
    </Layout>
  );
}