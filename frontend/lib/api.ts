const API_BASE = "/api";

export async function fetchStats() {
  const res = await fetch(`${API_BASE}/stats`);
  if (!res.ok) throw new Error("Failed to fetch stats");
  return res.json();
}

export async function askQuestion(question: string) {
  const res = await fetch(`${API_BASE}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  if (!res.ok) throw new Error("Failed to ask question");
  return res.json();
}

export async function fetchTopSpenders(limit = 10) {
  const res = await fetch(`${API_BASE}/top-spenders?limit=${limit}`);
  if (!res.ok) throw new Error("Failed to fetch top spenders");
  return res.json();
}

export async function fetchTopContractors(limit = 10) {
  const res = await fetch(`${API_BASE}/top-contractors?limit=${limit}`);
  if (!res.ok) throw new Error("Failed to fetch top contractors");
  return res.json();
}

export async function fetchSpendingByDate() {
  const res = await fetch(`${API_BASE}/spending-by-date`);
  if (!res.ok) throw new Error("Failed to fetch spending data");
  return res.json();
}

export async function fetchAnomalies() {
  const res = await fetch(`${API_BASE}/anomalies`);
  if (!res.ok) throw new Error("Failed to fetch anomalies");
  return res.json();
}

export async function fetchRecentDecisions(limit = 20) {
  const res = await fetch(`${API_BASE}/recent-decisions?limit=${limit}`);
  if (!res.ok) throw new Error("Failed to fetch recent decisions");
  return res.json();
}

export function formatCurrency(amount: number): string {
  return new Intl.NumberFormat("el-GR", {
    style: "currency",
    currency: "EUR",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
}

export function formatNumber(num: number): string {
  return new Intl.NumberFormat("el-GR").format(num);
}