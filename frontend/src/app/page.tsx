"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Film,
  Users,
  ShieldCheck,
  HardDrive,
  Layers,
  ArrowUpRight,
  Sparkles,
  Play,
  Cpu,
  CheckCircle,
  XCircle,
} from "lucide-react";
import { api, DashboardStats, Clip } from "@/services/api";

export default function OverviewPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [recentClips, setRecentClips] = useState<Clip[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.getDashboardStats().catch(() => null),
      api.getClips(0, 4).catch(() => ({ items: [] })),
    ]).then(([statsRes, clipsRes]) => {
      if (statsRes) setStats(statsRes);
      if (clipsRes) setRecentClips(clipsRes.items);
      setLoading(false);
    });
  }, []);

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Hero Welcome Banner */}
      <div className="relative overflow-hidden rounded-2xl p-8 border border-border bg-gradient-to-r from-surface via-surface-elevated to-surface">
        <div className="relative z-10 max-w-2xl">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-accent-cyan/10 border border-accent-cyan/30 text-accent-cyan text-xs font-semibold mb-3">
            <Sparkles className="w-3.5 h-3.5" />
            <span>Grand Theft Auto VI Autonomous Studio</span>
          </div>
          <h1 className="text-3xl font-extrabold tracking-tight text-text-primary">
            GTA 6 AI Clip Factory
          </h1>
          <p className="mt-2 text-sm text-text-secondary leading-relaxed">
            Extracting 15–60s viral 9:16 vertical clips from long-form authorized gameplay streams.
            Equipped with multi-stage audio excitement detection, facecam alignment, and burned-in dynamic captions.
          </p>
          <div className="mt-5 flex gap-3">
            <Link
              href="/clips"
              className="px-4 py-2 rounded-lg bg-accent-cyan hover:bg-accent-cyan-bright text-slate-950 text-xs font-bold transition-all glow-cyan flex items-center gap-2"
            >
              <Film className="w-4 h-4" />
              <span>Explore Finished Clips</span>
            </Link>
            <Link
              href="/queue"
              className="px-4 py-2 rounded-lg bg-surface-elevated hover:bg-surface-hover border border-border text-text-primary text-xs font-semibold transition-all flex items-center gap-2"
            >
              <Layers className="w-4 h-4" />
              <span>Processing Queue</span>
            </Link>
          </div>
        </div>
      </div>

      {/* KPI Metric Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Clips */}
        <div className="p-5 rounded-xl bg-surface border border-border flex items-center justify-between">
          <div>
            <div className="text-xs text-text-muted font-medium">Finished Clips</div>
            <div className="text-2xl font-extrabold text-text-primary mt-1">
              {stats?.total_clips ?? 0}
            </div>
            <div className="text-[11px] text-accent-cyan mt-1 flex items-center gap-1">
              <span>1080x1920 Vertical MP4</span>
            </div>
          </div>
          <div className="w-12 h-12 rounded-lg bg-accent-cyan/10 border border-accent-cyan/20 flex items-center justify-center text-accent-cyan">
            <Film className="w-6 h-6" />
          </div>
        </div>

        {/* Registered Streamers */}
        <div className="p-5 rounded-xl bg-surface border border-border flex items-center justify-between">
          <div>
            <div className="text-xs text-text-muted font-medium">Active Streamers</div>
            <div className="text-2xl font-extrabold text-text-primary mt-1">
              {stats?.total_streamers ?? 0}
            </div>
            <div className="text-[11px] text-emerald-400 mt-1 flex items-center gap-1">
              <span>{stats?.active_permissions ?? 0} with Active Consent</span>
            </div>
          </div>
          <div className="w-12 h-12 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
            <Users className="w-6 h-6" />
          </div>
        </div>

        {/* Storage Consumed */}
        <div className="p-5 rounded-xl bg-surface border border-border flex items-center justify-between">
          <div>
            <div className="text-xs text-text-muted font-medium">Storage Consumed</div>
            <div className="text-2xl font-extrabold text-text-primary mt-1">
              {stats ? `${(stats.total_storage_mb / 1024).toFixed(2)} GB` : "0.00 GB"}
            </div>
            <div className="text-[11px] text-text-muted mt-1">
              Raw recordings & rendered clips
            </div>
          </div>
          <div className="w-12 h-12 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
            <HardDrive className="w-6 h-6" />
          </div>
        </div>

        {/* GPU Status */}
        <div className="p-5 rounded-xl bg-surface border border-border flex items-center justify-between">
          <div>
            <div className="text-xs text-text-muted font-medium">Hardware Status</div>
            <div className="text-sm font-bold text-text-primary mt-1 truncate max-w-[150px]">
              {stats?.gpu_info?.device_name || "RTX 3050 6GB"}
            </div>
            <div className="text-[11px] text-emerald-400 mt-1">
              CUDA Active • 6GB VRAM
            </div>
          </div>
          <div className="w-12 h-12 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400">
            <Cpu className="w-6 h-6" />
          </div>
        </div>
      </div>

      {/* Integration Status Panel */}
      <div className="p-6 rounded-xl bg-surface border border-border">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-bold text-text-primary tracking-wide uppercase">
            Active Integrations & Intelligence Providers
          </h2>
          <Link
            href="/settings"
            className="text-xs text-accent-cyan hover:underline flex items-center gap-1 font-medium"
          >
            <span>Manage Credentials</span>
            <ArrowUpRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 text-xs">
          {/* YouTube API */}
          <div className="p-3.5 rounded-lg bg-surface-elevated border border-border">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-text-primary">YouTube Data API</span>
              {stats?.integrations?.youtube_api?.configured ? (
                <CheckCircle className="w-4 h-4 text-emerald-400" />
              ) : (
                <span className="text-[10px] text-text-muted font-mono">Offline / Manual</span>
              )}
            </div>
            <div className="text-[11px] text-text-muted mt-2">
              Key: {stats?.integrations?.youtube_api?.key_hint ?? "not configured"}
            </div>
          </div>

          {/* Gemini VLM */}
          <div className="p-3.5 rounded-lg bg-surface-elevated border border-border">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-text-primary">Google Gemini</span>
              {stats?.integrations?.gemini?.configured ? (
                <CheckCircle className="w-4 h-4 text-emerald-400" />
              ) : (
                <span className="text-[10px] text-text-muted font-mono">Unset</span>
              )}
            </div>
            <div className="text-[11px] text-text-muted mt-2">
              Model: {stats?.integrations?.gemini?.model ?? "gemini-1.5-flash"}
            </div>
          </div>

          {/* OpenAI VLM */}
          <div className="p-3.5 rounded-lg bg-surface-elevated border border-border">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-text-primary">OpenAI VLM</span>
              {stats?.integrations?.openai?.configured ? (
                <CheckCircle className="w-4 h-4 text-emerald-400" />
              ) : (
                <span className="text-[10px] text-text-muted font-mono">Unset</span>
              )}
            </div>
            <div className="text-[11px] text-text-muted mt-2">
              Key: {stats?.integrations?.openai?.key_hint ?? "not configured"}
            </div>
          </div>

          {/* Active Pipeline Fallback */}
          <div className="p-3.5 rounded-lg bg-surface-elevated border border-border">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-text-primary">Active Engine</span>
              <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-accent-cyan/20 text-accent-cyan uppercase">
                {stats?.integrations?.active_vlm ?? "LOCAL"}
              </span>
            </div>
            <div className="text-[11px] text-text-muted mt-2">
              Fallback: Local Heuristic
            </div>
          </div>
        </div>
      </div>

      {/* Recent Clips Grid */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-bold text-text-primary tracking-wide uppercase">
            Recent Rendered Highlights
          </h2>
          <Link
            href="/clips"
            className="text-xs text-accent-cyan hover:underline flex items-center gap-1 font-medium"
          >
            <span>View All Library</span>
            <ArrowUpRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        {recentClips.length === 0 ? (
          <div className="p-12 text-center rounded-xl bg-surface border border-border">
            <Film className="w-10 h-10 text-text-muted mx-auto mb-3 opacity-50" />
            <div className="text-sm font-medium text-text-primary">No Clips Rendered Yet</div>
            <p className="text-xs text-text-muted mt-1 max-w-sm mx-auto">
              Ingest an authorized GTA 6 stream or local recording in the Stream Monitor to begin generating viral vertical clips.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {recentClips.map((clip) => (
              <div
                key={clip.id}
                className="rounded-xl overflow-hidden bg-surface border border-border hover:border-accent-cyan/50 transition-all group"
              >
                <div className="aspect-[9/16] bg-slate-900 relative flex items-center justify-center">
                  <div className="w-12 h-12 rounded-full bg-accent-cyan/20 flex items-center justify-center text-accent-cyan group-hover:scale-110 transition-transform">
                    <Play className="w-5 h-5 fill-current" />
                  </div>
                  <span className="absolute top-3 right-3 px-2 py-0.5 rounded-full text-[10px] font-bold bg-slate-950/80 text-accent-cyan border border-accent-cyan/30">
                    {clip.score.toFixed(1)}
                  </span>
                  <span className="absolute bottom-3 left-3 px-2 py-0.5 rounded text-[10px] font-mono bg-slate-950/80 text-text-muted">
                    {clip.duration_seconds.toFixed(0)}s
                  </span>
                </div>
                <div className="p-4">
                  <div className="text-xs font-bold text-text-primary truncate">{clip.title}</div>
                  <div className="text-[11px] text-text-muted mt-1">{clip.preset}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
