/**
 * GTA 6 AI Clip Factory — API Client Service
 * Connects frontend to the FastAPI backend with full type safety.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api/v1";

// --- Types ---
export interface Streamer {
  id: number;
  uuid: string;
  display_name: string;
  platform: string;
  channel_id: string | null;
  channel_url: string | null;
  avatar_url: string | null;
  description: string | null;
  is_active: boolean;
  permission_status: "ACTIVE" | "PENDING" | "REVOKED" | null;
  created_at: string;
  updated_at: string;
}

export interface Permission {
  id: number;
  streamer_id: number;
  status: "ACTIVE" | "PENDING" | "REVOKED" | "EXPIRED";
  grant_type: string;
  granted_at: string | null;
  expires_at: string | null;
  revoked_at: string | null;
  scope: string;
  notes: string | null;
  created_at: string;
}

export interface Recording {
  id: number;
  uuid: string;
  streamer_id: number;
  stream_id: number | null;
  file_name: string;
  file_size_bytes: number | null;
  duration_seconds: number | null;
  width: number | null;
  height: number | null;
  fps: number | null;
  codec_video: string | null;
  codec_audio: string | null;
  status: string;
  ingested_at: string;
  created_at: string;
}

export interface YouTubePollResult {
  status: "completed" | "skipped";
  message?: string;
  streamers_checked: number;
  live_streams_detected: number;
  quota_status?: {
    used_units: number;
    daily_limit: number;
    remaining_units: number;
    percentage_used: number;
    last_reset: string;
  };
}

export interface Clip {
  id: number;
  uuid: string;
  candidate_id: number;
  title: string;
  file_name: string;
  file_size_bytes: number | null;
  duration_seconds: number;
  width: number;
  height: number;
  preset: "Viral Gaming" | "Clean Gameplay" | "Reaction Focus";
  score: number;
  event_category: string;
  has_subtitles: boolean;
  is_favorite: boolean;
  download_count: number;
  rendered_at: string;
  created_at: string;
  streamer_name?: string;
  thumbnail_url?: string;
  download_url?: string;
}

export interface ClipCandidate {
  id: number;
  uuid: string;
  recording_id: number;
  start_time: number;
  end_time: number;
  duration: number;
  score_audio: number;
  score_visual: number;
  score_context: number;
  score_composite: number;
  rank: number | null;
  event_category: string;
  status: "pending" | "approved" | "rejected" | "rendered";
  has_facecam: boolean;
  facecam_region?: { x: number; y: number; w: number; h: number } | null;
  transcript_text: string | null;
  suggested_titles: string[] | null;
  created_at: string;
}

export interface ProcessingJob {
  id: number;
  uuid: string;
  recording_id: number | null;
  job_type: string;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  current_stage: string | null;
  progress_percent: number;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  result_summary: any;
  created_at: string;
  updated_at: string;
}

export interface DashboardStats {
  total_streamers: number;
  active_permissions: number;
  total_recordings: number;
  total_clips: number;
  total_candidates: number;
  active_jobs: number;
  failed_jobs: number;
  total_storage_mb: number;
  gpu_info: {
    cuda_available: boolean;
    device_name?: string;
    total_vram_mb?: number;
    reserved_vram_mb?: number;
    allocated_vram_mb?: number;
    free_vram_mb?: number;
    device?: string;
  };
  integrations: {
    youtube_api: { configured: boolean; key_hint: string; poll_interval_s: number };
    youtube_oauth: { configured: boolean; client_id_hint: string };
    gemini: { configured: boolean; model: string; key_hint: string };
    openai: { configured: boolean; model: string; key_hint: string };
    active_vlm: string;
    auto_publish: boolean;
  };
}

// --- Fetch Helper ---
async function fetchApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  try {
    const res = await fetch(url, {
      headers: {
        "Content-Type": "application/json",
        ...options?.headers,
      },
      ...options,
    });
    if (!res.ok) {
      const errorData = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(errorData.detail || `HTTP Error ${res.status}`);
    }
    return (await res.json()) as T;
  } catch (err: any) {
    console.error(`API Error on ${endpoint}:`, err);
    throw err;
  }
}

// --- API Methods ---
export const api = {
  // Health & Stats
  getHealth: () => fetchApi<{ status: string; hardware: any; integrations: any }>("/health"),
  getIntegrationsStatus: () => fetchApi<any>("/integrations/status"),
  getDashboardStats: () => fetchApi<DashboardStats>("/dashboard/stats"),

  // Streamers
  getStreamers: (skip = 0, limit = 50, search?: string) => {
    const params = new URLSearchParams({ skip: String(skip), limit: String(limit) });
    if (search) params.append("search", search);
    return fetchApi<{ items: Streamer[]; total: number }>(`/streamers?${params}`);
  },
  createStreamer: (data: Partial<Streamer>) =>
    fetchApi<Streamer>("/streamers", { method: "POST", body: JSON.stringify(data) }),
  deleteStreamer: (id: number) =>
    fetchApi<{ status: string }>(`/streamers/${id}`, { method: "DELETE" }),

  // YouTube monitoring
  pollYouTube: () => fetchApi<YouTubePollResult>("/youtube/poll", { method: "POST" }),

  // Authorized recording intake
  uploadRecording: async (streamerId: number, file: File): Promise<Recording> => {
    const formData = new FormData();
    formData.append("streamer_id", String(streamerId));
    formData.append("file", file);

    const response = await fetch(`${API_BASE}/ingest/upload`, {
      method: "POST",
      body: formData,
    });
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(errorData.detail || `Upload failed (HTTP ${response.status})`);
    }
    return (await response.json()) as Recording;
  },

  // Permissions
  getPermissions: (streamerId?: number) => {
    const params = streamerId ? `?streamer_id=${streamerId}` : "";
    return fetchApi<Permission[]>(`/permissions${params}`);
  },
  grantPermission: (streamerId: number, notes?: string) =>
    fetchApi<Permission>("/permissions/grant", {
      method: "POST",
      body: JSON.stringify({ streamer_id: streamerId, grant_type: "manual", scope: "clip_creation", notes }),
    }),
  revokePermission: (permissionId: number, reason?: string) =>
    fetchApi<Permission>(`/permissions/${permissionId}/revoke`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    }),

  // Clips
  getClips: (skip = 0, limit = 50, search?: string, preset?: string) => {
    const params = new URLSearchParams({ skip: String(skip), limit: String(limit) });
    if (search) params.append("search", search);
    if (preset) params.append("preset", preset);
    return fetchApi<{ items: Clip[]; total: number }>(`/clips?${params}`);
  },
  getClip: (id: number) => fetchApi<Clip>(`/clips/${id}`),
  updateClip: (id: number, data: { title?: string; is_favorite?: boolean }) =>
    fetchApi<Clip>(`/clips/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  deleteClip: (id: number) => fetchApi<{ status: string }>(`/clips/${id}`, { method: "DELETE" }),

  // Jobs
  getJobs: () => fetchApi<{ items: ProcessingJob[]; total: number }>("/jobs"),
  createJob: (recordingId: number) =>
    fetchApi<ProcessingJob>("/jobs", { method: "POST", body: JSON.stringify({ recording_id: recordingId }) }),
  cancelJob: (jobId: number) => fetchApi<ProcessingJob>(`/jobs/${jobId}/cancel`, { method: "POST" }),

  // Candidates
  getCandidates: (recordingId?: number, status?: string, minScore?: number) => {
    const params = new URLSearchParams();
    if (recordingId) params.append("recording_id", String(recordingId));
    if (status) params.append("status", status);
    if (minScore !== undefined) params.append("min_score", String(minScore));
    return fetchApi<{ items: ClipCandidate[]; total: number; skip: number; limit: number }>(`/candidates?${params}`);
  },
  getCandidate: (id: number) => fetchApi<ClipCandidate>(`/candidates/${id}`),
  generateCandidates: (recordingId: number, count = 10) =>
    fetchApi<ClipCandidate[]>(`/candidates/generate/${recordingId}?count=${count}`, { method: "POST" }),
  approveCandidate: (candidateId: number, preset = "Viral Gaming", customTitle?: string) =>
    fetchApi<ProcessingJob>(`/candidates/${candidateId}/approve`, {
      method: "POST",
      body: JSON.stringify({ preset, custom_title: customTitle }),
    }),
  renderCandidate: (candidateId: number, preset = "Viral Gaming", customTitle?: string) =>
    fetchApi<Clip>(`/candidates/${candidateId}/render`, {
      method: "POST",
      body: JSON.stringify({ preset, custom_title: customTitle }),
    }),
  rejectCandidate: (candidateId: number) =>
    fetchApi<ClipCandidate>(`/candidates/${candidateId}/reject`, { method: "POST" }),
};
