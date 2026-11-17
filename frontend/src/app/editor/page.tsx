"use client";

import { useState } from "react";
import { Video, Sliders, Type, Download, Play, RefreshCw } from "lucide-react";

export default function ClipEditorPage() {
  const [preset, setPreset] = useState("Viral Gaming");
  const [title, setTitle] = useState("INSANE 5-STAR CHASE IN VICE CITY!");
  const [subtitleColor, setSubtitleColor] = useState("#00f0ff");

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div>
        <h1 className="text-2xl font-extrabold text-text-primary tracking-tight">
          Clip Fine-Tuning Studio
        </h1>
        <p className="text-xs text-text-secondary mt-1">
          Adjust clip boundaries, switch editing presets, and re-generate dynamic subtitles with live preview.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Preview Viewport */}
        <div className="lg:col-span-1 bg-surface border border-border rounded-xl p-4 flex flex-col items-center">
          <div className="aspect-[9/16] w-full max-w-[280px] bg-slate-950 rounded-lg overflow-hidden relative border border-border flex items-center justify-center">
            <div className="text-center p-4">
              <Play className="w-10 h-10 text-accent-cyan mx-auto mb-2 opacity-80" />
              <div className="text-xs font-bold text-text-primary">1080x1920 9:16 Canvas</div>
              <div className="text-[10px] text-text-muted mt-1 font-mono">{preset}</div>
            </div>

            {/* Subtitle simulation overlay */}
            <div className="absolute bottom-12 inset-x-4 text-center">
              <span
                className="px-2 py-1 rounded font-black text-xs uppercase tracking-wider bg-slate-950/80 border border-slate-800"
                style={{ color: subtitleColor }}
              >
                LOOK AT THE COPS!
              </span>
            </div>
          </div>
        </div>

        {/* Controls */}
        <div className="lg:col-span-2 space-y-4">
          <div className="p-6 bg-surface border border-border rounded-xl space-y-4">
            <h3 className="text-sm font-bold text-text-primary uppercase tracking-wide">
              Editing Preset & Layout
            </h3>
            <div className="grid grid-cols-3 gap-3">
              {["Viral Gaming", "Clean Gameplay", "Reaction Focus"].map((p) => (
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
            </div>

            <div className="pt-4 border-t border-border space-y-3">
              <label className="block text-xs font-medium text-text-secondary">
                Subtitle Highlight Color
              </label>
              <div className="flex items-center gap-3">
                {["#00f0ff", "#f59e0b", "#10b981", "#f43f5e", "#ffffff"].map((color) => (
                  <button
                    key={color}
                    onClick={() => setSubtitleColor(color)}
                    className="w-8 h-8 rounded-full border border-border transition-transform hover:scale-110"
                    style={{ backgroundColor: color }}
                  />
                ))}
              </div>
            </div>

            <div className="pt-6 border-t border-border flex justify-end gap-3">
              <button className="px-4 py-2 rounded-lg bg-surface-elevated hover:bg-surface-hover text-xs font-semibold text-text-secondary">
                Reset to AI Defaults
              </button>
              <button className="px-5 py-2 rounded-lg bg-accent-cyan hover:bg-accent-cyan-bright text-slate-950 text-xs font-bold transition-all glow-cyan flex items-center gap-2">
                <RefreshCw className="w-4 h-4" />
                <span>Re-Render Clip (FFmpeg NVENC)</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
