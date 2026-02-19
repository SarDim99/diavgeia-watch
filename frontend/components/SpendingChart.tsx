"use client";

import { useEffect, useState } from "react";
import { fetchTopSpenders, formatCurrency } from "@/lib/api";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { TrendingUp } from "lucide-react";

interface Spender {
  org_name: string;
  total: number;
  decisions: number;
}

const COLORS = ["#2563eb", "#0ea5e9", "#059669", "#d97706", "#e11d48", "#7c3aed"];

export default function SpendingChart() {
  const [data, setData] = useState<Spender[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchTopSpenders(6)
      .then((res) => setData(res.data || []))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <div className="rounded-2xl bg-white border border-slate-200 shadow-sm p-6 h-[380px] animate-pulse" />;
  }

  const chartData = data.map((d) => ({
    name: d.org_name.length > 25 ? d.org_name.slice(0, 25) + "…" : d.org_name,
    fullName: d.org_name,
    total: d.total,
    decisions: d.decisions,
  }));

  return (
    <div className="rounded-2xl bg-white border border-slate-200 shadow-sm p-6">
      <div className="flex items-center gap-2 mb-6">
        <TrendingUp className="w-5 h-5 text-blue-600" />
        <h3 className="font-semibold text-base text-slate-800">Top Organizations by Spending</h3>
      </div>

      <div className="h-[300px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData} layout="vertical" margin={{ top: 0, right: 20, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" horizontal={false} />
            <XAxis
              type="number"
              tickFormatter={(val) => `€${(val / 1000).toFixed(0)}k`}
              tick={{ fill: "#64748b", fontSize: 12 }}
              axisLine={{ stroke: "#cbd5e1" }}
            />
            <YAxis
              type="category"
              dataKey="name"
              width={180}
              tick={{ fill: "#475569", fontSize: 12 }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              cursor={{ fill: '#f1f5f9' }}
              content={({ active, payload }) => {
                if (!active || !payload?.[0]) return null;
                const d = payload[0].payload;
                return (
                  <div className="bg-white border border-slate-200 rounded-xl p-3 shadow-lg">
                    <p className="text-xs text-slate-500 mb-1 max-w-[250px] font-medium">{d.fullName}</p>
                    <p className="text-sm font-bold text-slate-900">{formatCurrency(d.total)}</p>
                    <p className="text-xs text-slate-400 mt-1">{d.decisions} decisions</p>
                  </div>
                );
              }}
            />
            <Bar dataKey="total" radius={[0, 4, 4, 0]} barSize={24}>
              {chartData.map((_, i) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}