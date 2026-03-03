import { useEffect, useMemo, useState } from "react";
import Layout from "../../components/Layout";
import PageHeader from "../../components/common/PageHeader";
import PillSelect from "../../components/common/PillSelect";
import ConfirmDialog from "../../components/common/ConfirmDialog";
import PhoneInput from "react-phone-input-2";
import "react-phone-input-2/lib/style.css";
import { parsePhoneNumberFromString } from "libphonenumber-js";
import "./UserAccountManagement.css";

// ── Config ────────────────────────────────────────────────────────────────────
const API_BASE = 'http://127.0.0.1:8000/api';

// ── Helpers ────────────────────────────────────────────────────────────────────
function authHeaders() {
  const token = localStorage.getItem("access_token");
  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

const ROLE_OPTIONS = [
  { value: "customer", label: "Customer" },
  { value: "employee", label: "Employee" },
  { value: "manager", label: "Manager" },
  { value: "operator", label: "Operator" },
];

function isValidEmail(email) {
  return /^\S+@\S+\.\S+$/.test(email);
}

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
      setErrors((prev) => {
        const { department, ...rest } = prev;
        return rest;
      });
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

    if (form.role !== "customer" && !form.department.trim()) {
      e.department = "Department is required for non-customer roles.";
    }

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
      fullName: form.fullName.trim(),
      email: form.email.trim(),
      phone: form.phoneE164,
      location: form.location.trim(),
      password: form.password,
      role: form.role,
      ...(form.role !== "customer" ? { department: form.department.trim() } : {}),
    };

    try {
      const res = await fetch(`${API_BASE}/operator/user-creation`, {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify(payload),
      });

      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        setToast({
          type: "error",
          message: data?.detail ?? `Failed to create user (HTTP ${res.status}).`,
        });
        return;
      }

      setToast({ type: "success", message: data?.message ?? "User created successfully." });
      setForm((p) => ({
        ...p,
        fullName: "",
        email: "",
        phoneE164: "",
        phoneCountry: "ae",
        location: "",
        role: "customer",
        department: "",
        password: "",
        confirmPassword: "",
      }));
    } catch (err) {
      setToast({ type: "error", message: "Failed to create user. Check the backend and network." });
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
          <div className={`umToast ${toast.type === "success" ? "success" : "error"}`}>
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
                setCreate((p) => ({
                  ...p,
                  phoneE164: e164,
                  phoneCountry: (countryData?.countryCode || "ae").toLowerCase(),
                }));
                setErrors((prev) => {
                  const { phone, ...rest } = prev;
                  return rest;
                });
              }}
                enableSearch
                autoFormat={false}
                countryCodeEditable={false}
                inputProps={{ name: "phone", required: true }}
              />
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

            {/* Department only for non-customer */}
            {form.role !== "customer" && (
              <div className="uamField">
                <label>Department *</label>
                <input name="department" value={form.department} onChange={onChange} placeholder="e.g. Customer Support" />
                {errors.department && <span className="umErr">{errors.department}</span>}
              </div>
            )}

            <div className="uamField">
              <label>Password *</label>
              <input type="password" name="password" value={form.password} onChange={onChange} placeholder="Minimum 8 characters" />
              {errors.password && <span className="umErr">{errors.password}</span>}
            </div>

            <div className="uamField">
              <label>Confirm Password *</label>
              <input
                type="password"
                name="confirmPassword"
                value={form.confirmPassword}
                onChange={onChange}
                placeholder="Re-enter password"
              />
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
