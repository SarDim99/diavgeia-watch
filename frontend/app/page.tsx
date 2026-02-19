"use client";

import StatsCards from "@/components/StatsCards";
import ChatPanel from "@/components/ChatPanel";
import SpendingChart from "@/components/SpendingChart";
import AnomalyPanel from "@/components/AnomalyPanel";
import TopContractors from "@/components/TopContractors";
import { Search } from "lucide-react";

export default function Home() {
  return (
    <div className="min-h-screen bg-slate-50 flex flex-col font-sans text-slate-900">
      {/* Clean Header */}
      <header className="sticky top-0 z-50 bg-white border-b border-slate-200 shadow-sm">
        <div className="max-w-[1400px] mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-blue-50 text-blue-600">
              <Search className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-xl font-semibold tracking-tight text-slate-900">
                Diavgeia<span className="text-blue-600">Watch</span>
              </h1>
              <p className="text-xs text-slate-500 font-medium">
                Public Spending Explorer
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-50 border border-emerald-100">
            <span className="pulse-dot w-2 h-2 rounded-full bg-emerald-500" />
            <span className="text-xs font-medium text-emerald-700">Live Data</span>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-[1400px] w-full mx-auto px-6 py-8 space-y-8">
        <StatsCards />

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 h-full">
          {/* Left Column: Natural Search Interface */}
          <div className="lg:col-span-5 flex flex-col h-[700px] lg:h-auto min-h-[600px]">
            <ChatPanel />
          </div>

          {/* Right Column: Visualizations */}
          <div className="lg:col-span-7 flex flex-col space-y-8">
            <SpendingChart />
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              <TopContractors />
              <AnomalyPanel />
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="mt-auto border-t border-slate-200 bg-white py-6 text-center text-sm text-slate-500">
        <p>
          Data sourced from{" "}
          <a href="https://diavgeia.gov.gr" target="_blank" rel="noopener" className="text-blue-600 hover:underline font-medium">
            Δι@ύγεια
          </a>{" "}
          · Open Government Data
        </p>
      </footer>
    </div>
  );
}