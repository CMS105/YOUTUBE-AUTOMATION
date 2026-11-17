"use client";

import { useEffect, useState } from "react";
import { Radio, Video, Play, AlertCircle, RefreshCw, Plus } from "lucide-react";
import { api, Streamer } from "@/services/api";

export default function StreamMonitorPage() {
  const [streamers, setStreamers] = useState<Streamer[]>([]);
  const [loading, setLoading] = useState(true);

  const loadData = () => {
    setLoading(true);
    api.getStreamers().then((res) => {
      setStreamers(res.items);
      setLoading(false);
    }).catch(() => setLoading(false));
  };

  useEffect(() => {
    loadData();
  }, []);

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-extrabold text-text-primary tracking-tight">
            Stream Monitor
          </h1>
          <p className="text-xs text-text-secondary mt-1">
            Real-time broadcast detection and authorized media intake for registered GTA 6 creators.
          </p>
        </div>
        <button
          onClick={loadData}
          className="px-3.5 py-2 rounded-lg bg-surface border border-border hover:bg-surface-elevated text-xs font-semibold text-text-primary flex items-center gap-2"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          <span>Poll Now</span>
        </button>
      </div>

      {/* Streamers Live Radar Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {streamers.map((s) => (
          <div
            key={s.id}
            className="p-5 rounded-xl bg-surface border border-border flex flex-col justify-between"
          >
            <div>
              <div className="flex items-center justify-between">
                <span className="text-sm font-bold text-text-primary">{s.display_name}</span>
                <span
                  className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                    s.permission_status === "ACTIVE"
                      ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30"
                      : "bg-amber-500/10 text-amber-400 border border-amber-500/30"
                  }`}
                >
                  {s.permission_status === "ACTIVE" ? "PERMITTED" : "NO PERMIT"}
                </span>
              </div>
              <div className="text-xs text-text-muted mt-1 font-mono">
                {s.channel_id || "Direct Capture / Local File"}
              </div>
            </div>

            <div className="mt-6 pt-4 border-t border-border flex items-center justify-between">
              <span className="text-[11px] text-text-muted flex items-center gap-1.5">
                <Radio className="w-3.5 h-3.5 text-text-muted" />
                <span>Status: Offline</span>
              </span>
              <button
                disabled={s.permission_status !== "ACTIVE"}
                className={`px-3 py-1.5 rounded text-xs font-bold transition-all ${
                  s.permission_status === "ACTIVE"
                    ? "bg-accent-cyan hover:bg-accent-cyan-bright text-slate-950"
                    : "bg-surface-elevated text-text-muted cursor-not-allowed"
                }`}
              >
                Intake Recording
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
