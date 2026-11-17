"use client";

import { useEffect, useState } from "react";
import { Cpu, Zap, Radio, AlertTriangle } from "lucide-react";
import { api, DashboardStats } from "@/services/api";

export default function Header() {
  const [stats, setStats] = useState<DashboardStats | null>(null);

  useEffect(() => {
    api.getDashboardStats().then(setStats).catch(() => {});
    const interval = setInterval(() => {
      api.getDashboardStats().then(setStats).catch(() => {});
    }, 10000);
    return () => clearInterval(interval);
  }, []);

  const gpuName = stats?.gpu_info?.device_name || "NVIDIA RTX 3050 6GB";
  const hasCuda = stats?.gpu_info?.cuda_available ?? true;
  const vlm = stats?.integrations?.active_vlm?.toUpperCase() || "LOCAL";

  return (
    <header className="h-16 bg-surface/80 backdrop-blur-md border-b border-border flex items-center justify-between px-8 fixed top-0 right-0 left-64 z-20">
      <div className="flex items-center gap-3">
        <div className="h-2.5 w-2.5 rounded-full bg-emerald-400 animate-pulse" />
        <span className="text-xs font-medium text-text-secondary">
          Factory Core: <span className="text-emerald-400 font-semibold">ONLINE</span>
        </span>
      </div>

      <div className="flex items-center gap-3">
        {/* GPU Hardware Indicator */}
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-md bg-surface-elevated border border-border text-xs">
          <Cpu className={`w-3.5 h-3.5 ${hasCuda ? "text-accent-cyan" : "text-amber-400"}`} />
          <span className="text-text-secondary font-mono text-[11px]">{gpuName}</span>
          <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-accent-cyan/20 text-accent-cyan">
            CUDA 13.2
          </span>
        </div>

        {/* AI Provider Indicator */}
        <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-surface-elevated border border-border text-xs">
          <Zap className="w-3.5 h-3.5 text-amber-400" />
          <span className="text-text-muted text-[11px]">VLM:</span>
          <span className="text-amber-300 font-mono text-[11px] font-semibold">{vlm}</span>
        </div>
      </div>
    </header>
  );
}
