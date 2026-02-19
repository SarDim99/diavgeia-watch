"use client";

import { useEffect, useState } from "react";
import { fetchTopSpenders, formatCurrency } from "@/lib/api";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { TrendingUp } from "lucide-react";

interface Spender {
  org_name: string;
  total: number;
  decisions: number;
}

const COLORS = [
  "#4f8ff7",
  "#22d3ee",
  "#10b981",
  "#f59e0b",
  "#f43f5e",
  "#8b5cf6",
  "#ec4899",
  "#06b6d4",
];

export default function SpendingChart() {
  const [data, setData] = useState<Spender[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchTopSpenders(8)
      .then((res) => setData(res.data || []))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="rounded-xl border border-navy-600 bg-navy-800 p-5 h-[380px] animate-pulse" />
    );
  }

  const chartData = data.map((d) => ({
    name: d.org_name.length > 25 ? d.org_name.slice(0, 25) + "…" : d.org_name,
    fullName: d.org_name,
    total: d.total,
    decisions: d.decisions,
  }));

  return (
    <div className="rounded-xl border border-navy-600 bg-navy-800 p-5">
      <div className="flex items-center gap-2 mb-4">
        <TrendingUp className="w-4 h-4 text-accent-blue" />
        <h3 className="font-semibold text-sm">Top Organizations by Spending</h3>
      </div>

      <div className="h-[300px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={chartData}
            layout="vertical"
            margin={{ top: 0, right: 20, left: 0, bottom: 0 }}
          >
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="#1e293b"
              horizontal={false}
            />
            <XAxis
              type="number"
              tickFormatter={(val) => `€${(val / 1000).toFixed(0)}k`}
              tick={{ fill: "#64748b", fontSize: 11 }}
              axisLine={{ stroke: "#1e293b" }}
            />
            <YAxis
              type="category"
              dataKey="name"
              width={180}
              tick={{ fill: "#94a3b8", fontSize: 11 }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              content={({ active, payload }) => {
                if (!active || !payload?.[0]) return null;
                const d = payload[0].payload;
                return (
                  <div className="bg-navy-900 border border-navy-600 rounded-lg p-3 shadow-xl">
                    <p className="text-xs text-slate-300 mb-1 max-w-[250px]">
                      {d.fullName}
                    </p>
                    <p className="text-sm font-semibold text-white">
                      {formatCurrency(d.total)}
                    </p>
                    <p className="text-xs text-slate-400 mt-1">
                      {d.decisions} decisions
                    </p>
                  </div>
                );
              }}
            />
            <Bar dataKey="total" radius={[0, 4, 4, 0]} barSize={20}>
              {chartData.map((_, i) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} fillOpacity={0.85} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}