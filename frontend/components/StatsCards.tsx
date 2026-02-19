"use client";

import { useEffect, useState } from "react";
import { fetchStats, formatCurrency, formatNumber } from "@/lib/api";
import { FileText, Building2, Users, Banknote } from "lucide-react";

interface Stats {
  total_decisions: number;
  unique_organizations: number;
  unique_contractors: number;
  total_amount: number;
}

export default function StatsCards() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchStats().then(setStats).catch(console.error).finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-6">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="h-28 rounded-2xl bg-white border border-slate-200 shadow-sm animate-pulse" />
        ))}
      </div>
    );
  }

  if (!stats) return null;

  const cards = [
    { label: "Total Spending", value: formatCurrency(stats.total_amount), icon: Banknote, color: "text-emerald-600", bg: "bg-emerald-50" },
    { label: "Decisions Processed", value: formatNumber(stats.total_decisions), icon: FileText, color: "text-blue-600", bg: "bg-blue-50" },
    { label: "Public Organizations", value: formatNumber(stats.unique_organizations), icon: Building2, color: "text-cyan-600", bg: "bg-cyan-50" },
    { label: "Contractors", value: formatNumber(stats.unique_contractors), icon: Users, color: "text-amber-600", bg: "bg-amber-50" },
  ];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-6 stagger">
      {cards.map((card) => (
        <div key={card.label} className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <span className="text-sm font-semibold text-slate-500">{card.label}</span>
            <div className={`p-2 rounded-xl ${card.bg}`}>
              <card.icon className={`w-5 h-5 ${card.color}`} />
            </div>
          </div>
          <p className="text-2xl lg:text-3xl font-bold tracking-tight text-slate-900">{card.value}</p>
        </div>
      ))}
    </div>
  );
}