"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Compass,
  Radio,
  Search,
  RefreshCw,
  ExternalLink,
  ShieldCheck,
  ShieldAlert,
  CircleDot,
  CheckCircle2,
  Clock,
  Film,
  Zap,
  Play,
  Square,
  AlertCircle,
  KeyRound,
} from "lucide-react";
import { api, LiveDiscovery, CreatorAuthorization } from "@/services/api";

export default function DiscoveriesPage() {
  const [discoveries, setDiscoveries] = useState<LiveDiscovery[]>([]);
  const [loading, setLoading] = useState(true);
  const [polling, setPolling] = useState(false);
  const [automating, setAutomating] = useState(false);
  const [actionLoadingId, setActionLoadingId] = useState<number | null>(null);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<"all" | "authorized" | "awaiting" | "recording" | "completed" | "ended">("all");
  const [stats, setStats] = useState({ total: 0, live: 0, authorized: 0, recording: 0 });
  const [quotaInfo, setQuotaInfo] = useState<any>(null);

  // Authorize Modal state
  const [authModalDiscovery, setAuthModalDiscovery] = useState<LiveDiscovery | null>(null);
  const [authSource, setAuthSource] = useState("");
  const [authScope, setAuthScope] = useState<"clip_creation" | "full_access">("clip_creation");
  const [authNotes, setAuthNotes] = useState("");
  const [submittingAuth, setSubmittingAuth] = useState(false);
  const [notification, setNotification] = useState<{ type: "success" | "error"; message: string } | null>(null);

  const showNotice = (type: "success" | "error", message: string) => {
    setNotification({ type, message });
    setTimeout(() => setNotification(null), 5000);
  };

  const loadDiscoveries = async () => {
    try {
      setLoading(true);
      const res = await api.getDiscoveries();
      setDiscoveries(res.items);
      setStats({
        total: res.total,
        live: res.live_count,
        authorized: res.authorized_count,
        recording: res.recording_count,
      });
      setQuotaInfo(res.quota_status);
    } catch (e: any) {
      showNotice("error", e.message || "Failed to load live discoveries.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDiscoveries();
    const interval = setInterval(loadDiscoveries, 15000);
    return () => clearInterval(interval);
  }, []);

  const handlePollNow = async () => {
    try {
      setPolling(true);
      const res = await api.pollDiscoveries();
      if (res.success) {
        showNotice("success", `Discovery completed! Discovered ${res.items_discovered} streams (${res.new_discoveries} new). Query: "${res.query_used}".`);
        loadDiscoveries();
      } else {
        showNotice("error", res.error || "Discovery poll failed.");
      }
    } catch (e: any) {
      showNotice("error", e.message || "Error running discovery poll.");
    } finally {
      setPolling(false);
    }
  };

  const handleRunAutomation = async () => {
    try {
      setAutomating(true);
      const res = await api.runAutomationCycle();
      showNotice("success", `Automation cycle finished: ${res.recordings_started} recordings started, ${res.recordings_stopped} stopped.`);
      loadDiscoveries();
    } catch (e: any) {
      showNotice("error", e.message || "Error executing automation cycle.");
    } finally {
      setAutomating(false);
    }
  };

  const handleStartRecording = async (discovery: LiveDiscovery) => {
    try {
      setActionLoadingId(discovery.id);
      await api.startOBSRecording({
        channel_id: discovery.channel_id,
        video_id: discovery.video_id,
        discovery_id: discovery.id,
      });
      showNotice("success", `OBS recording started for "${discovery.channel_title}"!`);
      loadDiscoveries();
    } catch (e: any) {
      showNotice("error", e.message || "Failed to start OBS recording.");
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleStopRecording = async (discovery: LiveDiscovery) => {
    try {
      setActionLoadingId(discovery.id);
      const res = await api.stopOBSRecording();
      showNotice("success", res.message || "Recording stopped and registered.");
      loadDiscoveries();
    } catch (e: any) {
      showNotice("error", e.message || "Failed to stop recording.");
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleOpenAuthModal = (discovery: LiveDiscovery) => {
    setAuthModalDiscovery(discovery);
    setAuthSource(`OBS:WindowCapture_${discovery.channel_title.replace(/\\s+/g, "_")}`);
    setAuthScope("clip_creation");
    setAuthNotes(`Authorized via Live Discoveries Dashboard on ${new Date().toLocaleDateString()}`);
  };

  const handleSubmitAuthorization = async () => {
    if (!authModalDiscovery) return;
    try {
      setSubmittingAuth(true);
      await api.authorizeCreator({
        channel_id: authModalDiscovery.channel_id,
        creator_name: authModalDiscovery.channel_title,
        authorized_source: authSource,
        allowed_scope: authScope,
        notes: authNotes,
        status: "ACTIVE",
      });
      showNotice("success", `Creator "${authModalDiscovery.channel_title}" successfully AUTHORIZED! Approved input saved.`);
      setAuthModalDiscovery(null);
      loadDiscoveries();
    } catch (e: any) {
      showNotice("error", e.message || "Failed to authorize creator.");
    } finally {
      setSubmittingAuth(false);
    }
  };

  // Filtered discoveries
  const filtered = discoveries.filter((d) => {
    const matchesSearch =
      d.title.toLowerCase().includes(search.toLowerCase()) ||
      d.channel_title.toLowerCase().includes(search.toLowerCase());

    if (!matchesSearch) return false;

    if (filter === "authorized") return d.authorization_status === "AUTHORIZED";
    if (filter === "awaiting") return d.authorization_status === "AWAITING_AUTHORIZATION";
    if (filter === "recording") return d.recording_status === "RECORDING";
    if (filter === "completed") return d.recording_status === "RECORDED" || d.recording_status === "CLIPPED";
    if (filter === "ended") return d.live_status === "ended";
    return true;
  });

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8 bg-[#0B1220] min-h-screen text-[#E5E7EB]">
      {/* Toast Notification */}
      {notification && (
        <div
          className={`p-4 rounded-xl border flex items-center justify-between shadow-2xl transition-all ${
            notification.type === "success"
              ? "bg-emerald-950/70 border-emerald-500/40 text-emerald-300"
              : "bg-rose-950/70 border-rose-500/40 text-rose-300"
          }`}
        >
          <div className="flex items-center gap-3">
            {notification.type === "success" ? <CheckCircle2 className="w-5 h-5" /> : <AlertCircle className="w-5 h-5" />}
            <span className="text-sm font-medium">{notification.message}</span>
          </div>
          <button onClick={() => setNotification(null)} className="text-xs font-mono opacity-70 hover:opacity-100">
            DISMISS
          </button>
        </div>
      )}

      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#172337] pb-6">
        <div>
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-[#38BDF8]/10 text-[#38BDF8] border border-[#38BDF8]/20">
              <Compass className="w-6 h-6 animate-spin-slow" />
            </div>
            <div>
              <h1 className="text-2xl font-black tracking-tight text-white flex items-center gap-2">
                Live Discoveries
                <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 flex items-center gap-1 font-mono">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  YOUTUBE API v3
                </span>
              </h1>
              <p className="text-xs text-[#94A3B8] mt-0.5">
                Public GTA 6 broadcasts across YouTube. Zero scraping: Official discovery & metadata.
              </p>
            </div>
          </div>
        </div>

        {/* Global Action Buttons */}
        <div className="flex items-center gap-3">
          <button
            onClick={handleRunAutomation}
            disabled={automating}
            className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-[#111C2E] border border-[#172337] text-xs font-semibold hover:border-[#38BDF8]/40 hover:text-[#38BDF8] transition-all disabled:opacity-50"
          >
            <Zap className={`w-4 h-4 text-amber-400 ${automating ? "animate-spin" : ""}`} />
            {automating ? "Running Cycle..." : "Run Automation"}
          </button>

          <button
            onClick={handlePollNow}
            disabled={polling}
            className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-gradient-to-r from-[#38BDF8] to-blue-600 text-slate-950 text-xs font-bold shadow-lg shadow-[#38BDF8]/20 hover:brightness-110 active:scale-95 transition-all disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${polling ? "animate-spin" : ""}`} />
            {polling ? "Searching YouTube..." : "Poll YouTube Now"}
          </button>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="p-4 rounded-xl bg-[#111C2E] border border-[#172337]">
          <div className="text-xs text-[#94A3B8]">Total Discovered</div>
          <div className="text-2xl font-black text-white mt-1">{stats.total}</div>
          <div className="text-[11px] text-[#38BDF8] mt-0.5 font-mono">ALL TIME CHANNELS</div>
        </div>
        <div className="p-4 rounded-xl bg-[#111C2E] border border-[#172337]">
          <div className="text-xs text-[#94A3B8]">Currently Streaming</div>
          <div className="text-2xl font-black text-emerald-400 mt-1 flex items-center gap-2">
            {stats.live}
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
          </div>
          <div className="text-[11px] text-emerald-400/80 mt-0.5 font-mono">ACTIVE GTA 6 BROADCASTS</div>
        </div>
        <div className="p-4 rounded-xl bg-[#111C2E] border border-[#172337]">
          <div className="text-xs text-[#94A3B8]">Authorized Creators</div>
          <div className="text-2xl font-black text-[#38BDF8] mt-1">{stats.authorized}</div>
          <div className="text-[11px] text-[#38BDF8]/80 mt-0.5 font-mono">PERMITTED FOR RECORDING</div>
        </div>
        <div className="p-4 rounded-xl bg-[#111C2E] border border-[#172337]">
          <div className="text-xs text-[#94A3B8]">API Quota Used</div>
          <div className="text-2xl font-black text-amber-400 mt-1">
            {quotaInfo?.used_units || 0}
            <span className="text-xs text-[#94A3B8] font-normal"> / 10,000</span>
          </div>
          <div className="text-[11px] text-[#94A3B8] mt-0.5 font-mono">DAILY UNITS (RESETS UTC)</div>
        </div>
      </div>

      {/* Search & Filter Bar */}
      <div className="flex flex-col md:flex-row gap-4 items-center justify-between p-4 rounded-xl bg-[#111C2E] border border-[#172337]">
        <div className="relative w-full md:w-80">
          <Search className="w-4 h-4 absolute left-3 top-3 text-[#94A3B8]" />
          <input
            type="text"
            placeholder="Search channels or titles..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2 bg-[#0B1220] border border-[#172337] rounded-lg text-xs text-white placeholder-[#94A3B8] focus:outline-none focus:border-[#38BDF8]"
          />
        </div>

        {/* Filter Pills */}
        <div className="flex items-center gap-1.5 overflow-x-auto w-full md:w-auto pb-1 md:pb-0">
          {[
            { id: "all", label: "All Streams" },
            { id: "authorized", label: "Authorized" },
            { id: "awaiting", label: "Awaiting Auth" },
            { id: "recording", label: "Recording" },
            { id: "completed", label: "Recorded / Clipped" },
            { id: "ended", label: "Ended" },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setFilter(tab.id as any)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-all ${
                filter === tab.id
                  ? "bg-[#38BDF8]/20 text-[#38BDF8] border border-[#38BDF8]/40 font-semibold"
                  : "text-[#94A3B8] hover:text-white hover:bg-[#172337]"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Stream Cards Grid */}
      {loading ? (
        <div className="p-16 text-center rounded-2xl bg-[#111C2E] border border-[#172337]">
          <RefreshCw className="w-8 h-8 text-[#38BDF8] animate-spin mx-auto mb-3" />
          <div className="text-sm font-semibold text-white">Loading Live GTA 6 Discoveries...</div>
        </div>
      ) : filtered.length === 0 ? (
        <div className="p-16 text-center rounded-2xl bg-[#111C2E] border border-[#172337] space-y-4">
          <Compass className="w-12 h-12 text-[#94A3B8] mx-auto opacity-40" />
          <div className="space-y-1">
            <div className="text-base font-bold text-white">No livestreams match your criteria</div>
            <p className="text-xs text-[#94A3B8] max-w-md mx-auto">
              Click &quot;Poll YouTube Now&quot; to search active GTA 6 gameplay broadcasts using official YouTube Data API endpoints.
            </p>
          </div>
          <button
            onClick={handlePollNow}
            disabled={polling}
            className="px-4 py-2 rounded-lg bg-[#38BDF8] text-slate-950 font-bold text-xs"
          >
            Poll YouTube Now
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filtered.map((item) => {
            const isAuthorized = item.authorization_status === "AUTHORIZED";
            const isRecording = item.recording_status === "RECORDING";
            const isLive = item.live_status === "live";

            return (
              <div
                key={item.id}
                className={`rounded-2xl bg-[#111C2E] border transition-all overflow-hidden flex flex-col justify-between hover:border-[#38BDF8]/40 hover:shadow-xl ${
                  isRecording
                    ? "border-rose-500/50 shadow-rose-950/20 shadow-lg"
                    : isAuthorized
                    ? "border-emerald-500/30"
                    : "border-[#172337]"
                }`}
              >
                {/* Thumbnail Header with badges */}
                <div className="relative aspect-video bg-[#0B1220] overflow-hidden">
                  {item.thumbnail_url ? (
                    <img
                      src={item.thumbnail_url}
                      alt={item.title}
                      className="w-full h-full object-cover group-hover:scale-105 transition-all duration-300"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-slate-700">
                      <Radio className="w-12 h-12 opacity-30" />
                    </div>
                  )}

                  {/* Gradient overlay */}
                  <div className="absolute inset-0 bg-gradient-to-t from-[#111C2E] via-transparent to-black/60" />

                  {/* Live Status Badge */}
                  <div className="absolute top-3 left-3 flex items-center gap-1.5">
                    {isLive ? (
                      <span className="px-2.5 py-0.5 rounded-full bg-rose-600/90 text-white font-black text-[10px] tracking-wider uppercase flex items-center gap-1 shadow-md">
                        <span className="w-1.5 h-1.5 rounded-full bg-white animate-ping" />
                        LIVE
                      </span>
                    ) : (
                      <span className="px-2.5 py-0.5 rounded-full bg-slate-800/90 text-slate-300 font-bold text-[10px] tracking-wider uppercase">
                        ENDED
                      </span>
                    )}

                    {isRecording && (
                      <span className="px-2.5 py-0.5 rounded-full bg-rose-500 text-white font-bold text-[10px] flex items-center gap-1 animate-pulse">
                        <CircleDot className="w-3 h-3" />
                        REC
                      </span>
                    )}
                  </div>

                  {/* Authorization Status Badge */}
                  <div className="absolute top-3 right-3">
                    {isAuthorized ? (
                      <span className="px-2 py-0.5 rounded-md bg-emerald-950/90 border border-emerald-500/40 text-emerald-400 text-[10px] font-bold flex items-center gap-1">
                        <ShieldCheck className="w-3 h-3" />
                        AUTHORIZED
                      </span>
                    ) : item.authorization_status === "REVOKED" ? (
                      <span className="px-2 py-0.5 rounded-md bg-rose-950/90 border border-rose-500/40 text-rose-400 text-[10px] font-bold flex items-center gap-1">
                        <ShieldAlert className="w-3 h-3" />
                        REVOKED
                      </span>
                    ) : (
                      <span className="px-2 py-0.5 rounded-md bg-amber-950/90 border border-amber-500/40 text-amber-400 text-[10px] font-bold flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        AWAITING AUTH
                      </span>
                    )}
                  </div>

                  {/* External Link */}
                  <a
                    href={item.stream_url}
                    target="_blank"
                    rel="noreferrer"
                    className="absolute bottom-2 right-2 p-1.5 rounded-lg bg-black/60 text-slate-300 hover:text-white hover:bg-black/90 transition-all text-xs flex items-center gap-1"
                    title="Open on YouTube"
                  >
                    <ExternalLink className="w-3.5 h-3.5" />
                  </a>
                </div>

                {/* Content Section */}
                <div className="p-5 space-y-3 flex-1 flex flex-col justify-between">
                  <div>
                    <h3 className="font-bold text-sm text-white line-clamp-2 leading-snug hover:text-[#38BDF8] transition-colors">
                      {item.title}
                    </h3>

                    <div className="flex items-center justify-between text-xs text-[#94A3B8] mt-2 font-medium">
                      <span className="text-white font-semibold truncate max-w-[180px]">
                        {item.channel_title}
                      </span>
                      <span className="font-mono text-[10px] text-slate-500">
                        {new Date(item.detected_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                      </span>
                    </div>
                  </div>

                  {/* Recording Status Bar */}
                  <div className="p-2.5 rounded-lg bg-[#0B1220] border border-[#172337] flex items-center justify-between text-xs">
                    <span className="text-[11px] text-[#94A3B8]">Pipeline Status</span>
                    <span
                      className={`font-mono text-[11px] font-bold ${
                        item.recording_status === "RECORDING"
                          ? "text-rose-400"
                          : item.recording_status === "CLIPPED"
                          ? "text-[#38BDF8]"
                          : item.recording_status === "RECORDED"
                          ? "text-blue-400"
                          : "text-slate-400"
                      }`}
                    >
                      {item.recording_status}
                    </span>
                  </div>

                  {/* Action Buttons */}
                  <div className="pt-2 border-t border-[#172337] flex items-center gap-2">
                    {/* If Awaiting Authorization */}
                    {!isAuthorized && (
                      <button
                        onClick={() => handleOpenAuthModal(item)}
                        className="w-full flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-400 text-xs font-bold hover:bg-amber-500/20 transition-all"
                      >
                        <KeyRound className="w-3.5 h-3.5" />
                        Authorize Creator
                      </button>
                    )}

                    {/* If Authorized and Idle -> Start OBS Recording */}
                    {isAuthorized && !isRecording && isLive && (
                      <button
                        onClick={() => handleStartRecording(item)}
                        disabled={actionLoadingId === item.id}
                        className="w-full flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg bg-rose-600 text-white text-xs font-bold shadow-md shadow-rose-900/30 hover:bg-rose-500 transition-all disabled:opacity-50"
                      >
                        <Play className="w-3.5 h-3.5 fill-current" />
                        {actionLoadingId === item.id ? "Connecting OBS..." : "Record with OBS"}
                      </button>
                    )}

                    {/* If Currently Recording -> Stop Recording */}
                    {isRecording && (
                      <button
                        onClick={() => handleStopRecording(item)}
                        disabled={actionLoadingId === item.id}
                        className="w-full flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg bg-rose-950 border border-rose-500 text-rose-300 text-xs font-bold hover:bg-rose-900 transition-all disabled:opacity-50 animate-pulse"
                      >
                        <Square className="w-3.5 h-3.5 fill-current" />
                        {actionLoadingId === item.id ? "Stopping..." : "Stop Recording"}
                      </button>
                    )}

                    {/* If Completed/Clipped */}
                    {(item.recording_status === "CLIPPED" || item.recording_status === "RECORDED") && (
                      <Link
                        href="/clips"
                        className="w-full flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg bg-[#38BDF8]/10 border border-[#38BDF8]/30 text-[#38BDF8] text-xs font-bold hover:bg-[#38BDF8]/20 transition-all text-center"
                      >
                        <Film className="w-3.5 h-3.5" />
                        View Highlight Clips
                      </Link>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Authorize Creator Modal */}
      {authModalDiscovery && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-lg rounded-2xl bg-[#111C2E] border border-[#172337] p-6 space-y-6 shadow-2xl">
            <div className="flex items-center justify-between border-b border-[#172337] pb-4">
              <div className="flex items-center gap-2.5">
                <ShieldCheck className="w-5 h-5 text-emerald-400" />
                <h2 className="text-base font-bold text-white">Authorize Creator Recording</h2>
              </div>
              <button
                onClick={() => setAuthModalDiscovery(null)}
                className="text-xs text-[#94A3B8] hover:text-white"
              >
                ✕
              </button>
            </div>

            <div className="space-y-4 text-xs">
              <div>
                <label className="text-[#94A3B8] block mb-1">Creator / Channel Name</label>
                <input
                  type="text"
                  disabled
                  value={authModalDiscovery.channel_title}
                  className="w-full p-2.5 rounded-lg bg-[#0B1220] border border-[#172337] text-white font-semibold"
                />
              </div>

              <div>
                <label className="text-[#94A3B8] block mb-1">YouTube Channel ID</label>
                <input
                  type="text"
                  disabled
                  value={authModalDiscovery.channel_id}
                  className="w-full p-2.5 rounded-lg bg-[#0B1220] border border-[#172337] text-slate-400 font-mono"
                />
              </div>

              <div>
                <label className="text-[#38BDF8] block mb-1 font-semibold">
                  Approved Video Input Source (Required for OBS)
                </label>
                <input
                  type="text"
                  value={authSource}
                  onChange={(e) => setAuthSource(e.target.value)}
                  placeholder="e.g. OBS:GameCapture_GTA6 or rtmp://127.0.0.1:1935/live/streamer"
                  className="w-full p-2.5 rounded-lg bg-[#0B1220] border border-[#38BDF8]/40 text-white font-mono focus:outline-none focus:border-[#38BDF8]"
                />
                <p className="text-[10px] text-[#94A3B8] mt-1">
                  OBS Scene, Window Capture title, or creator-provided RTMP/SRT ingestion feed.
                </p>
              </div>

              <div>
                <label className="text-[#94A3B8] block mb-1">Allowed Usage Scope</label>
                <select
                  value={authScope}
                  onChange={(e) => setAuthScope(e.target.value as any)}
                  className="w-full p-2.5 rounded-lg bg-[#0B1220] border border-[#172337] text-white"
                >
                  <option value="clip_creation">Clip Creation & Highlight Editing (Recommended)</option>
                  <option value="full_access">Full Access (Unrestricted)</option>
                </select>
              </div>

              <div>
                <label className="text-[#94A3B8] block mb-1">Verification / Consent Notes</label>
                <textarea
                  rows={2}
                  value={authNotes}
                  onChange={(e) => setAuthNotes(e.target.value)}
                  className="w-full p-2.5 rounded-lg bg-[#0B1220] border border-[#172337] text-white resize-none"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-4 border-t border-[#172337]">
              <button
                onClick={() => setAuthModalDiscovery(null)}
                className="px-4 py-2 rounded-lg text-xs font-semibold text-[#94A3B8] hover:text-white"
              >
                Cancel
              </button>
              <button
                onClick={handleSubmitAuthorization}
                disabled={submittingAuth || !authSource.trim()}
                className="px-5 py-2.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs shadow-lg shadow-emerald-500/20 disabled:opacity-50"
              >
                {submittingAuth ? "Authorizing..." : "Grant Active Authorization"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
