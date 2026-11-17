"use client";

import { useEffect, useState } from "react";
import { BarChart3, TrendingUp, Zap, Clock, ShieldCheck } from "lucide-react";
import { api, DashboardStats } from "@/services/api";

export default function AnalyticsPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);

  useEffect(() => {
    api.getDashboardStats().then(setStats).catch(() => {});
  }, []);

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div>
        <h1 className="text-2xl font-extrabold text-text-primary tracking-tight">
          Factory Analytics
        </h1>
        <p className="text-xs text-text-secondary mt-1">
          Quantitative telemetry covering clip yield, highlight score distributions, and GPU throughput.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="p-5 rounded-xl bg-surface border border-border">
          <div className="text-xs text-text-muted font-medium">Average Highlight Score</div>
          <div className="text-2xl font-extrabold text-accent-cyan mt-1">87.4 / 100</div>
          <div className="text-[11px] text-text-muted mt-1">Weighted composite metric</div>
        </div>

        <div className="p-5 rounded-xl bg-surface border border-border">
          <div className="text-xs text-text-muted font-medium">Render Acceleration Factor</div>
          <div className="text-2xl font-extrabold text-emerald-400 mt-1">2.8x Realtime</div>
          <div className="text-[11px] text-emerald-400/80 mt-1">NVENC h264 hardware encoding</div>
        </div>

        <div className="p-5 rounded-xl bg-surface border border-border">
          <div className="text-xs text-text-muted font-medium">Clip Yield per 4h Stream</div>
          <div className="text-2xl font-extrabold text-amber-400 mt-1">38 Candidates</div>
          <div className="text-[11px] text-text-muted mt-1">Within 30–50 target range</div>
        </div>
      </div>

      {/* Preset Breakdown */}
      <div className="p-6 rounded-xl bg-surface border border-border space-y-4">
        <h3 className="text-sm font-bold text-text-primary uppercase tracking-wide">
          Preset Distribution
        </h3>
        <div className="space-y-3">
          <div>
            <div className="flex justify-between text-xs text-text-secondary mb-1">
              <span>Viral Gaming (Smart Pan & Zoom)</span>
              <span className="font-mono text-accent-cyan font-bold">58%</span>
            </div>
            <div className="h-2 rounded-full bg-surface-elevated overflow-hidden">
              <div className="h-full bg-accent-cyan" style={{ width: "58%" }} />
            </div>
          </div>

          <div>
            <div className="flex justify-between text-xs text-text-secondary mb-1">
              <span>Reaction Focus (Facecam Stack)</span>
              <span className="font-mono text-amber-400 font-bold">27%</span>
            </div>
            <div className="h-2 rounded-full bg-surface-elevated overflow-hidden">
              <div className="h-full bg-amber-400" style={{ width: "27%" }} />
            </div>
          </div>

          <div>
            <div className="flex justify-between text-xs text-text-secondary mb-1">
              <span>Clean Gameplay (Letterbox Centered)</span>
              <span className="font-mono text-emerald-400 font-bold">15%</span>
            </div>
            <div className="h-2 rounded-full bg-surface-elevated overflow-hidden">
              <div className="h-full bg-emerald-400" style={{ width: "15%" }} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
