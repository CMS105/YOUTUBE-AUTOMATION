"use client";

import { useEffect, useState } from "react";
import { Film, Play, Download, Heart, Trash2, Search, SlidersHorizontal } from "lucide-react";
import { api, Clip } from "@/services/api";

export default function ClipLibraryPage() {
  const [clips, setClips] = useState<Clip[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [selectedPreset, setSelectedPreset] = useState<string>("");
  const [previewClip, setPreviewClip] = useState<Clip | null>(null);

  const loadData = () => {
    setLoading(true);
    api.getClips(0, 50, search || undefined, selectedPreset || undefined).then((res) => {
      setClips(res.items);
      setLoading(false);
    }).catch(() => setLoading(false));
  };

  useEffect(() => {
    loadData();
  }, [selectedPreset]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    loadData();
  };

  const toggleFavorite = async (clip: Clip) => {
    await api.updateClip(clip.id, { is_favorite: !clip.is_favorite });
    loadData();
  };

  const handleDelete = async (id: number) => {
    if (confirm("Delete this finished clip?")) {
      await api.deleteClip(id);
      loadData();
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold text-text-primary tracking-tight">
            Clip Library
          </h1>
          <p className="text-xs text-text-secondary mt-1">
            Browse, preview, and download finalized 1080x1920 vertical MP4 clips.
          </p>
        </div>

        {/* Filter Controls */}
        <div className="flex items-center gap-3">
          <form onSubmit={handleSearchSubmit} className="relative">
            <Search className="w-3.5 h-3.5 text-text-muted absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search clip titles..."
              className="pl-8 pr-4 py-2 rounded-lg bg-surface border border-border text-xs text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent-cyan w-48 md:w-64"
            />
          </form>

          <select
            value={selectedPreset}
            onChange={(e) => setSelectedPreset(e.target.value)}
            className="px-3 py-2 rounded-lg bg-surface border border-border text-xs text-text-secondary focus:outline-none focus:border-accent-cyan"
          >
            <option value="">All Presets</option>
            <option value="Viral Gaming">Viral Gaming</option>
            <option value="Clean Gameplay">Clean Gameplay</option>
            <option value="Reaction Focus">Reaction Focus</option>
          </select>
        </div>
      </div>

      {/* Grid */}
      {clips.length === 0 ? (
        <div className="p-16 text-center rounded-xl bg-surface border border-border">
          <Film className="w-10 h-10 text-text-muted mx-auto mb-3 opacity-40" />
          <div className="text-sm font-bold text-text-primary">No Clips Found</div>
          <p className="text-xs text-text-muted mt-1">
            Render clips through the Processing Queue to view them here.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {clips.map((c) => (
            <div
              key={c.id}
              className="rounded-xl overflow-hidden bg-surface border border-border hover:border-accent-cyan/50 transition-all flex flex-col justify-between group"
            >
              {/* Media Card Top */}
              <div
                onClick={() => setPreviewClip(c)}
                className="aspect-[9/16] bg-slate-900 relative cursor-pointer overflow-hidden flex items-center justify-center"
              >
                <div className="w-12 h-12 rounded-full bg-accent-cyan/20 flex items-center justify-center text-accent-cyan group-hover:scale-110 transition-transform">
                  <Play className="w-5 h-5 fill-current" />
                </div>
                <div className="absolute top-3 right-3 px-2 py-0.5 rounded-full text-[10px] font-bold bg-slate-950/80 text-accent-cyan border border-accent-cyan/30">
                  {c.score.toFixed(1)}
                </div>
                <div className="absolute bottom-3 left-3 px-2 py-0.5 rounded text-[10px] font-mono bg-slate-950/80 text-text-muted">
                  {c.duration_seconds.toFixed(0)}s
                </div>
              </div>

              {/* Media Card Details */}
              <div className="p-4 space-y-2">
                <div className="text-xs font-bold text-text-primary truncate" title={c.title}>
                  {c.title}
                </div>
                <div className="flex items-center justify-between text-[11px] text-text-muted">
                  <span className="capitalize">{c.preset}</span>
                  <span>{new Date(c.rendered_at).toLocaleDateString()}</span>
                </div>

                <div className="pt-2 border-t border-border flex items-center justify-between">
                  <button
                    onClick={() => toggleFavorite(c)}
                    className={`p-1.5 rounded hover:bg-surface-elevated transition-colors ${
                      c.is_favorite ? "text-rose-400" : "text-text-muted"
                    }`}
                  >
                    <Heart className={`w-4 h-4 ${c.is_favorite ? "fill-current" : ""}`} />
                  </button>

                  <div className="flex items-center gap-1">
                    <a
                      href={`http://127.0.0.1:8000/api/v1/clips/${c.id}/download`}
                      download
                      className="p-1.5 rounded hover:bg-accent-cyan/10 text-text-muted hover:text-accent-cyan transition-colors"
                      title="Download MP4"
                    >
                      <Download className="w-4 h-4" />
                    </a>
                    <button
                      onClick={() => handleDelete(c.id)}
                      className="p-1.5 rounded hover:bg-rose-500/10 text-text-muted hover:text-rose-400 transition-colors"
                      title="Delete Clip"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Video Preview Modal */}
      {previewClip && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-md flex items-center justify-center z-50 p-4">
          <div className="bg-surface border border-border rounded-xl p-5 max-w-sm w-full space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-text-primary truncate">{previewClip.title}</span>
              <button
                onClick={() => setPreviewClip(null)}
                className="text-text-muted hover:text-text-primary text-xs font-bold"
              >
                ✕
              </button>
            </div>
            <div className="aspect-[9/16] bg-slate-950 rounded-lg overflow-hidden flex items-center justify-center">
              <video
                src={`http://127.0.0.1:8000/api/v1/clips/${previewClip.id}/download`}
                controls
                autoPlay
                className="w-full h-full object-cover"
              />
            </div>
            <div className="text-[11px] text-text-muted flex justify-between pt-1">
              <span>Preset: {previewClip.preset}</span>
              <span>Duration: {previewClip.duration_seconds.toFixed(1)}s</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
