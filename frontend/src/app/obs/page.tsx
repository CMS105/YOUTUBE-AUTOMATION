"use client";

import { useEffect, useState } from "react";
import {
  CircleDot,
  Radio,
  HardDrive,
  RefreshCw,
  Play,
  Square,
  CheckCircle2,
  AlertCircle,
  Clock,
  Film,
  Zap,
  Layers,
  Settings,
} from "lucide-react";
import { api, OBSStatus, RecordingSession, CreatorAuthorization } from "@/services/api";

export default function OBSPage() {
  const [status, setStatus] = useState<OBSStatus | null>(null);
  const [sessions, setSessions] = useState<RecordingSession[]>([]);
  const [authorizations, setAuthorizations] = useState<CreatorAuthorization[]>([]);
  const [loading, setLoading] = useState(true);
  const [connecting, setConnecting] = useState(false);
  const [selectedChannel, setSelectedChannel] = useState("");
  const [customSource, setCustomSource] = useState("");
  const [processingId, setProcessingId] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [notice, setNotice] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const showNotice = (type: "success" | "error", text: string) => {
    setNotice({ type, text });
    setTimeout(() => setNotice(null), 5000);
  };

  const loadData = async () => {
    try {
      const [obsRes, sessRes, authRes] = await Promise.all([
        api.getOBSStatus().catch(() => null),
        api.getRecordingSessions({ limit: 15 }).catch(() => ({ items: [], total: 0, active_sessions: 0 })),
        api.getAuthorizations({ status: "ACTIVE" }).catch(() => ({ items: [], total: 0, active_count: 0 })),
      ]);
      if (obsRes) setStatus(obsRes);
      setSessions(sessRes.items);
      setAuthorizations(authRes.items);
      if (authRes.items.length > 0 && !selectedChannel) {
        setSelectedChannel(authRes.items[0].channel_id);
      }
    } catch (e: any) {
      showNotice("error", e.message || "Failed to load OBS status");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleConnect = async () => {
    try {
      setConnecting(true);
      const res = await api.connectOBS();
      setStatus(res);
      if (res.connected) {
        showNotice("success", `Connected to OBS Studio (v${res.version || "5.x"}) at ${res.host}:${res.port}!`);
      } else {
        showNotice("error", res.error || "Cannot connect to OBS Studio WebSocket.");
      }
    } catch (e: any) {
      showNotice("error", e.message || "Connection attempt failed.");
    } finally {
      setConnecting(false);
    }
  };

  const handleStartRecording = async () => {
    if (!selectedChannel) {
      showNotice("error", "Please select an authorized creator channel first.");
      return;
    }
    try {
      setActionLoading(true);
      await api.startOBSRecording({
        channel_id: selectedChannel,
        custom_source: customSource || undefined,
      });
      showNotice("success", "OBS recording started successfully!");
      loadData();
    } catch (e: any) {
      showNotice("error", e.message || "Failed to start OBS recording.");
    } finally {
      setActionLoading(false);
    }
  };

  const handleStopRecording = async () => {
    try {
      setActionLoading(true);
      const res = await api.stopOBSRecording();
      showNotice("success", res.message || "Recording stopped and registered in database.");
      loadData();
    } catch (e: any) {
      showNotice("error", e.message || "Failed to stop recording.");
    } finally {
      setActionLoading(false);
    }
  };

  const handleProcessSession = async (session: RecordingSession) => {
    try {
      setProcessingId(session.session_id);
      const res = await api.processRecordingSession(session.session_id);
      showNotice("success", `AI clipping initiated! Job #${res.job_id} queued.`);
      loadData();
    } catch (e: any) {
      showNotice("error", e.message || "Failed to initiate AI clipping.");
    } finally {
      setProcessingId(null);
    }
  };

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8 bg-[#0B1220] min-h-screen text-[#E5E7EB]">
      {/* Toast Notice */}
      {notice && (
        <div
          className={`p-4 rounded-xl border flex items-center justify-between shadow-2xl transition-all ${
            notice.type === "success"
              ? "bg-emerald-950/70 border-emerald-500/40 text-emerald-300"
              : "bg-rose-950/70 border-rose-500/40 text-rose-300"
          }`}
        >
          <div className="flex items-center gap-3">
            {notice.type === "success" ? <CheckCircle2 className="w-5 h-5" /> : <AlertCircle className="w-5 h-5" />}
            <span className="text-sm font-medium">{notice.text}</span>
          </div>
          <button onClick={() => setNotice(null)} className="text-xs font-mono opacity-70 hover:opacity-100">
            DISMISS
          </button>
        </div>
      )}

      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#172337] pb-6">
        <div>
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-rose-500/10 text-rose-400 border border-rose-500/20">
              <CircleDot className="w-6 h-6 animate-pulse" />
            </div>
            <div>
              <h1 className="text-2xl font-black tracking-tight text-white flex items-center gap-2">
                OBS Studio Recording Hub
                <span className="text-xs px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-400 border border-blue-500/30 font-mono">
                  WEBSOCKET v5
                </span>
              </h1>
              <p className="text-xs text-[#94A3B8] mt-0.5">
                Automated broadcast recording & hardware capture pipeline.
              </p>
            </div>
          </div>
        </div>

        <button
          onClick={handleConnect}
          disabled={connecting}
          className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-[#111C2E] border border-[#172337] text-xs font-semibold hover:border-[#38BDF8]/40 hover:text-[#38BDF8] transition-all disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 text-[#38BDF8] ${connecting ? "animate-spin" : ""}`} />
          {connecting ? "Testing Connection..." : "Reconnect OBS"}
        </button>
      </div>

      {/* Hardware & Connection Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* OBS Status Card */}
        <div className="p-6 rounded-2xl bg-[#111C2E] border border-[#172337] space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-[#94A3B8] uppercase tracking-wider">OBS Connection</span>
            {status?.connected ? (
              <span className="px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 text-[11px] font-bold flex items-center gap-1.5 font-mono">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                ONLINE
              </span>
            ) : (
              <span className="px-2.5 py-0.5 rounded-full bg-rose-500/20 text-rose-400 border border-rose-500/40 text-[11px] font-bold font-mono">
                DISCONNECTED
              </span>
            )}
          </div>

          <div className="space-y-2 text-xs">
            <div className="flex justify-between py-1 border-b border-[#172337]">
              <span className="text-[#94A3B8]">WebSocket Endpoint</span>
              <span className="text-white font-mono">{status?.host || "127.0.0.1"}:{status?.port || 4455}</span>
            </div>
            <div className="flex justify-between py-1 border-b border-[#172337]">
              <span className="text-[#94A3B8]">OBS Version</span>
              <span className="text-white font-mono">{status?.version || "Unknown"}</span>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-[#94A3B8]">Password Protection</span>
              <span className="text-emerald-400 font-mono">Configured</span>
            </div>
          </div>
        </div>

        {/* Live Recording Status Card */}
        <div className="p-6 rounded-2xl bg-[#111C2E] border border-[#172337] space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-[#94A3B8] uppercase tracking-wider">Recording State</span>
            {status?.is_recording ? (
              <span className="px-2.5 py-0.5 rounded-full bg-rose-500 text-white font-black text-[11px] flex items-center gap-1.5 animate-pulse font-mono">
                <CircleDot className="w-3.5 h-3.5" />
                RECORDING
              </span>
            ) : (
              <span className="px-2.5 py-0.5 rounded-full bg-slate-800 text-slate-400 text-[11px] font-bold font-mono">
                STANDBY
              </span>
            )}
          </div>

          <div className="space-y-2 text-xs">
            <div className="flex justify-between py-1 border-b border-[#172337]">
              <span className="text-[#94A3B8]">Recording Duration</span>
              <span className="text-rose-400 font-mono font-bold">
                {status?.recording_time_seconds ? `${status.recording_time_seconds}s` : "0.0s"}
              </span>
            </div>
            <div className="flex justify-between py-1 border-b border-[#172337]">
              <span className="text-[#94A3B8]">Active Sessions</span>
              <span className="text-white font-mono">{sessions.filter((s) => s.status === "recording").length}</span>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-[#94A3B8]">Auto-Process AI</span>
              <span className="text-[#38BDF8] font-mono">ENABLED</span>
            </div>
          </div>
        </div>

        {/* Disk Space & Safety Card */}
        <div className="p-6 rounded-2xl bg-[#111C2E] border border-[#172337] space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-[#94A3B8] uppercase tracking-wider">Disk Storage Guard</span>
            <span className={`px-2.5 py-0.5 rounded-full text-[11px] font-bold font-mono ${status?.disk_sufficient ? "bg-emerald-500/20 text-emerald-400" : "bg-rose-500/20 text-rose-400"}`}>
              {status?.disk_sufficient ? "SPACE SAFE" : "LOW STORAGE"}
            </span>
          </div>

          <div className="space-y-2 text-xs">
            <div className="flex justify-between py-1 border-b border-[#172337]">
              <span className="text-[#94A3B8]">Free Storage</span>
              <span className="text-emerald-400 font-mono font-bold">{status?.disk_free_gb || 0} GB</span>
            </div>
            <div className="flex justify-between py-1 border-b border-[#172337]">
              <span className="text-[#94A3B8]">Total Capacity</span>
              <span className="text-white font-mono">{status?.disk_total_gb || 0} GB</span>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-[#94A3B8]">Min Buffer Threshold</span>
              <span className="text-amber-400 font-mono">5.0 GB</span>
            </div>
          </div>
        </div>
      </div>

      {/* Live Recording Control Console */}
      <div className="p-6 rounded-2xl bg-[#111C2E] border border-[#172337] space-y-6">
        <h2 className="text-base font-bold text-white flex items-center gap-2">
          <Radio className="w-5 h-5 text-rose-400" />
          OBS Recording Console
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="text-xs text-[#94A3B8] block mb-1.5 font-semibold">
              Select Authorized Streamer / Channel
            </label>
            <select
              value={selectedChannel}
              onChange={(e) => setSelectedChannel(e.target.value)}
              className="w-full p-2.5 rounded-lg bg-[#0B1220] border border-[#172337] text-xs text-white focus:outline-none focus:border-[#38BDF8]"
            >
              {authorizations.length === 0 ? (
                <option value="">No creators currently authorized (Go to Authorizations)</option>
              ) : (
                authorizations.map((auth) => (
                  <option key={auth.channel_id} value={auth.channel_id}>
                    {auth.creator_name} ({auth.channel_id}) — Input: {auth.authorized_source || "Default"}
                  </option>
                ))
              )}
            </select>
          </div>

          <div>
            <label className="text-xs text-[#94A3B8] block mb-1.5 font-semibold">
              Override Ingestion Source / Window (Optional)
            </label>
            <input
              type="text"
              placeholder="e.g. OBS:GameCapture_GTA6 or rtmp://127.0.0.1:1935/live"
              value={customSource}
              onChange={(e) => setCustomSource(e.target.value)}
              className="w-full p-2.5 rounded-lg bg-[#0B1220] border border-[#172337] text-xs text-white placeholder-[#94A3B8] focus:outline-none focus:border-[#38BDF8]"
            />
          </div>
        </div>

        <div className="flex items-center gap-4 pt-4 border-t border-[#172337]">
          {status?.is_recording ? (
            <button
              onClick={handleStopRecording}
              disabled={actionLoading}
              className="px-6 py-3 rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-bold text-xs flex items-center gap-2 shadow-lg shadow-rose-900/30 transition-all disabled:opacity-50"
            >
              <Square className="w-4 h-4 fill-current" />
              {actionLoading ? "Stopping OBS..." : "Stop Recording Session"}
            </button>
          ) : (
            <button
              onClick={handleStartRecording}
              disabled={actionLoading || authorizations.length === 0}
              className="px-6 py-3 rounded-xl bg-gradient-to-r from-rose-600 to-rose-700 hover:brightness-110 text-white font-bold text-xs flex items-center gap-2 shadow-lg shadow-rose-900/30 transition-all disabled:opacity-50"
            >
              <Play className="w-4 h-4 fill-current" />
              {actionLoading ? "Starting OBS..." : "Start OBS Recording"}
            </button>
          )}

          <div className="text-xs text-[#94A3B8]">
            {authorizations.length === 0 && (
              <span className="text-amber-400">
                ⚠️ Recording requires at least one ACTIVE creator authorization.
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Recording Sessions Ledger */}
      <div className="p-6 rounded-2xl bg-[#111C2E] border border-[#172337] space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-bold text-white flex items-center gap-2">
            <Layers className="w-5 h-5 text-[#38BDF8]" />
            Recent Recording Sessions
          </h2>
          <span className="text-xs text-[#94A3B8] font-mono">{sessions.length} RECORDINGS</span>
        </div>

        {sessions.length === 0 ? (
          <div className="p-12 text-center text-xs text-[#94A3B8]">
            No recording sessions logged yet. Start a recording above to capture authorized gameplay!
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-[#0B1220] text-[#94A3B8] font-mono border-b border-[#172337]">
                <tr>
                  <th className="p-3">Session ID</th>
                  <th className="p-3">Channel / Creator</th>
                  <th className="p-3">Source Feed</th>
                  <th className="p-3">Duration</th>
                  <th className="p-3">Status</th>
                  <th className="p-3">Timestamp</th>
                  <th className="p-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#172337]">
                {sessions.map((sess) => (
                  <tr key={sess.id} className="hover:bg-[#172337]/40 transition-colors">
                    <td className="p-3 font-mono text-[#38BDF8]">{sess.session_id.slice(0, 10)}...</td>
                    <td className="p-3 font-semibold text-white">{sess.channel_id}</td>
                    <td className="p-3 text-[#94A3B8] font-mono truncate max-w-[160px]">{sess.source_input}</td>
                    <td className="p-3 font-mono">{sess.duration_seconds.toFixed(1)}s</td>
                    <td className="p-3">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold font-mono ${
                          sess.status === "completed"
                            ? "bg-emerald-500/20 text-emerald-400"
                            : sess.status === "recording"
                            ? "bg-rose-500 text-white animate-pulse"
                            : "bg-slate-800 text-slate-400"
                        }`}
                      >
                        {sess.status.toUpperCase()}
                      </span>
                    </td>
                    <td className="p-3 text-slate-500 font-mono">
                      {new Date(sess.started_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                    </td>
                    <td className="p-3 text-right">
                      {sess.recording_id && (
                        <button
                          onClick={() => handleProcessSession(sess)}
                          disabled={processingId === sess.session_id}
                          className="px-3 py-1.5 rounded-lg bg-[#38BDF8]/10 text-[#38BDF8] hover:bg-[#38BDF8]/20 font-bold font-mono text-[11px] transition-all disabled:opacity-50"
                        >
                          {processingId === sess.session_id ? "Processing..." : "Generate AI Clips"}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
