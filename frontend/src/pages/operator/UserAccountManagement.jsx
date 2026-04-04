import { useState, useEffect } from "react";
import Layout from "../../components/Layout";
import PageHeader from "../../components/common/PageHeader";
import PillSelect from "../../components/common/PillSelect";
import ConfirmDialog from "../../components/common/ConfirmDialog";
import PhoneInput from "react-phone-input-2";
import "react-phone-input-2/lib/style.css";
import { parsePhoneNumberFromString } from "libphonenumber-js";
import { apiUrl } from "../../config/apiBase";
import { sanitizeText } from "./Operatorsanitize";
import { getCsrfToken } from "../../services/api";
import "./UserAccountManagement.css";

// ── API helpers (same pattern as QualityControl) ───────────────────────────────
function getStoredToken() {
  const direct =
    localStorage.getItem("access_token") ||
    localStorage.getItem("token") ||
    localStorage.getItem("jwt") ||
    localStorage.getItem("authToken");
  if (direct) return direct;
  try {
    const u = JSON.parse(localStorage.getItem("user") || "{}");
    return u?.access_token || "";
  } catch {
    return "";
  }
}

async function apiFetch(path, options = {}) {
  const token = getStoredToken();
  const csrf = await getCsrfToken();
  const url = apiUrl(`/api${path}`);
  const res = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(csrf ? { "X-CSRF-Token": csrf } : {}),
      ...(options.headers ?? {}),
    },
  });
  if (res.status === 401 || res.status === 403) {
    window.location.href = "/login";
    throw new Error("Session expired.");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw Object.assign(new Error(data?.detail ?? `HTTP ${res.status}`), { status: res.status, data });
  }
  return data;
}

// ── Config ────────────────────────────────────────────────────────────────────
const ROLE_OPTIONS = [
  { value: "customer", label: "Customer" },
  { value: "employee", label: "Employee" },
  { value: "manager", label: "Manager" },
  { value: "operator", label: "Operator" },
];

const DEPARTMENT_OPTIONS = [
  "Facilities Management",
  "Legal and Compliance",
  "Safety & Security",
  "HR",
  "Leasing",
  "Maintenance",
  "IT",
];

// ── Helpers ───────────────────────────────────────────────────────────────────
function isValidEmail(email) {
  return /^\S+@\S+\.\S+$/.test(email);
}

function toPhoneInputValue(e164) {
  if (!e164) return "";
  return e164.startsWith("+") ? e164.slice(1) : e164;
}

function validateE164Phone(e164) {
  if (!e164) return "Phone is required.";
  const p = parsePhoneNumberFromString(e164);
  if (!p || !p.isValid()) return "Invalid phone number.";
  return "";
}

