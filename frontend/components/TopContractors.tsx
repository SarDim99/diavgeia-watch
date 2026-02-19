"use client";

import { useEffect, useState } from "react";
import { fetchTopContractors, formatCurrency } from "@/lib/api";
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
    fetchTopContractors(8)
      .then((res) => setData(res.data || []))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <div className="rounded-2xl bg-white border border-slate-200 shadow-sm p-6 h-[380px] animate-pulse" />;
  }

  const maxAmount = data.length > 0 ? data[0].total : 1;

  return (
    <div className="rounded-2xl bg-white border border-slate-200 shadow-sm p-6">
      <div className="flex items-center gap-2 mb-6">
        <Users className="w-5 h-5 text-amber-600" />
        <h3 className="font-semibold text-base text-slate-800">Top Contractors</h3>
      </div>

      <div className="space-y-3 max-h-[300px] overflow-y-auto pr-2">
        {data.map((c, i) => (
          <div key={i} className="group relative p-3 rounded-xl border border-slate-100 bg-slate-50/50 hover:bg-slate-50 transition-colors">
            {/* Background progress bar */}
            <div
              className="absolute inset-y-0 left-0 bg-blue-50 rounded-xl transition-all"
              style={{ width: `${(c.total / maxAmount) * 100}%` }}
            />

            <div className="relative flex items-center justify-between gap-3">
              <div className="flex items-center gap-3 min-w-0">
                <span className="text-xs font-bold text-slate-400 w-5 text-right shrink-0">
                  {i + 1}
                </span>
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-slate-800 truncate">
                    {c.contractor_name || "Unknown"}
                  </p>
                  <p className="text-xs text-slate-500 mt-0.5">
                    {c.contracts} contracts {c.contractor_afm && `· AFM ${c.contractor_afm}`}
                  </p>
                </div>
              </div>
              <span className="text-sm font-bold text-slate-900 whitespace-nowrap">
                {formatCurrency(c.total)}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}