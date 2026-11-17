"use client";

import { useEffect, useState } from "react";
import { Users, Plus, Trash2, ExternalLink, ShieldCheck, Check } from "lucide-react";
import { api, Streamer } from "@/services/api";

export default function StreamersPage() {
  const [streamers, setStreamers] = useState<Streamer[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAddModal, setShowAddModal] = useState(false);
  const [name, setName] = useState("");
  const [channelId, setChannelId] = useState("");

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

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    await api.createStreamer({ display_name: name.trim(), channel_id: channelId.trim() || undefined });
    setName("");
    setChannelId("");
    setShowAddModal(false);
    loadData();
  };

  const handleDelete = async (id: number) => {
    if (confirm("Delete this streamer and all associated recordings?")) {
      await api.deleteStreamer(id);
      loadData();
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-extrabold text-text-primary tracking-tight">
            Registered Streamers
          </h1>
          <p className="text-xs text-text-secondary mt-1">
            Maintain authorized GTA 6 streamer roster, platform handles, and channel identifiers.
          </p>
        </div>
        <button
          onClick={() => setShowAddModal(true)}
          className="px-4 py-2 rounded-lg bg-accent-cyan hover:bg-accent-cyan-bright text-slate-950 text-xs font-bold transition-all glow-cyan flex items-center gap-2"
        >
          <Plus className="w-4 h-4" />
          <span>Register Streamer</span>
        </button>
      </div>

      {/* Streamers Table */}
      <div className="rounded-xl bg-surface border border-border overflow-hidden">
        <table className="w-full text-left text-xs">
          <thead className="bg-surface-elevated/50 text-text-muted border-b border-border uppercase font-semibold">
            <tr>
              <th className="px-6 py-3.5">Streamer</th>
              <th className="px-6 py-3.5">Platform</th>
              <th className="px-6 py-3.5">Channel ID</th>
              <th className="px-6 py-3.5">Permission State</th>
              <th className="px-6 py-3.5">Registered</th>
              <th className="px-6 py-3.5 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {streamers.map((s) => (
              <tr key={s.id} className="hover:bg-surface-elevated/30 transition-colors">
                <td className="px-6 py-4 font-bold text-text-primary">{s.display_name}</td>
                <td className="px-6 py-4 capitalize text-text-secondary">{s.platform}</td>
                <td className="px-6 py-4 font-mono text-text-muted">{s.channel_id || "—"}</td>
                <td className="px-6 py-4">
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                      s.permission_status === "ACTIVE"
                        ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30"
                        : "bg-amber-500/10 text-amber-400 border border-amber-500/30"
                    }`}
                  >
                    {s.permission_status || "PENDING"}
                  </span>
                </td>
                <td className="px-6 py-4 text-text-muted">{new Date(s.created_at).toLocaleDateString()}</td>
                <td className="px-6 py-4 text-right">
                  <button
                    onClick={() => handleDelete(s.id)}
                    className="p-1.5 rounded hover:bg-rose-500/10 text-text-muted hover:text-rose-400 transition-colors"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Add Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-surface border border-border rounded-xl p-6 max-w-md w-full space-y-4">
            <h3 className="text-base font-bold text-text-primary">Register New GTA 6 Streamer</h3>
            <form onSubmit={handleCreate} className="space-y-4 text-xs">
              <div>
                <label className="block text-text-secondary mb-1">Display Name</label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. ViceCityKing"
                  className="w-full px-3 py-2 rounded-lg bg-surface-elevated border border-border text-text-primary focus:outline-none focus:border-accent-cyan"
                />
              </div>
              <div>
                <label className="block text-text-secondary mb-1">YouTube Channel ID (Optional)</label>
                <input
                  type="text"
                  value={channelId}
                  onChange={(e) => setChannelId(e.target.value)}
                  placeholder="e.g. UCxxxxxxxx"
                  className="w-full px-3 py-2 rounded-lg bg-surface-elevated border border-border text-text-primary focus:outline-none focus:border-accent-cyan font-mono"
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-3.5 py-2 rounded-lg bg-surface-elevated hover:bg-surface-hover text-text-secondary"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-lg bg-accent-cyan text-slate-950 font-bold hover:bg-accent-cyan-bright"
                >
                  Register
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
