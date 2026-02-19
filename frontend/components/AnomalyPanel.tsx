"use client";

import { useEffect, useState } from "react";
import { fetchAnomalies } from "@/lib/api";
import { AlertTriangle, Scissors, Target, PieChart } from "lucide-react";

interface Anomaly {
  type: string;
  severity: string;
  title: string;
  description: string;
  data: any;
}

const TYPE_CONFIG: Record<string, { icon: any; label: string; color: string; bg: string }> = {
  contract_splitting: { icon: Scissors, label: "Contract Splitting", color: "text-rose-600", bg: "bg-rose-50" },
  threshold_gaming: { icon: Target, label: "Threshold Gaming", color: "text-amber-600", bg: "bg-amber-50" },
  concentration: { icon: PieChart, label: "Concentration Risk", color: "text-orange-600", bg: "bg-orange-50" },
};

export default function AnomalyPanel() {
  const [anomalies, setAnomalies] = useState<Anomaly[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>("all");

  useEffect(() => {
    fetchAnomalies()
      .then((res) => setAnomalies(res.anomalies || []))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <div className="rounded-2xl bg-white border border-slate-200 shadow-sm p-6 h-[380px] animate-pulse" />;
  }

  const filtered = filter === "all" ? anomalies : anomalies.filter((a) => a.type === filter);
  const typeCounts = anomalies.reduce((acc, a) => { acc[a.type] = (acc[a.type] || 0) + 1; return acc; }, {} as Record<string, number>);

  return (
    <div className="rounded-2xl bg-white border border-slate-200 shadow-sm p-6 flex flex-col h-[400px]">
      <div className="flex items-center gap-2 mb-4 shrink-0">
        <AlertTriangle className="w-5 h-5 text-rose-500" />
        <h3 className="font-semibold text-base text-slate-800">Anomaly Detection</h3>
        <span className="ml-auto text-xs font-semibold text-slate-500 bg-slate-100 px-2 py-1 rounded-md">
          {anomalies.length} total
        </span>
      </div>

      <div className="flex gap-2 mb-4 flex-wrap shrink-0">
        <FilterTab label={`All`} active={filter === "all"} onClick={() => setFilter("all")} />
        {Object.entries(TYPE_CONFIG).map(([key, cfg]) => (
          <FilterTab key={key} label={cfg.label} active={filter === key} onClick={() => setFilter(key)} />
        ))}
      </div>

      <div className="space-y-3 overflow-y-auto pr-2 flex-1">
        {filtered.length === 0 ? (
          <p className="text-sm text-slate-400 text-center py-8">No anomalies detected in this category</p>
        ) : (
          filtered.map((anomaly, i) => <AnomalyCard key={i} anomaly={anomaly} />)
        )}
      </div>
    </div>
  );
}

function FilterTab({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`text-xs px-3 py-1.5 rounded-full font-medium transition-all duration-200
        ${active ? "bg-slate-800 text-white shadow-sm" : "bg-slate-50 text-slate-600 border border-slate-200 hover:bg-slate-100"}`}
    >
      {label}
    </button>
  );
}

function AnomalyCard({ anomaly }: { anomaly: Anomaly }) {
  const config = TYPE_CONFIG[anomaly.type] || TYPE_CONFIG.concentration;
  const Icon = config.icon;
  const isHigh = anomaly.severity === "high";
  const severityStyle = isHigh ? "bg-rose-100 text-rose-700" : "bg-amber-100 text-amber-700";

  return (
    <div className="p-4 rounded-xl border border-slate-100 bg-slate-50 hover:bg-white hover:border-slate-200 hover:shadow-sm transition-all duration-200">
      <div className="flex items-start gap-3">
        <div className={`p-2 rounded-lg ${config.bg} shrink-0 mt-0.5`}>
          <Icon className={`w-4 h-4 ${config.color}`} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1.5">
            <span className="text-sm font-semibold text-slate-800 truncate">{anomaly.title}</span>
            <span className={`text-[10px] px-2 py-0.5 rounded-md font-bold uppercase tracking-wide ${severityStyle}`}>
              {anomaly.severity}
            </span>
          </div>
          <p className="text-xs text-slate-500 leading-relaxed">{anomaly.description}</p>
        </div>
      </div>
    </div>
  );
}