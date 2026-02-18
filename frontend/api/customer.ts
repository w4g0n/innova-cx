import axios from "axios";
import { authHeader } from "../src/utils/auth";

const BASE_URL = "http://localhost:8000/api/customer";

export async function getCustomerDashboard() {
  const response = await axios.get(`${BASE_URL}/dashboard`, {
    headers: authHeader(),
  });
  return response.data;
}

export async function getCustomerHistory() {
  const response = await axios.get(`${BASE_URL}/history`, {
    headers: authHeader(),
  });
  return response.data;
}
