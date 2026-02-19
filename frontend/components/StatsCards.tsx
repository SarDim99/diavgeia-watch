"use client";

import { useEffect, useState } from "react";
import { fetchStats, formatCurrency, formatNumber } from "@/lib/api";
import {
  FileText,
  Building2,
  Users,
  Banknote,
} from "lucide-react";

interface Stats {
  total_decisions: number;
  total_expense_items: number;
  unique_organizations: number;
  unique_contractors: number;
  total_amount: number;
}

export default function StatsCards() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchStats()
      .then(setStats)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <div
            key={i}
            className="h-28 rounded-xl bg-navy-800 animate-pulse"
          />
        ))}
      </div>
    );
  }

  if (!stats) return null;

  const cards = [
    {
      label: "Total Spending",
      value: formatCurrency(stats.total_amount),
      icon: Banknote,
      color: "text-accent-green",
      bg: "bg-accent-green/10",
      glow: "glow-green",
    },
    {
      label: "Decisions",
      value: formatNumber(stats.total_decisions),
      icon: FileText,
      color: "text-accent-blue",
      bg: "bg-accent-blue/10",
      glow: "glow-blue",
    },
    {
      label: "Organizations",
      value: formatNumber(stats.unique_organizations),
      icon: Building2,
      color: "text-accent-cyan",
      bg: "bg-accent-cyan/10",
      glow: "",
    },
    {
      label: "Contractors",
      value: formatNumber(stats.unique_contractors),
      icon: Users,
      color: "text-accent-amber",
      bg: "bg-accent-amber/10",
      glow: "",
    },
  ];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 stagger">
      {cards.map((card) => (
        <div
          key={card.label}
          className={`rounded-xl border border-navy-600 bg-navy-800 p-5 transition-all duration-300 hover:border-navy-600/80 hover:bg-navy-700 ${card.glow}`}
        >
          <div className="flex items-center justify-between mb-3">
            <span className="text-sm text-slate-400 font-medium">
              {card.label}
            </span>
            <div className={`p-2 rounded-lg ${card.bg}`}>
              <card.icon className={`w-4 h-4 ${card.color}`} />
            </div>
          </div>
          <p className="text-2xl font-bold tracking-tight">{card.value}</p>
        </div>
      ))}
    </div>
  );
}