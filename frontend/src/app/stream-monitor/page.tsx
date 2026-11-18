"use client";

import { ChangeEvent, useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  Radio,
  Video,
  Play,
  Square,
  AlertCircle,
  RefreshCw,
  Plus,
  ShieldCheck,
  ShieldAlert,
  Compass,
  CircleDot,
  CheckCircle2,
  Film,
  Zap,
  Upload,
} from "lucide-react";
import {
  api,
  Streamer,
  LiveDiscovery,
  RecordingSession,
  OBSStatus,
} from "@/services/api";

export default function StreamMonitorPage() {
  const [streamers, setStreamers] = useState<Streamer[]>([]);
  const [discoveries, setDiscoveries] = useState<LiveDiscovery[]>([]);
  const [activeSession, setActiveSession] = useState<RecordingSession | null>(null);
  const [obsStatus, setOBSStatus] = useState<OBSStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [polling, setPolling] = useState(false);
  const [actionLoadingId, setActionLoadingId] = useState<string | null>(null);
  const [uploadingStreamerId, setUploadingStreamerId] = useState<number | null>(null);
  const [selectedStreamer, setSelectedStreamer] = useState<Streamer | null>(null);
  const [notice, setNotice] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const showNotice = (type: "success" | "error", text: string) => {
    setNotice({ type, text });
    setTimeout(() => setNotice(null), 5000);
  };

  const loadAll = async () => {
    try {
      const [stRes, discRes, sessRes, obsRes] = await Promise.all([
        api.getStreamers().catch(() => ({ items: [] })),
        api.getDiscoveries({ live_status: "live", limit: 6 }).catch(() => ({ items: [] })),
        api.getRecordingSessions({ status: "recording" }).catch(() => ({ items: [] })),
        api.getOBSStatus().catch(() => null),
      ]);
      setStreamers(stRes.items);
      setDiscoveries(discRes.items);
      setActiveSession(sessRes.items && sessRes.items.length > 0 ? sessRes.items[0] : null);
      if (obsRes) setOBSStatus(obsRes);
    } catch (e: any) {
      showNotice("error", e.message || "Failed to update monitor.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAll();
    const interval = setInterval(loadAll, 6000);
    return () => clearInterval(interval);
  }, []);

  const handlePoll = async () => {
    setPolling(true);
    try {
      const result = await api.pollYouTube();
      if (result.status === "skipped") {
        showNotice("error", result.message || "YouTube polling was skipped. Check your API key configuration.");
      } else {
        showNotice(
          "success",
          `Poll completed: checked ${result.streamers_checked} streamer(s), detected ${result.live_streams_detected} new live stream(s).`
        );
      }
      await loadAll();
    } catch (err) {
      showNotice("error", err instanceof Error ? err.message : "YouTube polling failed.");
    } finally {
      setPolling(false);
    }
  };

  const handleStartRecording = async (channelId: string, videoId?: string) => {
    try {
      setActionLoadingId(channelId);
      await api.startOBSRecording({
        channel_id: channelId,
        video_id: videoId,
      });
      showNotice("success", `OBS recording started for channel '${channelId}'!`);
      loadAll();
    } catch (e: any) {
      showNotice("error", e.message || "Failed to start recording.");
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleStopRecording = async () => {
    try {
      setActionLoadingId("stop");
      const res = await api.stopOBSRecording();
      showNotice("success", res.message || "Recording stopped.");
      loadAll();
    } catch (e: any) {
      showNotice("error", e.message || "Failed to stop recording.");
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleIntakeClick = (streamer: Streamer) => {
    setSelectedStreamer(streamer);
    fileInputRef.current?.click();
  };

  const handleFileSelected = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    const streamer = selectedStreamer;
    event.target.value = "";
    if (!file || !streamer) return;

    setUploadingStreamerId(streamer.id);
    try {
      const recording = await api.uploadRecording(streamer.id, file);
      showNotice(
        "success",
        `Recording "${recording.file_name}" successfully ingested for ${streamer.display_name} (Recording #${recording.id}).`
      );
      loadAll();
    } catch (err) {
      showNotice("error", err instanceof Error ? err.message : "Recording upload failed.");
    } finally {
      setUploadingStreamerId(null);
      setSelectedStreamer(null);
    }
  };

  return (
    <div className="space-y-8 max-w-7xl mx-auto p-8 bg-[#0B1220] min-h-screen text-[#E5E7EB]">
      <input
        ref={fileInputRef}
        type="file"
        accept="video/*,.mp4,.mkv,.mov,.webm"
        className="hidden"
        onChange={handleFileSelected}
      />

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
            <div className="p-2.5 rounded-xl bg-[#38BDF8]/10 text-[#38BDF8] border border-[#38BDF8]/20">
              <Radio className="w-6 h-6 animate-pulse" />
            </div>
            <div>
              <h1 className="text-2xl font-black tracking-tight text-white">Stream Ingestion & Radar</h1>
              <p className="text-xs text-[#94A3B8] mt-0.5">
                Multi-stage pipeline: Discovery → Creator Authorization → OBS Recording → AI Highlights
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handlePoll}
            disabled={polling || loading}
            className="px-3.5 py-2 rounded-xl bg-[#172337] border border-[#172337] hover:bg-[#1f2f4a] disabled:opacity-50 text-xs font-bold text-white flex items-center gap-2 transition-all"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${polling ? "animate-spin" : ""}`} />
            <span>{polling ? "Polling..." : "Poll Streams"}</span>
          </button>

          <Link
            href="/discoveries"
            className="px-4 py-2.5 rounded-xl bg-[#172337] border border-[#172337] hover:bg-[#1f2f4a] text-xs font-bold text-white flex items-center gap-2 transition-all"
          >
            <Compass className="w-4 h-4 text-[#38BDF8]" />
            Live Discoveries
          </Link>
          <Link
            href="/obs"
            className="px-4 py-2.5 rounded-xl bg-[#172337] border border-[#172337] hover:bg-[#1f2f4a] text-xs font-bold text-white flex items-center gap-2 transition-all"
          >
            <Video className="w-4 h-4 text-rose-400" />
            OBS Console
          </Link>
        </div>
      </div>

      {/* Multi-Stage Visual Pipeline Radar */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* Stage 1: Public Discovery */}
        <div className="p-5 rounded-2xl bg-[#111C2E] border border-[#172337] relative overflow-hidden">
          <div className="flex items-center justify-between text-xs font-mono text-[#94A3B8] mb-2">
            <span>STAGE 01</span>
            <Compass className="w-4 h-4 text-[#38BDF8]" />
          </div>
          <div className="text-sm font-bold text-white">Public Discovery</div>
          <p className="text-xs text-[#94A3B8] mt-1">Official YouTube API metadata discovery. Zero download.</p>
          <div className="mt-4 pt-3 border-t border-[#172337] flex items-center justify-between">
            <span className="text-xs font-bold text-[#38BDF8]">{discoveries.length} Live Found</span>
            <Link href="/discoveries" className="text-[11px] text-[#94A3B8] hover:text-white underline">
              View All →
            </Link>
          </div>
        </div>

        {/* Stage 2: Authorization Gate */}
        <div className="p-5 rounded-2xl bg-[#111C2E] border border-[#172337] relative overflow-hidden">
          <div className="flex items-center justify-between text-xs font-mono text-[#94A3B8] mb-2">
            <span>STAGE 02</span>
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-sm font-bold text-white">Creator Consent Gate</div>
          <p className="text-xs text-[#94A3B8] mt-1">
            Enforces explicit creator authorization & approved feed before intake.
          </p>
          <div className="mt-4 pt-3 border-t border-[#172337] flex items-center justify-between">
            <span className="text-xs font-bold text-emerald-400">Strict Permission</span>
            <Link href="/authorizations" className="text-[11px] text-[#94A3B8] hover:text-white underline">
              Authorizations →
            </Link>
          </div>
        </div>

        {/* Stage 3: OBS Recording Pipeline */}
        <div
          className={`p-5 rounded-2xl border relative overflow-hidden ${
            activeSession ? "bg-rose-950/20 border-rose-500/40" : "bg-[#111C2E] border-[#172337]"
          }`}
        >
          <div className="flex items-center justify-between text-xs font-mono text-[#94A3B8] mb-2">
            <span>STAGE 03</span>
            <Video className={`w-4 h-4 ${activeSession ? "text-rose-400 animate-pulse" : "text-slate-400"}`} />
          </div>
          <div className="text-sm font-bold text-white">OBS Ingestion Feed</div>
          <p className="text-xs text-[#94A3B8] mt-1">Authorized window/RTMP feed recorded via OBS WebSocket.</p>
          <div className="mt-4 pt-3 border-t border-[#172337] flex items-center justify-between">
            <span className="text-xs font-bold text-white">
              {activeSession ? (
                <span className="text-rose-400 flex items-center gap-1.5">
                  <CircleDot className="w-3.5 h-3.5 animate-ping" />
                  Recording Now
                </span>
              ) : obsStatus?.connected ? (
                <span className="text-emerald-400">OBS Standby</span>
              ) : (
                <span className="text-slate-500">OBS Offline</span>
              )}
            </span>
            <Link href="/obs" className="text-[11px] text-[#94A3B8] hover:text-white underline">
              Control →
            </Link>
          </div>
        </div>

        {/* Stage 4: AI Highlights */}
        <div className="p-5 rounded-2xl bg-[#111C2E] border border-[#172337] relative overflow-hidden">
          <div className="flex items-center justify-between text-xs font-mono text-[#94A3B8] mb-2">
            <span>STAGE 04</span>
            <Zap className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-sm font-bold text-white">AI Highlight Engine</div>
          <p className="text-xs text-[#94A3B8] mt-1">Multi-modal audio/visual scoring & 9:16 vertical render.</p>
          <div className="mt-4 pt-3 border-t border-[#172337] flex items-center justify-between">
            <span className="text-xs font-bold text-amber-400">Automated Pipeline</span>
            <Link href="/clips" className="text-[11px] text-[#94A3B8] hover:text-white underline">
              Clips Library →
            </Link>
          </div>
        </div>
      </div>

      {/* Live Recording Console (if active session) */}
      {activeSession && (
        <div className="p-6 rounded-2xl bg-[#111C2E] border-2 border-rose-500/50 shadow-2xl space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <span className="relative flex h-3.5 w-3.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-3.5 w-3.5 bg-rose-500"></span>
              </span>
              <div>
                <div className="text-sm font-bold text-white flex items-center gap-2">
                  Active Recording Session: {activeSession.channel_id}
                </div>
                <div className="text-xs text-[#94A3B8] font-mono mt-0.5">
                  Input: {activeSession.source_input} | Started:{" "}
                  {new Date(activeSession.started_at).toLocaleTimeString()}
                </div>
              </div>
            </div>

            <button
              onClick={handleStopRecording}
              disabled={actionLoadingId === "stop"}
              className="px-5 py-2.5 rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-bold text-xs flex items-center gap-2 shadow-lg shadow-rose-950 transition-all disabled:opacity-50"
            >
              <Square className="w-4 h-4 fill-current" />
              Stop & Trigger AI Clipping
            </button>
          </div>
        </div>
      )}

      {/* Discovered Livestreams Live Radar */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-bold text-white flex items-center gap-2">
            <Radio className="w-5 h-5 text-[#38BDF8]" />
            Live GTA 6 Broadcasts on YouTube Radar
          </h2>
          <Link href="/discoveries" className="text-xs text-[#38BDF8] hover:underline font-mono">
            DISCOVERY DASHBOARD →
          </Link>
        </div>

        {discoveries.length === 0 ? (
          <div className="p-8 rounded-2xl bg-[#111C2E] border border-[#172337] text-center space-y-3">
            <Compass className="w-8 h-8 text-slate-500 mx-auto" />
            <p className="text-sm text-[#94A3B8]">No active GTA 6 livestreams detected on radar.</p>
            <Link
              href="/discoveries"
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-[#172337] text-xs font-bold text-white hover:bg-[#1f2f4a]"
            >
              <RefreshCw className="w-3.5 h-3.5 text-[#38BDF8]" />
              Trigger Live Discovery Scan
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {discoveries.map((d) => {
              const isAuthorized = d.authorization_status === "AUTHORIZED";
              const isRecording = d.recording_status === "RECORDING";
              return (
                <div
                  key={d.id}
                  className="rounded-2xl bg-[#111C2E] border border-[#172337] overflow-hidden flex flex-col justify-between hover:border-slate-700 transition-all"
                >
                  <div>
                    <div className="relative aspect-video bg-black/60">
                      {d.thumbnail_url ? (
                        <img
                          src={d.thumbnail_url}
                          alt={d.title}
                          className="w-full h-full object-cover"
                        />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center text-slate-600">
                          <Video className="w-8 h-8" />
                        </div>
                      )}
                      <span className="absolute top-2 left-2 px-2 py-0.5 rounded bg-rose-600 text-white font-black text-[10px] tracking-wider uppercase flex items-center gap-1 shadow-lg">
                        <CircleDot className="w-2.5 h-2.5 fill-current animate-ping" />
                        LIVE
                      </span>
                    </div>

                    <div className="p-4 space-y-2">
                      <div className="font-bold text-sm text-white line-clamp-2 leading-snug">{d.title}</div>
                      <div className="text-xs text-[#94A3B8] font-medium">{d.channel_title}</div>
                    </div>
                  </div>

                  <div className="p-4 pt-0 border-t border-[#172337] mt-3 flex items-center justify-between text-xs">
                    <div>
                      {isAuthorized ? (
                        <span className="text-emerald-400 font-bold flex items-center gap-1 text-[11px]">
                          <ShieldCheck className="w-3.5 h-3.5" />
                          Authorized
                        </span>
                      ) : (
                        <span className="text-amber-400 font-medium flex items-center gap-1 text-[11px]">
                          <ShieldAlert className="w-3.5 h-3.5" />
                          Needs Consent
                        </span>
                      )}
                    </div>

                    <div>
                      {isRecording ? (
                        <span className="px-3 py-1 rounded-lg bg-rose-950/80 text-rose-400 border border-rose-500/30 text-xs font-bold font-mono">
                          RECORDING
                        </span>
                      ) : isAuthorized ? (
                        <button
                          onClick={() => handleStartRecording(d.channel_id, d.video_id)}
                          disabled={actionLoadingId === d.channel_id || activeSession !== null}
                          className="px-3 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-white font-bold text-xs flex items-center gap-1.5 transition-all disabled:opacity-50"
                        >
                          <Play className="w-3 h-3 fill-current" />
                          Record Feed
                        </button>
                      ) : (
                        <Link
                          href={`/authorizations?channel_id=${d.channel_id}&name=${encodeURIComponent(
                            d.channel_title
                          )}`}
                          className="px-3 py-1.5 rounded-lg bg-[#172337] hover:bg-[#1f2f4a] text-[#38BDF8] font-bold text-xs flex items-center gap-1 transition-all"
                        >
                          <Plus className="w-3 h-3" />
                          Authorize
                        </Link>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Streamers Roster & Manual Intake Section */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-bold text-white flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-emerald-400" />
            Registered Streamers Roster
          </h2>
          <Link href="/streamers" className="text-xs text-[#38BDF8] hover:underline font-mono">
            MANAGE ROSTER →
          </Link>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {streamers.map((s) => {
            const permitted = s.permission_status === "ACTIVE";
            const uploading = uploadingStreamerId === s.id;
            return (
              <div key={s.id} className="p-5 rounded-xl bg-[#111C2E] border border-[#172337] space-y-4 flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="font-bold text-sm text-white">{s.display_name}</div>
                      <div className="text-xs font-mono text-slate-400 truncate max-w-[180px] mt-0.5">
                        {s.channel_id || "Direct File Intake"}
                      </div>
                    </div>
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold font-mono ${
                        permitted
                          ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                          : "bg-amber-500/20 text-amber-400 border border-amber-500/30"
                      }`}
                    >
                      {permitted ? "PERMITTED" : "NO PERMIT"}
                    </span>
                  </div>
                </div>

                <div className="pt-3 border-t border-[#172337] flex items-center justify-between text-xs gap-2">
                  <button
                    type="button"
                    disabled={!permitted || uploading}
                    onClick={() => handleIntakeClick(s)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 ${
                      permitted
                        ? "bg-[#172337] hover:bg-[#1f2f4a] text-[#38BDF8] border border-[#38BDF8]/30"
                        : "bg-[#172337] text-slate-500 cursor-not-allowed border border-transparent"
                    }`}
                  >
                    <Upload className="w-3.5 h-3.5" />
                    {uploading ? "Uploading..." : "Intake File"}
                  </button>

                  {s.channel_id && permitted && (
                    <button
                      onClick={() => handleStartRecording(s.channel_id!)}
                      disabled={actionLoadingId === s.channel_id || activeSession !== null}
                      className="px-3 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-white font-bold text-xs flex items-center gap-1.5 transition-all disabled:opacity-50"
                    >
                      <Play className="w-3 h-3 fill-current" />
                      Record Feed
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