export default function UserAccountManagement() {
  const [form, setForm] = useState({
    fullName: "",
    email: "",
    phoneE164: "",
    phoneCountry: "ae",
    location: "",
    role: "customer",
    department: "",
    password: "",
    confirmPassword: "",
  });

  const [errors, setErrors] = useState({});
  const [toast, setToast] = useState({ type: "", message: "" });
  const [showPwd, setShowPwd] = useState(false);
  const [showConfirmPwd, setShowConfirmPwd] = useState(false);

  // Auto-dismiss toast
  useEffect(() => {
    if (!toast.message) return;
    const t = setTimeout(() => setToast({ type: "", message: "" }), 4000);
    return () => clearTimeout(t);
  }, [toast]);

  const [confirm, setConfirm] = useState({
    open: false,
    icon: null,
    title: "",
    message: "",
    variant: "danger",
    onConfirm: null,
  });
  const closeConfirm = () => setConfirm((c) => ({ ...c, open: false }));

  const onChange = (e) => {
    const { name, value } = e.target;
    if (name === "role" && value === "customer") {
      setForm((p) => ({ ...p, role: value, department: "" }));
      setErrors((prev) => { const { department: _d, ...rest } = prev; return rest; });
      return;
    }
    setForm((p) => ({ ...p, [name]: value }));
  };

  const validate = () => {
    const e = {};
    if (!form.fullName.trim()) e.fullName = "Full name is required.";
    if (!form.email.trim()) e.email = "Email is required.";
    if (form.email && !isValidEmail(form.email)) e.email = "Invalid email format.";
    const phoneErr = validateE164Phone(form.phoneE164);
    if (phoneErr) e.phone = phoneErr;
    if (!form.location.trim()) e.location = "Location is required.";
    if (form.role !== "customer" && !form.department.trim()) e.department = "Department is required for non-customer roles.";
    if (!form.password) e.password = "Password is required.";
    if (form.password && form.password.length < 8) e.password = "Min 8 characters.";
    if (form.confirmPassword !== form.password) e.confirmPassword = "Passwords do not match.";
    return e;
  };

  const createUser = async () => {
    setToast({ type: "", message: "" });
    const e = validate();
    setErrors(e);
    if (Object.keys(e).length) {
      setToast({ type: "error", message: "Fix the highlighted fields." });
      return;
    }

    const payload = {
      fullName: sanitizeText(form.fullName, 100),
      email: sanitizeText(form.email, 254),
      phone: form.phoneE164,
      location: sanitizeText(form.location, 200),
      password: form.password,
      role: form.role,
      ...(form.role !== "customer" ? { department: sanitizeText(form.department, 100) } : {}),
    };

    try {
      const data = await apiFetch("/operator/user-creation", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setToast({ type: "success", message: sanitizeText(data?.message ?? "User created successfully.", 200) });
      setForm({
        fullName: "",
        email: "",
        phoneE164: "",
        phoneCountry: "ae",
        location: "",
        role: "customer",
        department: "",
        password: "",
        confirmPassword: "",
      });
    } catch {
      setToast({ type: "error", message: "Failed to create user. Please try again." });
    }
  };

  return (
    <Layout role="operator">
      <div className="uamPage">
        <PageHeader
          title="Create User"
          subtitle="Create a new user account. Customers do not require a department."
        />

        {toast.message && (
          <div className={`uamToast ${toast.type === "success" ? "success" : "error"}`}>
            {toast.message}
          </div>
        )}

        <div className="uamCard">
          <div className="uamGrid">
            <div className="uamField">
              <label>Full Name *</label>
              <input name="fullName" value={form.fullName} onChange={onChange} placeholder="e.g. Hana Ayad" />
              {errors.fullName && <span className="umErr">{errors.fullName}</span>}
            </div>

            <div className="uamField">
              <label>Email *</label>
              <input name="email" value={form.email} onChange={onChange} placeholder="e.g. hana@company.com" />
              {errors.email && <span className="umErr">{errors.email}</span>}
            </div>

            <div className="uamField">
              <label>Phone *</label>
              <div className="uamPhoneWrap">
                <PhoneInput
                  country={form.phoneCountry}
                  value={toPhoneInputValue(form.phoneE164)}
                  onChange={(digits, countryData) => {
                    let cleanDigits = digits || "";
                    const dialCode = countryData?.dialCode || "";
                    if (cleanDigits.startsWith(dialCode + "0")) {
                      cleanDigits = dialCode + cleanDigits.slice(dialCode.length + 1);
                    }
                    const e164 = cleanDigits ? `+${cleanDigits}` : "";
                    setForm((p) => ({
                      ...p,
                      phoneE164: e164,
                      phoneCountry: (countryData?.countryCode || "ae").toLowerCase(),
                    }));
                    setErrors((prev) => { const { phone: _p, ...rest } = prev; return rest; });
                  }}
                  enableSearch
                  autoFormat={false}
                  countryCodeEditable={false}
                  inputProps={{ name: "phone", required: true }}
                />
              </div>
              {errors.phone && <span className="umErr">{errors.phone}</span>}
            </div>

            <div className="uamField">
              <label>Location *</label>
              <input name="location" value={form.location} onChange={onChange} placeholder="e.g. Dubai, UAE" />
              {errors.location && <span className="umErr">{errors.location}</span>}
            </div>

            <div className="uamField">
              <label>Role *</label>
              <PillSelect
                value={form.role}
                onChange={(v) => onChange({ target: { name: "role", value: v } })}
                ariaLabel="Role"
                options={ROLE_OPTIONS}
              />
            </div>

            {form.role !== "customer" && (
              <div className="uamField">
                <label>Department *</label>
                <select name="department" value={form.department} onChange={onChange}>
                  <option value="">Select department…</option>
                  {DEPARTMENT_OPTIONS.map((d) => (
                    <option key={d} value={d}>{d}</option>
                  ))}
                </select>
                {errors.department && <span className="umErr">{errors.department}</span>}
              </div>
            )}

            <div className="uamField">
              <label>Password *</label>
              <div className="uamPwdWrap">
                <input
                  type={showPwd ? "text" : "password"}
                  name="password"
                  value={form.password}
                  onChange={onChange}
                  placeholder="Minimum 8 characters"
                />
                <button type="button" className="uamEyeBtn" onClick={() => setShowPwd(v => !v)} tabIndex={-1}>
                  {showPwd
                    ? <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/><path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
                    : <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                  }
                </button>
              </div>
              {errors.password && <span className="umErr">{errors.password}</span>}
            </div>

            <div className="uamField">
              <label>Confirm Password *</label>
              <div className="uamPwdWrap">
                <input
                  type={showConfirmPwd ? "text" : "password"}
                  name="confirmPassword"
                  value={form.confirmPassword}
                  onChange={onChange}
                  placeholder="Re-enter password"
                />
                <button type="button" className="uamEyeBtn" onClick={() => setShowConfirmPwd(v => !v)} tabIndex={-1}>
                  {showConfirmPwd
                    ? <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/><path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/><line x1="1" y1="1" x2="23" y2="23"/></svg>
                    : <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                  }
                </button>
              </div>
              {errors.confirmPassword && <span className="umErr">{errors.confirmPassword}</span>}
            </div>
          </div>

          <div className="uamActions">
            <button className="filterPillBtn" type="button" onClick={createUser}>
              Create User
            </button>
          </div>
        </div>

        <ConfirmDialog
          open={confirm.open}
          icon={confirm.icon}
          title={confirm.title}
          message={confirm.message}
          variant={confirm.variant}
          confirmLabel="Confirm"
          onConfirm={confirm.onConfirm}
          onCancel={closeConfirm}
        />
      </div>
    </Layout>
  );
}