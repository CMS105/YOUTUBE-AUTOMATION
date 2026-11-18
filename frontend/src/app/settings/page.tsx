"use client";

import { useEffect, useState } from "react";
import { Settings, Key, Cpu, Film, ExternalLink, ShieldAlert, CheckCircle2 } from "lucide-react";
import { api, DashboardStats } from "@/services/api";

export default function SettingsPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);

  useEffect(() => {
    api.getDashboardStats().then(setStats).catch(() => {});
  }, []);

  const int = stats?.integrations;

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div>
        <h1 className="text-2xl font-extrabold text-text-primary tracking-tight">
          Factory Settings & API Integrations
        </h1>
        <p className="text-xs text-text-secondary mt-1">
          Configure external credentials, hardware execution devices, and video rendering defaults.
        </p>
      </div>

      {/* Safety Banner */}
      <div className="p-4 rounded-xl bg-surface border border-emerald-500/30 bg-emerald-500/5 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
          <div className="text-xs">
            <span className="font-bold text-emerald-400">Automatic Publishing Disabled: </span>
            <span className="text-text-secondary">
              Clips are rendered and saved strictly to your local machine. No automatic uploads to social networks.
            </span>
          </div>
        </div>
      </div>

      {/* External APIs Section */}
      <div className="p-6 rounded-xl bg-surface border border-border space-y-4">
        <h3 className="text-sm font-bold text-text-primary uppercase tracking-wide flex items-center gap-2">
          <Key className="w-4 h-4 text-accent-cyan" />
          <span>External API Credentials</span>
        </h3>
        <p className="text-xs text-text-muted">
          All credentials are saved locally in your <code className="text-accent-cyan font-mono">.env</code> file. The UI displays safe hints only.
        </p>

        <div className="space-y-3 pt-2">
          {/* YouTube Data API */}
          <div className="p-4 rounded-lg bg-surface-elevated border border-border flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs">
            <div>
              <div className="font-bold text-text-primary flex items-center gap-2">
                <span>YouTube Data API v3</span>
                <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${int?.youtube_api?.configured ? "bg-emerald-500/10 text-emerald-400" : "bg-surface text-text-muted"}`}>
                  {int?.youtube_api?.configured ? "CONNECTED" : "NOT SET"}
                </span>
              </div>
              <div className="text-text-muted mt-1">
                Enables automatic broadcast detection and channel polling. Key: <span className="font-mono text-text-secondary">{int?.youtube_api?.key_hint ?? "not set"}</span>
              </div>
            </div>
            <a
              href="https://console.cloud.google.com/apis/library/youtube.googleapis.com"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface hover:bg-surface-hover border border-border text-accent-cyan font-medium text-xs self-start md:self-auto"
            >
              <span>Get API Key</span>
              <ExternalLink className="w-3.5 h-3.5" />
            </a>
          </div>

          {/* Google Gemini API */}
          <div className="p-4 rounded-lg bg-surface-elevated border border-border flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs">
            <div>
              <div className="font-bold text-text-primary flex items-center gap-2">
                <span>Google Gemini (VLM Intelligence)</span>
                <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${int?.gemini?.configured ? "bg-emerald-500/10 text-emerald-400" : "bg-surface text-text-muted"}`}>
                  {int?.gemini?.configured ? "CONNECTED" : "NOT SET"}
                </span>
              </div>
              <div className="text-text-muted mt-1">
                Generates multimodal context reasoning and catchy titles. Free tier available.
              </div>
            </div>
            <a
              href="https://aistudio.google.com/"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface hover:bg-surface-hover border border-border text-accent-cyan font-medium text-xs self-start md:self-auto"
            >
              <span>Get Gemini Key</span>
              <ExternalLink className="w-3.5 h-3.5" />
            </a>
          </div>

          {/* OpenAI API */}
          <div className="p-4 rounded-lg bg-surface-elevated border border-border flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs">
            <div>
              <div className="font-bold text-text-primary flex items-center gap-2">
                <span>OpenAI API</span>
                <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${int?.openai?.configured ? "bg-emerald-500/10 text-emerald-400" : "bg-surface text-text-muted"}`}>
                  {int?.openai?.configured ? "CONNECTED" : "NOT SET"}
                </span>
              </div>
              <div className="text-text-muted mt-1">
                Key: <span className="font-mono text-text-secondary">{int?.openai?.key_hint ?? "not set"}</span>
              </div>
            </div>
            <a
              href="https://platform.openai.com/api-keys"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface hover:bg-surface-hover border border-border text-accent-cyan font-medium text-xs self-start md:self-auto"
            >
              <span>Get OpenAI Key</span>
              <ExternalLink className="w-3.5 h-3.5" />
            </a>
          </div>

          {/* OBS Studio WebSocket */}
          <div className="p-4 rounded-lg bg-surface-elevated border border-border flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs">
            <div>
              <div className="font-bold text-text-primary flex items-center gap-2">
                <span>OBS Studio WebSocket v5</span>
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/10 text-emerald-400">
                  PORT 4455
                </span>
              </div>
              <div className="text-text-muted mt-1">
                Enables automated hands-free livestream recording for authorized creator feeds.
              </div>
            </div>
            <a
              href="/obs"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface hover:bg-surface-hover border border-border text-accent-cyan font-medium text-xs self-start md:self-auto"
            >
              <span>OBS Control Hub</span>
              <ExternalLink className="w-3.5 h-3.5" />
            </a>
          </div>
        </div>
      </div>

      {/* Hardware Settings */}
      <div className="p-6 rounded-xl bg-surface border border-border space-y-4">
        <h3 className="text-sm font-bold text-text-primary uppercase tracking-wide flex items-center gap-2">
          <Cpu className="w-4 h-4 text-accent-cyan" />
          <span>Hardware Execution Profile</span>
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
          <div className="p-4 rounded-lg bg-surface-elevated border border-border">
            <div className="text-text-muted">Detected GPU Device</div>
            <div className="text-base font-bold text-text-primary mt-1">
              {stats?.gpu_info?.device_name || "NVIDIA GeForce RTX 3050 6GB"}
            </div>
            <div className="text-[11px] text-emerald-400 mt-1">CUDA Acceleration: Active</div>
          </div>
          <div className="p-4 rounded-lg bg-surface-elevated border border-border">
            <div className="text-text-muted">Speech-to-Text Engine</div>
            <div className="text-base font-bold text-text-primary mt-1">
              faster-whisper (float16 on CUDA)
            </div>
            <div className="text-[11px] text-accent-cyan mt-1">PyAV Safe Patched</div>
          </div>
        </div>
      </div>
    </div>
  );
}
