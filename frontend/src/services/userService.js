// Later: replace with real API call using fetch/axios.
// Keep this in services so you can swap it easily.

export async function createUser(payload) {
  // Example future endpoint:
  // return fetch("/api/users", { method: "POST", headers: {...}, body: JSON.stringify(payload) })

  // Mock delay
  await new Promise((r) => setTimeout(r, 600));

  // Simple mock failure example:
  if (payload.email?.toLowerCase() === "taken@company.com") {
    const err = new Error("This email is already in use.");
    err.code = "EMAIL_TAKEN";
    throw err;
  }

  // Return mock created user
  return {
    id: crypto?.randomUUID?.() || String(Date.now()),
    ...payload,
    password: undefined, // never return password in real backend
  };
}