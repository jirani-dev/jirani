// src/services/api/videos.ts
import { ApiError, apiFetch } from './client';
import { Video } from '../../types';
import API_BASE from '../../config';

const BASE = '/videos';

// For a native <video src>: the browser streams it with range requests and
// authenticates with the httpOnly cookie, so no token (or apiFetch) is involved.
export function getVideoStreamUrl(id: Video['id']): string {
    return `${API_BASE}${BASE}/stream/${id}`;
}

export async function fetchVideos(): Promise<Video[]> {
    const res = await apiFetch(`${BASE}/`);
    if (!res.ok) throw await ApiError.fromResponse(res, 'Failed to fetch videos');
    return res.json();
}

export async function uploadVideo(file: File, tags?: string): Promise<Video> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('title', file.name.replace(/\.[^/.]+$/, ''));
    if (tags?.trim()) formData.append('tags', tags.trim());
    const res = await apiFetch(`${BASE}/upload`, { method: 'POST', body: formData });
    if (!res.ok) throw await ApiError.fromResponse(res, 'Upload failed');
    return res.json();
}

export async function deleteVideo(id: Video['id']): Promise<void> {
    const res = await apiFetch(`${BASE}/${id}`, { method: 'DELETE' });
    if (!res.ok) throw await ApiError.fromResponse(res, 'Delete failed');
}

export async function updateVideo(
    id: Video['id'], title: string, description: string, tags: string = '',
): Promise<Video> {
    const params = new URLSearchParams();
    if (title.trim()) params.append('title', title.trim());
    params.append('description', description);
    params.append('tags', tags);
    const res = await apiFetch(`${BASE}/${id}?${params}`, { method: 'PATCH' });
    if (!res.ok) throw await ApiError.fromResponse(res, 'Update failed');
    return res.json();
}
