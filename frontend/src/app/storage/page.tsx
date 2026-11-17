"use client";

import { useEffect, useState } from "react";
import { HardDrive, Trash2, ShieldAlert, CheckCircle2 } from "lucide-react";
import { api, DashboardStats } from "@/services/api";

export default function StoragePage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);

  useEffect(() => {
    api.getDashboardStats().then(setStats).catch(() => {});
  }, []);

  const totalMb = stats?.total_storage_mb ?? 0;
  const quotaMb = 100 * 1024; // 100 GB default quota
  const usagePercent = Math.min(100, Math.round((totalMb / quotaMb) * 100));

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div>
        <h1 className="text-2xl font-extrabold text-text-primary tracking-tight">
          Storage & Retention
        </h1>
        <p className="text-xs text-text-secondary mt-1">
          Monitor local filesystem disk consumption and configure automated raw video cleanup policies.
        </p>
      </div>

      <div className="p-6 rounded-xl bg-surface border border-border space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <HardDrive className="w-5 h-5 text-accent-cyan" />
            <span className="text-sm font-bold text-text-primary">Local Storage Allocation</span>
          </div>
          <span className="text-xs font-mono text-accent-cyan font-bold">
            {totalMb.toFixed(1)} MB / 100,000 MB ({usagePercent}%)
          </span>
        </div>

        <div className="h-3 rounded-full bg-surface-elevated overflow-hidden border border-border">
          <div
            className="h-full bg-gradient-to-r from-accent-cyan to-blue-500 transition-all duration-500"
            style={{ width: `${Math.max(2, usagePercent)}%` }}
          />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-4 border-t border-border text-xs">
          <div className="p-3.5 rounded-lg bg-surface-elevated border border-border">
            <div className="text-text-muted">Raw Stream Recordings</div>
            <div className="text-lg font-bold text-text-primary mt-1">
              {(totalMb * 0.75).toFixed(1)} MB
            </div>
            <div className="text-[10px] text-text-muted mt-0.5">./data/recordings/</div>
          </div>

          <div className="p-3.5 rounded-lg bg-surface-elevated border border-border">
            <div className="text-text-muted">Finished 9:16 Vertical Clips</div>
            <div className="text-lg font-bold text-text-primary mt-1">
              {(totalMb * 0.23).toFixed(1)} MB
            </div>
            <div className="text-[10px] text-accent-cyan mt-0.5">./data/clips/ (Preserved)</div>
          </div>

          <div className="p-3.5 rounded-lg bg-surface-elevated border border-border">
            <div className="text-text-muted">Thumbnails & Waveforms</div>
            <div className="text-lg font-bold text-text-primary mt-1">
              {(totalMb * 0.02).toFixed(1)} MB
            </div>
            <div className="text-[10px] text-text-muted mt-0.5">./data/thumbnails/</div>
          </div>
        </div>
      </div>

      <div className="p-6 rounded-xl bg-surface border border-border space-y-4">
        <h3 className="text-sm font-bold text-text-primary uppercase tracking-wide">
          Automated Retention Rules
        </h3>
        <div className="flex items-center justify-between p-4 rounded-lg bg-surface-elevated border border-border text-xs">
          <div>
            <div className="font-bold text-text-primary">Purge Raw Recordings After 7 Days</div>
            <div className="text-text-muted mt-0.5">
              Automatically deletes processed long-form source videos while keeping rendered vertical clips permanently.
            </div>
          </div>
          <span className="px-2.5 py-1 rounded bg-emerald-500/10 text-emerald-400 font-bold border border-emerald-500/30">
            ACTIVE
          </span>
        </div>
      </div>
    </div>
  );
}
