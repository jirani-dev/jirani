// src/services/api/audio.ts
import { ApiError, apiFetch } from './client';
import { Audio } from '../../types';
import API_BASE from '../../config';

const BASE = '/audio';

// For a native <audio src>: the browser streams it with range requests and
// authenticates with the httpOnly cookie, so no token (or apiFetch) is involved.
export function getAudioStreamUrl(id: Audio['id']): string {
    return `${API_BASE}${BASE}/stream/${id}`;
}

export async function fetchAudioTracks(): Promise<Audio[]> {
    const res = await apiFetch(`${BASE}/`);
    if (!res.ok) throw await ApiError.fromResponse(res, 'Failed to fetch audio');
    return res.json();
}

export async function uploadAudio(file: File, tags?: string): Promise<Audio> {
    const formData = new FormData();
    formData.append('file', file);
    if (tags?.trim()) formData.append('tags', tags.trim());
    const res = await apiFetch(`${BASE}/upload`, { method: 'POST', body: formData });
    if (!res.ok) throw await ApiError.fromResponse(res, 'Upload failed');
    return res.json();
}

export async function deleteAudio(id: Audio['id']): Promise<void> {
    const res = await apiFetch(`${BASE}/${id}`, { method: 'DELETE' });
    if (!res.ok) throw await ApiError.fromResponse(res, 'Delete failed');
}

export async function updateAudio(
    id: Audio['id'], title: string, description: string, tags: string = '',
): Promise<Audio> {
    const params = new URLSearchParams();
    if (title.trim()) params.append('title', title.trim());
    params.append('description', description);
    params.append('tags', tags);
    const res = await apiFetch(`${BASE}/${id}?${params}`, { method: 'PATCH' });
    if (!res.ok) throw await ApiError.fromResponse(res, 'Update failed');
    return res.json();
}
