"use client";

import { ChangeEvent, useEffect, useRef, useState } from "react";
import { Radio, RefreshCw, Upload } from "lucide-react";
import { api, Streamer } from "@/services/api";

export default function StreamMonitorPage() {
  const [streamers, setStreamers] = useState<Streamer[]>([]);
  const [loading, setLoading] = useState(true);
  const [polling, setPolling] = useState(false);
  const [uploadingStreamerId, setUploadingStreamerId] = useState<number | null>(null);
  const [selectedStreamer, setSelectedStreamer] = useState<Streamer | null>(null);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadData = async () => {
    setLoading(true);
    try {
      const res = await api.getStreamers();
      setStreamers(res.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load streamers.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadData();
  }, []);

  const handlePoll = async () => {
    setPolling(true);
    setNotice("");
    setError("");
    try {
      const result = await api.pollYouTube();
      if (result.status === "skipped") {
        setNotice(result.message || "YouTube polling was skipped. Check your API key configuration.");
      } else {
        setNotice(
          `Poll completed: checked ${result.streamers_checked} streamer(s), detected ${result.live_streams_detected} new live stream(s).`
        );
      }
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "YouTube polling failed.");
    } finally {
      setPolling(false);
    }
  };

  const handleIntakeClick = (streamer: Streamer) => {
    setSelectedStreamer(streamer);
    setError("");
    setNotice("");
    fileInputRef.current?.click();
  };

  const handleFileSelected = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    const streamer = selectedStreamer;
    event.target.value = "";
    if (!file || !streamer) return;

    setUploadingStreamerId(streamer.id);
    setNotice("");
    setError("");
    try {
      const recording = await api.uploadRecording(streamer.id, file);
      setNotice(
        `Recording "${recording.file_name}" successfully ingested for ${streamer.display_name} (Recording #${recording.id}).`
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Recording upload failed.");
    } finally {
      setUploadingStreamerId(null);
      setSelectedStreamer(null);
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <input
        ref={fileInputRef}
        type="file"
        accept="video/*,.mp4,.mkv,.mov,.webm"
        className="hidden"
        onChange={handleFileSelected}
      />

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-extrabold text-text-primary tracking-tight">
            Stream Monitor
          </h1>
          <p className="text-xs text-text-secondary mt-1">
            Live broadcast detection and authorized media intake for registered GTA 6 creators.
          </p>
        </div>
        <button
          onClick={handlePoll}
          disabled={polling || loading}
          className="px-3.5 py-2 rounded-lg bg-surface border border-border hover:bg-surface-elevated disabled:opacity-50 text-xs font-semibold text-text-primary flex items-center gap-2"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${polling ? "animate-spin" : ""}`} />
          <span>{polling ? "Polling..." : "Poll Now"}</span>
        </button>
      </div>

      {notice && (
        <div role="status" className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-300">
          {notice}
        </div>
      )}
      {error && (
        <div role="alert" className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {loading ? (
        <p className="text-sm text-text-secondary">Loading registered streamers...</p>
      ) : streamers.length === 0 ? (
        <p className="text-sm text-text-secondary">No streamers registered yet.</p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {streamers.map((s) => {
            const permitted = s.permission_status === "ACTIVE";
            const uploading = uploadingStreamerId === s.id;
            return (
              <div
                key={s.id}
                className="p-5 rounded-xl bg-surface border border-border flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-bold text-text-primary">{s.display_name}</span>
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                        permitted
                          ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30"
                          : "bg-amber-500/10 text-amber-400 border border-amber-500/30"
                      }`}
                    >
                      {permitted ? "PERMITTED" : "NO PERMIT"}
                    </span>
                  </div>
                  <div className="text-xs text-text-muted mt-1 font-mono">
                    {s.channel_id || "Direct Capture / Local File"}
                  </div>
                </div>

                <div className="mt-6 pt-4 border-t border-border flex items-center justify-between">
                  <span className="text-[11px] text-text-muted flex items-center gap-1.5">
                    <Radio className="w-3.5 h-3.5 text-text-muted" />
                    <span>Live status checked by Poll Now</span>
                  </span>
                  <button
                    type="button"
                    disabled={!permitted || uploading}
                    onClick={() => handleIntakeClick(s)}
                    className={`px-3 py-1.5 rounded text-xs font-bold transition-all flex items-center gap-1.5 ${
                      permitted
                        ? "bg-accent-cyan hover:bg-accent-cyan-bright text-slate-950"
                        : "bg-surface-elevated text-text-muted cursor-not-allowed"
                    }`}
                  >
                    <Upload className="w-3.5 h-3.5" />
                    {uploading ? "Uploading..." : "Intake Recording"}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
      <p className="text-xs text-text-muted">
        Intake uploads a video file you select. YouTube polling detects public live broadcasts only; it does not download or record the livestream.
      </p>
    </div>
  );
}
