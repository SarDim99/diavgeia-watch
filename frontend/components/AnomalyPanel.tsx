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

const TYPE_CONFIG: Record<string, { icon: any; label: string; color: string }> = {
  contract_splitting: {
    icon: Scissors,
    label: "Contract Splitting",
    color: "text-accent-red",
  },
  threshold_gaming: {
    icon: Target,
    label: "Threshold Gaming",
    color: "text-accent-amber",
  },
  concentration: {
    icon: PieChart,
    label: "Concentration Risk",
    color: "text-orange-400",
  },
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
    return (
      <div className="rounded-xl border border-navy-600 bg-navy-800 p-5 h-[380px] animate-pulse" />
    );
  }

  const filtered =
    filter === "all"
      ? anomalies
      : anomalies.filter((a) => a.type === filter);

  const typeCounts = anomalies.reduce(
    (acc, a) => {
      acc[a.type] = (acc[a.type] || 0) + 1;
      return acc;
    },
    {} as Record<string, number>
  );

  return (
    <div className="rounded-xl border border-navy-600 bg-navy-800 p-5">
      <div className="flex items-center gap-2 mb-4">
        <AlertTriangle className="w-4 h-4 text-accent-red" />
        <h3 className="font-semibold text-sm">Anomaly Detection</h3>
        <span className="ml-auto text-xs font-mono text-slate-500">
          {anomalies.length} found
        </span>
      </div>

      {/* Filter tabs */}
      <div className="flex gap-1.5 mb-4 flex-wrap">
        <FilterTab
          label={`All (${anomalies.length})`}
          active={filter === "all"}
          onClick={() => setFilter("all")}
        />
        {Object.entries(TYPE_CONFIG).map(([key, cfg]) => (
          <FilterTab
            key={key}
            label={`${cfg.label} (${typeCounts[key] || 0})`}
            active={filter === key}
            onClick={() => setFilter(key)}
          />
        ))}
      </div>

      {/* Anomaly list */}
      <div className="space-y-2.5 max-h-[280px] overflow-y-auto pr-1">
        {filtered.length === 0 ? (
          <p className="text-sm text-slate-500 text-center py-8">
            No anomalies detected in this category
          </p>
        ) : (
          filtered.map((anomaly, i) => (
            <AnomalyCard key={i} anomaly={anomaly} />
          ))
        )}
      </div>
    </div>
  );
}

function FilterTab({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`text-xs px-2.5 py-1 rounded-md transition-all duration-200
        ${
          active
            ? "bg-accent-blue/15 text-accent-blue border border-accent-blue/30"
            : "text-slate-400 border border-navy-600 hover:text-white hover:border-navy-600/80"
        }`}
    >
      {label}
    </button>
  );
}

function AnomalyCard({ anomaly }: { anomaly: Anomaly }) {
  const config = TYPE_CONFIG[anomaly.type] || TYPE_CONFIG.concentration;
  const Icon = config.icon;
  const severityColor =
    anomaly.severity === "high"
      ? "bg-accent-red/10 border-accent-red/30 text-accent-red"
      : "bg-accent-amber/10 border-accent-amber/30 text-accent-amber";

  return (
    <div className="p-3 rounded-lg border border-navy-600 hover:border-navy-600/80 hover:bg-navy-700/30 transition-all duration-200">
      <div className="flex items-start gap-2.5">
        <div className={`p-1.5 rounded-md ${config.color === "text-accent-red" ? "bg-accent-red/10" : config.color === "text-accent-amber" ? "bg-accent-amber/10" : "bg-orange-400/10"} mt-0.5`}>
          <Icon className={`w-3.5 h-3.5 ${config.color}`} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-medium truncate">
              {anomaly.title}
            </span>
            <span
              className={`text-[10px] px-1.5 py-0.5 rounded border font-medium ${severityColor}`}
            >
              {anomaly.severity}
            </span>
          </div>
          <p className="text-xs text-slate-400 leading-relaxed">
            {anomaly.description}
          </p>
        </div>
      </div>
    </div>
  );
}