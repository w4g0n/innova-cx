import Layout from "../../components/Layout"; // adjust if your Layout path is different
import { useMemo, useState } from "react";
import "./UserAccountManagement.css";

const initialForm = {
  // identity
  fullName: "",
  email: "",
  phone: "",
  location: "",

  // auth (backend will hash later)
  password: "",
  confirmPassword: "",

  // org + access
  role: "employee", // employee | manager | operator | customer
  department: "",
  status: "active", // active | inactive
};

function validate(form) {
  const errors = {};

  if (!form.fullName.trim()) errors.fullName = "Full name is required.";
  if (!form.email.trim()) errors.email = "Email is required.";
  if (form.email && !/^\S+@\S+\.\S+$/.test(form.email)) errors.email = "Invalid email format.";
  if (!form.phone.trim()) errors.phone = "Phone is required.";

  if (!form.location.trim()) errors.location = "Location is required.";

  if (!form.password) errors.password = "Password is required.";
  if (form.password && form.password.length < 8) errors.password = "Password must be at least 8 characters.";
  if (form.confirmPassword !== form.password) errors.confirmPassword = "Passwords do not match.";

  if (!form.role) errors.role = "Role is required.";
  if (!form.department.trim()) errors.department = "Department is required.";

  return errors;
}

export default function UserAccountManagement() {
  const [form, setForm] = useState(initialForm);
  const [touched, setTouched] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState({ type: "", message: "" });

  const errors = useMemo(() => validate(form), [form]);
  const isValid = Object.keys(errors).length === 0;

  const onChange = (e) => {
    const { name, value } = e.target;
    setForm((p) => ({ ...p, [name]: value }));
  };

  const onBlur = (e) => {
    setTouched((p) => ({ ...p, [e.target.name]: true }));
  };

  const showError = (key) => touched[key] && errors[key];

  const reset = () => {
    setForm(initialForm);
    setTouched({});
    setToast({ type: "", message: "" });
  };

  const onSubmit = async (e) => {
    e.preventDefault();

    // mark required fields as touched so errors show
    setTouched({
      fullName: true,
      email: true,
      phone: true,
      location: true,
      password: true,
      confirmPassword: true,
      role: true,
      department: true,
    });

    if (!isValid) {
      setToast({ type: "error", message: "Please fix the highlighted fields." });
      return;
    }

    setSubmitting(true);
    setToast({ type: "", message: "" });

    try {
      // FRONTEND ONLY (no backend):
      const payload = { ...form };
      delete payload.confirmPassword; // never send confirmPassword

      console.log("CREATE USER (frontend-only mock):", payload);

      setToast({ type: "success", message: "User created (mock). Check console." });
      reset();
    } catch (err) {
      setToast({
        type: "error",
        message: err?.message || "Something went wrong.",
      });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Layout role="operator">
      <div className="uamPage">
        <div className="uamHeader">
          <h1>User Account Management</h1>
        </div>

        {toast.message ? (
          <div className={`uamToast ${toast.type === "success" ? "success" : "error"}`}>
            {toast.message}
          </div>
        ) : null}

        <form className="uamCard" onSubmit={onSubmit}>
          <div className="uamSectionTitle">User Details</div>

          <div className="uamGrid">
            <div className="uamField">
              <label>Full Name *</label>
              <input
                name="fullName"
                value={form.fullName}
                onChange={onChange}
                onBlur={onBlur}
                placeholder="e.g., Hana Ayad"
              />
              {showError("fullName") ? <span className="uamError">{errors.fullName}</span> : null}
            </div>

            <div className="uamField">
              <label>Email *</label>
              <input
                name="email"
                value={form.email}
                onChange={onChange}
                onBlur={onBlur}
                placeholder="e.g., hana@company.com"
              />
              {showError("email") ? <span className="uamError">{errors.email}</span> : null}
            </div>

            <div className="uamField">
              <label>Phone *</label>
              <input
                name="phone"
                value={form.phone}
                onChange={onChange}
                onBlur={onBlur}
                placeholder="e.g., +971 50 123 4567"
              />
              {showError("phone") ? <span className="uamError">{errors.phone}</span> : null}
            </div>

            <div className="uamField">
              <label>Location *</label>
              <input
                name="location"
                value={form.location}
                onChange={onChange}
                onBlur={onBlur}
                placeholder="e.g., Dubai, UAE"
              />
              {showError("location") ? <span className="uamError">{errors.location}</span> : null}
            </div>
          </div>

          <div className="uamDivider" />

          <div className="uamSectionTitle">Login Credentials</div>

          <div className="uamGrid">
            <div className="uamField">
              <label>Password *</label>
              <input
                type="password"
                name="password"
                value={form.password}
                onChange={onChange}
                onBlur={onBlur}
                placeholder="Minimum 8 characters"
              />
              {showError("password") ? <span className="uamError">{errors.password}</span> : null}
            </div>

            <div className="uamField">
              <label>Confirm Password *</label>
              <input
                type="password"
                name="confirmPassword"
                value={form.confirmPassword}
                onChange={onChange}
                onBlur={onBlur}
                placeholder="Re-enter password"
              />
              {showError("confirmPassword") ? (
                <span className="uamError">{errors.confirmPassword}</span>
              ) : null}
            </div>
          </div>

          <div className="uamDivider" />

          <div className="uamSectionTitle">Access & Organization</div>

          <div className="uamGrid">
            <div className="uamField">
              <label>Role *</label>
              <select name="role" value={form.role} onChange={onChange} onBlur={onBlur}>
                <option value="customer">Customer</option>
                <option value="employee">Employee</option>
                <option value="manager">Manager</option>
                <option value="operator">Operator</option>
              </select>
              {showError("role") ? <span className="uamError">{errors.role}</span> : null}
            </div>

            <div className="uamField">
              <label>Department *</label>
              <input
                name="department"
                value={form.department}
                onChange={onChange}
                onBlur={onBlur}
                placeholder="e.g., Customer Support"
              />
              {showError("department") ? <span className="uamError">{errors.department}</span> : null}
            </div>

            <div className="uamField">
              <label>Status</label>
              <select name="status" value={form.status} onChange={onChange}>
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
              </select>
            </div>
          </div>

          <div className="uamActions">
            <button type="button" className="uamBtn secondary" onClick={reset} disabled={submitting}>
              Clear
            </button>
            <button type="submit" className="uamBtn primary" disabled={submitting}>
              {submitting ? "Creating..." : "Create User"}
            </button>
          </div>

          <div className="uamFootnote">
          </div>
        </form>
      </div>
    </Layout>
  );
}