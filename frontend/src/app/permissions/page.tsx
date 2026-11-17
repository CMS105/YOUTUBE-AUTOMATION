"use client";

import { useEffect, useState } from "react";
import { ShieldCheck, Plus, XCircle, CheckCircle, AlertTriangle } from "lucide-react";
import { api, Permission, Streamer } from "@/services/api";

export default function PermissionsPage() {
  const [permissions, setPermissions] = useState<Permission[]>([]);
  const [streamers, setStreamers] = useState<Streamer[]>([]);
  const [loading, setLoading] = useState(true);
  const [showGrantModal, setShowGrantModal] = useState(false);
  const [selectedStreamerId, setSelectedStreamerId] = useState<number | "">("");
  const [notes, setNotes] = useState("");

  const loadData = () => {
    setLoading(true);
    Promise.all([
      api.getPermissions().catch(() => []),
      api.getStreamers().catch(() => ({ items: [] })),
    ]).then(([permRes, stRes]) => {
      setPermissions(permRes);
      setStreamers(stRes.items);
      setLoading(false);
    });
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleGrant = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedStreamerId) return;
    await api.grantPermission(Number(selectedStreamerId), notes || undefined);
    setShowGrantModal(false);
    setSelectedStreamerId("");
    setNotes("");
    loadData();
  };

  const handleRevoke = async (id: number) => {
    const reason = prompt("Enter revocation reason (optional):");
    if (reason !== null) {
      await api.revokePermission(id, reason || undefined);
      loadData();
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-extrabold text-text-primary tracking-tight">
            Creator Permissions & Consent
          </h1>
          <p className="text-xs text-text-secondary mt-1">
            Maintain cryptographic permission records ensuring only authorized gameplay streams are clipped.
          </p>
        </div>
        <button
          onClick={() => setShowGrantModal(true)}
          className="px-4 py-2 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 text-xs font-bold transition-all glow-cyan flex items-center gap-2"
        >
          <ShieldCheck className="w-4 h-4" />
          <span>Grant Streamer Permission</span>
        </button>
      </div>

      <div className="rounded-xl bg-surface border border-border overflow-hidden">
        <table className="w-full text-left text-xs">
          <thead className="bg-surface-elevated/50 text-text-muted border-b border-border uppercase font-semibold">
            <tr>
              <th className="px-6 py-3.5">Permission ID</th>
              <th className="px-6 py-3.5">Streamer ID</th>
              <th className="px-6 py-3.5">Status</th>
              <th className="px-6 py-3.5">Grant Type</th>
              <th className="px-6 py-3.5">Scope</th>
              <th className="px-6 py-3.5">Granted Date</th>
              <th className="px-6 py-3.5 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {permissions.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-6 py-12 text-center text-text-muted">
                  No permission records logged. Grant permission to registered streamers above.
                </td>
              </tr>
            ) : (
              permissions.map((p) => (
                <tr key={p.id} className="hover:bg-surface-elevated/30 transition-colors">
                  <td className="px-6 py-4 font-mono font-bold text-text-primary">#{p.id}</td>
                  <td className="px-6 py-4 font-mono text-text-secondary">Streamer #{p.streamer_id}</td>
                  <td className="px-6 py-4">
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                        p.status === "ACTIVE"
                          ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30"
                          : "bg-rose-500/10 text-rose-400 border border-rose-500/30"
                      }`}
                    >
                      {p.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 capitalize text-text-muted">{p.grant_type}</td>
                  <td className="px-6 py-4 font-mono text-[11px] text-text-muted">{p.scope}</td>
                  <td className="px-6 py-4 text-text-muted">
                    {p.granted_at ? new Date(p.granted_at).toLocaleDateString() : "—"}
                  </td>
                  <td className="px-6 py-4 text-right">
                    {p.status === "ACTIVE" ? (
                      <button
                        onClick={() => handleRevoke(p.id)}
                        className="px-2.5 py-1 rounded bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 text-[11px] font-bold"
                      >
                        Revoke Consent
                      </button>
                    ) : (
                      <span className="text-text-muted text-[11px]">Revoked</span>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Grant Modal */}
      {showGrantModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-surface border border-border rounded-xl p-6 max-w-md w-full space-y-4">
            <h3 className="text-base font-bold text-text-primary">Grant Streamer Permission</h3>
            <form onSubmit={handleGrant} className="space-y-4 text-xs">
              <div>
                <label className="block text-text-secondary mb-1">Select Streamer</label>
                <select
                  required
                  value={selectedStreamerId}
                  onChange={(e) => setSelectedStreamerId(Number(e.target.value))}
                  className="w-full px-3 py-2 rounded-lg bg-surface-elevated border border-border text-text-primary focus:outline-none focus:border-accent-cyan"
                >
                  <option value="">Choose registered streamer...</option>
                  {streamers.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.display_name} (#{s.id})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-text-secondary mb-1">Consent Notes & Terms</label>
                <textarea
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="e.g. Authorized via creator partnership program."
                  rows={3}
                  className="w-full px-3 py-2 rounded-lg bg-surface-elevated border border-border text-text-primary focus:outline-none focus:border-accent-cyan"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowGrantModal(false)}
                  className="px-3.5 py-2 rounded-lg bg-surface-elevated hover:bg-surface-hover text-text-secondary"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-lg bg-emerald-500 text-slate-950 font-bold hover:bg-emerald-400"
                >
                  Grant Permission
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
