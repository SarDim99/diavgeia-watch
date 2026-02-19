"use client";

import StatsCards from "@/components/StatsCards";
import ChatPanel from "@/components/ChatPanel";
import SpendingChart from "@/components/SpendingChart";
import AnomalyPanel from "@/components/AnomalyPanel";
import TopContractors from "@/components/TopContractors";
import { Eye } from "lucide-react";

export default function Home() {
  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="border-b border-navy-600 bg-navy-800/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-[1400px] mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-accent-blue/10">
              <Eye className="w-5 h-5 text-accent-blue" />
            </div>
            <div>
              <h1 className="text-lg font-bold tracking-tight">
                Diavgeia
                <span className="text-accent-blue"> Watch</span>
              </h1>
              <p className="text-xs text-slate-500">
                Public Spending Intelligence · Ελληνική Δημόσια Δαπάνη
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="pulse-dot w-2 h-2 rounded-full bg-accent-green" />
            <span className="text-xs text-slate-400">Live</span>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-[1400px] mx-auto px-6 py-6 space-y-6">
        {/* Stats Overview */}
        <StatsCards />

        {/* Two-column layout: Chat + Charts */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left: Chat Panel */}
          <div className="lg:col-span-5">
            <ChatPanel />
          </div>

          {/* Right: Charts */}
          <div className="lg:col-span-7 space-y-6">
            <SpendingChart />
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
              <TopContractors />
              <AnomalyPanel />
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-navy-600 mt-12">
        <div className="max-w-[1400px] mx-auto px-6 py-4 flex items-center justify-between text-xs text-slate-500">
          <span>
            Data source:{" "}
            <a
              href="https://diavgeia.gov.gr"
              target="_blank"
              rel="noopener"
              className="text-accent-blue hover:underline"
            >
              Δι@ύγεια
            </a>{" "}
            — Open Government Data
          </span>
          <span>Built with Next.js · FastAPI · PostgreSQL</span>
        </div>
      </footer>
    </div>
  );
}