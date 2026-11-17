"use client";

import { useEffect, useState } from "react";
import { Layers, RefreshCw, CheckCircle, Clock, AlertTriangle, XCircle } from "lucide-react";
import { api, ProcessingJob } from "@/services/api";

export default function ProcessingQueuePage() {
  const [jobs, setJobs] = useState<ProcessingJob[]>([]);
  const [loading, setLoading] = useState(true);

  const loadData = () => {
    setLoading(true);
    api.getJobs().then((res) => {
      setJobs(res.items);
      setLoading(false);
    }).catch(() => setLoading(false));
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleCancel = async (id: number) => {
    await api.cancelJob(id);
    loadData();
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-extrabold text-text-primary tracking-tight">
            Processing Queue
          </h1>
          <p className="text-xs text-text-secondary mt-1">
            Real-time pipeline task monitor with progress tracking and cancel controls.
          </p>
        </div>
        <button
          onClick={loadData}
          className="px-3.5 py-2 rounded-lg bg-surface border border-border hover:bg-surface-elevated text-xs font-semibold text-text-primary flex items-center gap-2"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          <span>Refresh</span>
        </button>
      </div>

      <div className="rounded-xl bg-surface border border-border overflow-hidden">
        <table className="w-full text-left text-xs">
          <thead className="bg-surface-elevated/50 text-text-muted border-b border-border uppercase font-semibold">
            <tr>
              <th className="px-6 py-3.5">Job ID</th>
              <th className="px-6 py-3.5">Job Type</th>
              <th className="px-6 py-3.5">Current Stage</th>
              <th className="px-6 py-3.5">Progress</th>
              <th className="px-6 py-3.5">Status</th>
              <th className="px-6 py-3.5">Queued At</th>
              <th className="px-6 py-3.5 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {jobs.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-6 py-12 text-center text-text-muted">
                  No active or historical processing jobs found.
                </td>
              </tr>
            ) : (
              jobs.map((j) => (
                <tr key={j.id} className="hover:bg-surface-elevated/30 transition-colors">
                  <td className="px-6 py-4 font-mono font-bold text-text-primary">#{j.id}</td>
                  <td className="px-6 py-4 capitalize text-text-secondary">{j.job_type.replace("_", " ")}</td>
                  <td className="px-6 py-4 font-mono text-[11px] text-accent-cyan">
                    {j.current_stage || "Queued"}
                  </td>
                  <td className="px-6 py-4 w-48">
                    <div className="flex items-center gap-2">
                      <div className="flex-1 bg-surface-elevated rounded-full h-1.5 overflow-hidden border border-border">
                        <div
                          className="bg-accent-cyan h-full transition-all duration-300"
                          style={{ width: `${j.progress_percent}%` }}
                        />
                      </div>
                      <span className="font-mono text-[10px] text-text-muted">
                        {j.progress_percent.toFixed(0)}%
                      </span>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                        j.status === "completed"
                          ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/30"
                          : j.status === "running"
                          ? "bg-accent-cyan/10 text-accent-cyan border border-accent-cyan/30 animate-pulse"
                          : j.status === "failed"
                          ? "bg-rose-500/10 text-rose-400 border border-rose-500/30"
                          : "bg-surface-elevated text-text-muted border border-border"
                      }`}
                    >
                      {j.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-text-muted">
                    {new Date(j.created_at).toLocaleTimeString()}
                  </td>
                  <td className="px-6 py-4 text-right">
                    {j.status === "running" || j.status === "queued" ? (
                      <button
                        onClick={() => handleCancel(j.id)}
                        className="px-2.5 py-1 rounded bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 text-[11px] font-bold"
                      >
                        Cancel
                      </button>
                    ) : (
                      <span className="text-text-muted">—</span>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
