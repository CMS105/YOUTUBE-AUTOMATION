"use client";

import { useEffect, useState } from "react";
import { Video, Sliders, Type, Download, Play, RefreshCw, CheckCircle2, Sparkles } from "lucide-react";
import { api, ClipCandidate } from "@/services/api";

export default function ClipEditorPage() {
  const [candidates, setCandidates] = useState<ClipCandidate[]>([]);
  const [selectedCandidate, setSelectedCandidate] = useState<ClipCandidate | null>(null);
  const [preset, setPreset] = useState<"Viral Gaming" | "Clean Gameplay" | "Reaction Focus">("Viral Gaming");
  const [title, setTitle] = useState("INSANE 5-STAR CHASE IN VICE CITY!");
  const [subtitleColor, setSubtitleColor] = useState("#00f0ff");
  const [rendering, setRendering] = useState(false);
  const [renderedClipUrl, setRenderedClipUrl] = useState<string | null>(null);
  const [renderMessage, setRenderMessage] = useState<string | null>(null);

  useEffect(() => {
    api.getCandidates(undefined, "pending").then((res) => {
      setCandidates(res.items || []);
      if (res.items && res.items.length > 0) {
        const first = res.items[0];
        setSelectedCandidate(first);
        if (first.suggested_titles && first.suggested_titles.length > 0) {
          setTitle(first.suggested_titles[0]);
        }
      }
    }).catch(console.error);
  }, []);

  const handleSelectCandidate = (cand: ClipCandidate) => {
    setSelectedCandidate(cand);
    if (cand.suggested_titles && cand.suggested_titles.length > 0) {
      setTitle(cand.suggested_titles[0]);
    }
  };

  const handleRender = async () => {
    if (!selectedCandidate) return;
    setRendering(true);
    setRenderMessage(null);
    try {
      const clip = await api.renderCandidate(selectedCandidate.id, preset, title);
      setRenderMessage(`Successfully rendered: ${clip.title}`);
      setRenderedClipUrl(`http://127.0.0.1:8000/api/v1/clips/${clip.id}/download`);
    } catch (err: any) {
      setRenderMessage(`Render error: ${err.message}`);
    } finally {
      setRendering(false);
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div>
        <h1 className="text-2xl font-extrabold text-text-primary tracking-tight">
          Clip Fine-Tuning Studio
        </h1>
        <p className="text-xs text-text-secondary mt-1">
          Adjust clip boundaries, switch editing presets, and render vertical MP4s with live preview.
        </p>
      </div>

      {/* Candidate Selector Bar */}
      {candidates.length > 0 && (
        <div className="p-4 rounded-xl bg-surface border border-border">
          <div className="text-xs font-bold text-text-secondary uppercase tracking-wider mb-2 flex items-center gap-2">
            <Sparkles className="w-3.5 h-3.5 text-accent-cyan" />
            <span>Select AI Highlight Candidate</span>
          </div>
          <div className="flex gap-2 overflow-x-auto pb-1">
            {candidates.map((c) => (
              <button
                key={c.id}
                onClick={() => handleSelectCandidate(c)}
                className={`px-3 py-2 rounded-lg text-xs font-semibold whitespace-nowrap transition-all border ${
                  selectedCandidate?.id === c.id
                    ? "bg-accent-cyan/15 border-accent-cyan text-accent-cyan glow-cyan"
                    : "bg-surface-elevated border-border text-text-secondary hover:text-text-primary"
                }`}
              >
                #{c.rank || c.id} • {c.event_category} ({c.duration.toFixed(0)}s) • Score: {(c.score_composite * 100).toFixed(0)}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Preview Viewport */}
        <div className="lg:col-span-1 bg-surface border border-border rounded-xl p-4 flex flex-col items-center">
          <div className="aspect-[9/16] w-full max-w-[280px] bg-slate-950 rounded-lg overflow-hidden relative border border-border flex items-center justify-center">
            {/* Background simulation based on preset */}
            {preset === "Clean Gameplay" && (
              <div className="absolute inset-0 bg-gradient-to-b from-slate-900 via-slate-800 to-slate-900 opacity-60" />
            )}

            {/* Video content placeholder */}
            <div className="text-center p-4 relative z-10">
              <Play className="w-10 h-10 text-accent-cyan mx-auto mb-2 opacity-80" />
              <div className="text-xs font-bold text-text-primary">1080x1920 9:16 Canvas</div>
              <div className="text-[10px] text-accent-cyan mt-1 font-mono uppercase">{preset}</div>
              {selectedCandidate && (
                <div className="text-[9px] text-text-muted mt-2">
                  Window: {selectedCandidate.start_time.toFixed(1)}s - {selectedCandidate.end_time.toFixed(1)}s
                </div>
              )}
            </div>

            {/* Simulated Facecam Badge for Viral Gaming */}
            {preset === "Viral Gaming" && selectedCandidate?.has_facecam && (
              <div className="absolute top-4 right-4 w-20 h-14 bg-slate-800 border-2 border-accent-cyan rounded flex items-center justify-center text-[8px] font-bold text-accent-cyan">
                FACECAM
              </div>
            )}

            {/* Subtitle simulation overlay */}
            <div className="absolute bottom-12 inset-x-4 text-center z-10">
              <span
                className="px-2.5 py-1.5 rounded font-black text-xs uppercase tracking-wider bg-slate-950/90 border border-slate-800 shadow-lg"
                style={{ color: subtitleColor }}
              >
                BRO OUTSMARTED THE COPS! 💀
              </span>
            </div>
          </div>
        </div>

        {/* Controls */}
        <div className="lg:col-span-2 space-y-4">
          <div className="p-6 bg-surface border border-border rounded-xl space-y-4">
            <h3 className="text-sm font-bold text-text-primary uppercase tracking-wide">
              Editing Preset & Framing
            </h3>
            <div className="grid grid-cols-3 gap-3">
              {(["Viral Gaming", "Clean Gameplay", "Reaction Focus"] as const).map((p) => (
                <button
                  key={p}
                  onClick={() => setPreset(p)}
                  className={`p-3 rounded-lg border text-xs font-semibold transition-all ${
                    preset === p
                      ? "bg-accent-cyan/10 border-accent-cyan text-accent-cyan glow-cyan"
                      : "bg-surface-elevated border-border text-text-secondary hover:text-text-primary"
                  }`}
                >
                  {p}
                </button>
              ))}
            </div>

            <div className="pt-4 border-t border-border space-y-3">
              <label className="block text-xs font-medium text-text-secondary">Hook Title</label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="w-full px-3.5 py-2.5 rounded-lg bg-surface-elevated border border-border text-xs text-text-primary focus:outline-none focus:border-accent-cyan"
              />
              {selectedCandidate?.suggested_titles && (
                <div className="flex flex-wrap gap-1.5 mt-2">
                  {selectedCandidate.suggested_titles.map((t, idx) => (
                    <button
                      key={idx}
                      onClick={() => setTitle(t)}
                      className="text-[10px] px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-text-muted hover:text-text-primary border border-border transition-colors"
                    >
                      {t}
                    </button>
                  ))}
                </div>
              )}
            </div>

            <div className="pt-4 border-t border-border space-y-3">
              <label className="block text-xs font-medium text-text-secondary">
                Subtitle Highlight Color
              </label>
              <div className="flex items-center gap-3">
                {["#00f0ff", "#ffeb3b", "#10b981", "#f43f5e", "#ffffff"].map((color) => (
                  <button
                    key={color}
                    onClick={() => setSubtitleColor(color)}
                    className={`w-8 h-8 rounded-full border transition-transform hover:scale-110 ${
                      subtitleColor === color ? "ring-2 ring-accent-cyan ring-offset-2 ring-offset-slate-900" : "border-border"
                    }`}
                    style={{ backgroundColor: color }}
                  />
                ))}
              </div>
            </div>

            {renderMessage && (
              <div className={`p-3 rounded-lg text-xs font-semibold ${
                renderMessage.includes("error") ? "bg-rose-500/10 text-rose-400 border border-rose-500/30" : "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30"
              }`}>
                {renderMessage}
              </div>
            )}

            <div className="pt-6 border-t border-border flex justify-end gap-3 items-center">
              {renderedClipUrl && (
                <a
                  href={renderedClipUrl}
                  download
                  className="px-4 py-2 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 text-xs font-bold transition-all flex items-center gap-2"
                >
                  <Download className="w-4 h-4" />
                  <span>Download MP4</span>
                </a>
              )}
              <button
                disabled={rendering || !selectedCandidate}
                onClick={handleRender}
                className="px-5 py-2.5 rounded-lg bg-accent-cyan hover:bg-accent-cyan-bright disabled:opacity-50 text-slate-950 text-xs font-bold transition-all glow-cyan flex items-center gap-2"
              >
                <RefreshCw className={`w-4 h-4 ${rendering ? "animate-spin" : ""}`} />
                <span>{rendering ? "Rendering Vertical Clip..." : "Render Clip (FFmpeg / PyAV)"}</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
