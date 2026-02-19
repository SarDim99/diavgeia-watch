"use client";

import { useEffect, useState } from "react";
import { fetchTopContractors, formatCurrency, formatNumber } from "@/lib/api";
import { Users } from "lucide-react";

interface Contractor {
  contractor_name: string;
  contractor_afm: string;
  total: number;
  contracts: number;
}

export default function TopContractors() {
  const [data, setData] = useState<Contractor[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchTopContractors(10)
      .then((res) => setData(res.data || []))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="rounded-xl border border-navy-600 bg-navy-800 p-5 h-[380px] animate-pulse" />
    );
  }

  const maxAmount = data.length > 0 ? data[0].total : 1;

  return (
    <div className="rounded-xl border border-navy-600 bg-navy-800 p-5">
      <div className="flex items-center gap-2 mb-4">
        <Users className="w-4 h-4 text-accent-amber" />
        <h3 className="font-semibold text-sm">Top Contractors</h3>
      </div>

      <div className="space-y-2 max-h-[300px] overflow-y-auto pr-1">
        {data.map((c, i) => (
          <div
            key={i}
            className="group relative p-3 rounded-lg border border-navy-600 
                       hover:border-navy-600/80 hover:bg-navy-700/30 transition-all duration-200"
          >
            {/* Background bar */}
            <div
              className="absolute inset-y-0 left-0 bg-accent-blue/5 rounded-lg transition-all"
              style={{ width: `${(c.total / maxAmount) * 100}%` }}
            />

            <div className="relative flex items-center justify-between gap-3">
              <div className="flex items-center gap-3 min-w-0">
                <span className="text-xs font-mono text-slate-500 w-5 text-right flex-shrink-0">
                  {i + 1}
                </span>
                <div className="min-w-0">
                  <p className="text-sm font-medium truncate">
                    {c.contractor_name || "Unknown"}
                  </p>
                  <p className="text-xs text-slate-500 font-mono">
                    {c.contracts} {c.contracts === 1 ? "contract" : "contracts"}
                    {c.contractor_afm ? ` · AFM ${c.contractor_afm}` : ""}
                  </p>
                </div>
              </div>
              <span className="text-sm font-semibold font-mono text-accent-green whitespace-nowrap">
                {formatCurrency(c.total)}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}