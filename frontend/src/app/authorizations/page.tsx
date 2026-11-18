"use client";

import { useEffect, useState } from "react";
import {
  KeyRound,
  ShieldCheck,
  ShieldAlert,
  Search,
  Plus,
  RefreshCw,
  CheckCircle2,
  AlertCircle,
  FileCheck,
  ExternalLink,
  Ban,
} from "lucide-react";
import { api, CreatorAuthorization } from "@/services/api";

export default function AuthorizationsPage() {
  const [authorizations, setAuthorizations] = useState<CreatorAuthorization[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [showAddModal, setShowAddModal] = useState(false);
  const [revokingId, setRevokingId] = useState<number | null>(null);
  const [revokeReason, setRevokeReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [notice, setNotice] = useState<{ type: "success" | "error"; message: string } | null>(null);

  // New Auth form state
  const [newChannelId, setNewChannelId] = useState("");
  const [newCreatorName, setNewCreatorName] = useState("");
  const [newSource, setNewSource] = useState("");
  const [newScope, setNewScope] = useState<"clip_creation" | "full_access">("clip_creation");
  const [newNotes, setNewNotes] = useState("");

  const showNotice = (type: "success" | "error", message: string) => {
    setNotice({ type, message });
    setTimeout(() => setNotice(null), 5000);
  };

  const loadAuthorizations = async () => {
    try {
      setLoading(true);
      const res = await api.getAuthorizations({
        status: statusFilter || undefined,
        search: search || undefined,
      });
      setAuthorizations(res.items);
    } catch (e: any) {
      showNotice("error", e.message || "Failed to load creator authorizations.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAuthorizations();
  }, [statusFilter]);

  const handleCreate = async () => {
    if (!newChannelId.trim() || !newCreatorName.trim()) {
      showNotice("error", "Channel ID and Creator Name are required.");
      return;
    }
    try {
      setSubmitting(true);
      await api.authorizeCreator({
        channel_id: newChannelId.trim(),
        creator_name: newCreatorName.trim(),
        authorized_source: newSource.trim() || undefined,
        allowed_scope: newScope,
        notes: newNotes.trim() || undefined,
        status: "ACTIVE",
      });
      showNotice("success", `Authorization granted for "${newCreatorName}"!`);
      setShowAddModal(false);
      setNewChannelId("");
      setNewCreatorName("");
      setNewSource("");
      setNewNotes("");
      loadAuthorizations();
    } catch (e: any) {
      showNotice("error", e.message || "Failed to create authorization.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleRevoke = async () => {
    if (!revokingId || !revokeReason.trim()) {
      showNotice("error", "Please provide a reason for revoking authorization.");
      return;
    }
    try {
      setSubmitting(true);
      await api.revokeAuthorization(revokingId, revokeReason);
      showNotice("success", "Authorization revoked successfully.");
      setRevokingId(null);
      setRevokeReason("");
      loadAuthorizations();
    } catch (e: any) {
      showNotice("error", e.message || "Failed to revoke authorization.");
    } finally {
      setSubmitting(false);
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
            <span className="text-sm font-medium">{notice.message}</span>
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
            <div className="p-2.5 rounded-xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <KeyRound className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-2xl font-black tracking-tight text-white flex items-center gap-2">
                Creator Authorizations
                <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 font-mono">
                  PERMISSION GATEWAY
                </span>
              </h1>
              <p className="text-xs text-[#94A3B8] mt-0.5">
                Maintain explicit consent records and approved ingestion sources before recording.
              </p>
            </div>
          </div>
        </div>

        <button
          onClick={() => setShowAddModal(true)}
          className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 text-xs font-bold shadow-lg shadow-emerald-500/20 transition-all"
        >
          <Plus className="w-4 h-4" />
          Authorize New Creator
        </button>
      </div>

      {/* Search & Filter Bar */}
      <div className="flex flex-col md:flex-row gap-4 items-center justify-between p-4 rounded-xl bg-[#111C2E] border border-[#172337]">
        <div className="relative w-full md:w-80">
          <Search className="w-4 h-4 absolute left-3 top-3 text-[#94A3B8]" />
          <input
            type="text"
            placeholder="Search creator name or channel ID..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && loadAuthorizations()}
            className="w-full pl-9 pr-4 py-2 bg-[#0B1220] border border-[#172337] rounded-lg text-xs text-white placeholder-[#94A3B8] focus:outline-none focus:border-[#38BDF8]"
          />
        </div>

        <div className="flex items-center gap-2">
          {["", "ACTIVE", "PENDING", "REVOKED"].map((st) => (
            <button
              key={st}
              onClick={() => setStatusFilter(st)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                statusFilter === st
                  ? "bg-[#38BDF8]/20 text-[#38BDF8] border border-[#38BDF8]/40 font-semibold"
                  : "text-[#94A3B8] hover:text-white hover:bg-[#172337]"
              }`}
            >
              {st === "" ? "All Statuses" : st}
            </button>
          ))}
          <button
            onClick={loadAuthorizations}
            className="p-2 rounded-lg bg-[#0B1220] text-[#94A3B8] hover:text-white border border-[#172337]"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Authorizations Table */}
      <div className="rounded-2xl bg-[#111C2E] border border-[#172337] overflow-hidden">
        {loading ? (
          <div className="p-16 text-center">
            <RefreshCw className="w-8 h-8 text-[#38BDF8] animate-spin mx-auto mb-3" />
            <div className="text-xs font-semibold text-white">Loading Authorizations...</div>
          </div>
        ) : authorizations.length === 0 ? (
          <div className="p-16 text-center space-y-3">
            <ShieldAlert className="w-12 h-12 text-[#94A3B8] mx-auto opacity-30" />
            <div className="text-sm font-bold text-white">No creator authorizations found</div>
            <p className="text-xs text-[#94A3B8] max-w-sm mx-auto">
              Add explicit permissions for GTA 6 creators to unlock automated OBS recording.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-[#0B1220] text-[#94A3B8] font-mono border-b border-[#172337]">
                <tr>
                  <th className="p-4">Creator / Channel</th>
                  <th className="p-4">Channel ID</th>
                  <th className="p-4">Approved Ingestion Feed</th>
                  <th className="p-4">Scope</th>
                  <th className="p-4">Status</th>
                  <th className="p-4">Authorized At</th>
                  <th className="p-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#172337]">
                {authorizations.map((auth) => (
                  <tr key={auth.id} className="hover:bg-[#172337]/40 transition-colors">
                    <td className="p-4 font-bold text-white flex items-center gap-2">
                      <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
                      {auth.creator_name}
                    </td>
                    <td className="p-4 font-mono text-slate-400">{auth.channel_id}</td>
                    <td className="p-4 font-mono text-[#38BDF8] truncate max-w-[200px]">
                      {auth.authorized_source || <span className="text-amber-400 italic">None configured</span>}
                    </td>
                    <td className="p-4 font-mono text-slate-300 uppercase text-[10px]">
                      {auth.allowed_scope.replace("_", " ")}
                    </td>
                    <td className="p-4">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold font-mono ${
                          auth.status === "ACTIVE"
                            ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                            : auth.status === "REVOKED"
                            ? "bg-rose-500/20 text-rose-400 border border-rose-500/30"
                            : "bg-amber-500/20 text-amber-400 border border-amber-500/30"
                        }`}
                      >
                        {auth.status}
                      </span>
                    </td>
                    <td className="p-4 text-slate-500 font-mono">
                      {auth.authorized_at
                        ? new Date(auth.authorized_at).toLocaleDateString()
                        : "—"}
                    </td>
                    <td className="p-4 text-right">
                      {auth.status === "ACTIVE" && (
                        <button
                          onClick={() => setRevokingId(auth.id)}
                          className="px-3 py-1 rounded bg-rose-950/60 text-rose-400 border border-rose-500/30 hover:bg-rose-900 text-[11px] font-bold transition-all"
                        >
                          Revoke
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

      {/* Add Authorization Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-lg rounded-2xl bg-[#111C2E] border border-[#172337] p-6 space-y-6 shadow-2xl">
            <div className="flex items-center justify-between border-b border-[#172337] pb-4">
              <div className="flex items-center gap-2">
                <KeyRound className="w-5 h-5 text-emerald-400" />
                <h2 className="text-base font-bold text-white">Grant Creator Authorization</h2>
              </div>
              <button onClick={() => setShowAddModal(false)} className="text-xs text-[#94A3B8] hover:text-white">✕</button>
            </div>

            <div className="space-y-4 text-xs">
              <div>
                <label className="text-[#94A3B8] block mb-1">Creator Name *</label>
                <input
                  type="text"
                  placeholder="e.g. MiamiViceChampion"
                  value={newCreatorName}
                  onChange={(e) => setNewCreatorName(e.target.value)}
                  className="w-full p-2.5 rounded-lg bg-[#0B1220] border border-[#172337] text-white focus:outline-none focus:border-[#38BDF8]"
                />
              </div>

              <div>
                <label className="text-[#94A3B8] block mb-1">YouTube Channel ID *</label>
                <input
                  type="text"
                  placeholder="e.g. UC_SAMPLE_CHANNEL_ID"
                  value={newChannelId}
                  onChange={(e) => setNewChannelId(e.target.value)}
                  className="w-full p-2.5 rounded-lg bg-[#0B1220] border border-[#172337] text-white font-mono focus:outline-none focus:border-[#38BDF8]"
                />
              </div>

              <div>
                <label className="text-[#38BDF8] block mb-1 font-semibold">Approved Ingestion Feed / OBS Source</label>
                <input
                  type="text"
                  placeholder="e.g. OBS:WindowCapture_GTA6 or rtmp://127.0.0.1:1935/live/feed"
                  value={newSource}
                  onChange={(e) => setNewSource(e.target.value)}
                  className="w-full p-2.5 rounded-lg bg-[#0B1220] border border-[#38BDF8]/40 text-white font-mono focus:outline-none focus:border-[#38BDF8]"
                />
              </div>

              <div>
                <label className="text-[#94A3B8] block mb-1">Usage Scope</label>
                <select
                  value={newScope}
                  onChange={(e) => setNewScope(e.target.value as any)}
                  className="w-full p-2.5 rounded-lg bg-[#0B1220] border border-[#172337] text-white"
                >
                  <option value="clip_creation">Clip Creation & Highlight Editing</option>
                  <option value="full_access">Full Access</option>
                </select>
              </div>

              <div>
                <label className="text-[#94A3B8] block mb-1">Consent / Legal Notes</label>
                <textarea
                  rows={2}
                  placeholder="e.g. Written authorization granted via email consent."
                  value={newNotes}
                  onChange={(e) => setNewNotes(e.target.value)}
                  className="w-full p-2.5 rounded-lg bg-[#0B1220] border border-[#172337] text-white resize-none"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-4 border-t border-[#172337]">
              <button onClick={() => setShowAddModal(false)} className="px-4 py-2 rounded-lg text-xs font-semibold text-[#94A3B8]">
                Cancel
              </button>
              <button
                onClick={handleCreate}
                disabled={submitting}
                className="px-5 py-2.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs shadow-lg shadow-emerald-500/20 disabled:opacity-50"
              >
                {submitting ? "Saving..." : "Authorize Creator"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Revoke Modal */}
      {revokingId && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-md rounded-2xl bg-[#111C2E] border border-rose-500/40 p-6 space-y-4 shadow-2xl">
            <div className="flex items-center gap-2 text-rose-400">
              <Ban className="w-5 h-5" />
              <h2 className="text-base font-bold text-white">Revoke Creator Authorization</h2>
            </div>
            <p className="text-xs text-[#94A3B8]">
              Revoking authorization immediately stops any running OBS recording sessions and marks the creator as REVOKED.
            </p>
            <div>
              <label className="text-xs text-[#94A3B8] block mb-1 font-semibold">Reason for Revocation *</label>
              <input
                type="text"
                placeholder="e.g. Streamer requested cessation of clipping."
                value={revokeReason}
                onChange={(e) => setRevokeReason(e.target.value)}
                className="w-full p-2.5 rounded-lg bg-[#0B1220] border border-rose-500/40 text-xs text-white focus:outline-none"
              />
            </div>
            <div className="flex items-center justify-end gap-3 pt-4 border-t border-[#172337]">
              <button onClick={() => setRevokingId(null)} className="px-4 py-2 rounded-lg text-xs font-semibold text-[#94A3B8]">
                Cancel
              </button>
              <button
                onClick={handleRevoke}
                disabled={submitting || !revokeReason.trim()}
                className="px-4 py-2 rounded-lg bg-rose-600 hover:bg-rose-500 text-white font-bold text-xs disabled:opacity-50"
              >
                {submitting ? "Revoking..." : "Confirm Revocation"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
