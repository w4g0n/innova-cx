// src/api/customer.js
import { API_BASE_URL } from "../src/config/apiBase";

export function getStoredToken() {
  try {
    const rawUser = localStorage.getItem("user");
    if (!rawUser) return localStorage.getItem("access_token") || "";
    const user = JSON.parse(rawUser);
    return user?.access_token || "";
  } catch {
    return "";
  }
}

const BASE_URL = API_BASE_URL;

export async function fetchCustomerDashboard() {
  const token = getStoredToken();
  const res = await fetch(`${BASE_URL}/api/customer/dashboard`, {
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });
  if (!res.ok) throw new Error(`Dashboard fetch failed (${res.status})`);
  return res.json();
}

export async function fetchCustomerTickets() {
  const token = getStoredToken();
  const res = await fetch(`${BASE_URL}/api/customer/tickets`, {
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });
  if (!res.ok) throw new Error(`Tickets fetch failed (${res.status})`);
  return res.json();
}

export async function fetchCustomerTicketById(id) {
  const token = getStoredToken();
  const res = await fetch(`${BASE_URL}/api/customer/tickets/${id}`, {
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });
  if (!res.ok) throw new Error(`Ticket fetch failed (${res.status})`);
  return res.json();
}
