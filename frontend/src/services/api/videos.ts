// src/services/api/videos.ts
import { api, formData, unwrap } from '../../api/client';
import { Video } from '../../types';
import API_BASE from '../../config';

const BASE = '/videos';

export function getVideoStreamUrl(id: Video['id']): string {
    return `${API_BASE}${BASE}/stream/${id}`;
}

export async function streamVideo(id: Video['id']): Promise<Blob> {
    return unwrap(
        api.GET('/videos/stream/{video_id}', {
            params: { path: { video_id: id } },
            parseAs: 'blob',
        }),
        'Failed to stream video',
    ) as Promise<Blob>;
}

export async function fetchVideos() {
    return unwrap(api.GET('/videos/'), 'Failed to fetch videos');
}

export async function uploadVideo(file: File, tags?: string) {
    return unwrap(
        api.POST('/videos/upload', {
            body: {} as never,
            bodySerializer: () =>
                formData({
                    file,
                    title: file.name.replace(/\.[^/.]+$/, ''),
                    tags: tags?.trim() || undefined,
                }),
        }),
        'Upload failed',
    );
}

export async function uploadVideos(files: File[]) {
    return unwrap(
        api.POST('/videos/upload_multiple', {
            body: {} as never,
            bodySerializer: () => {
                const fd = new FormData();
                files.forEach((f) => fd.append('files', f));
                return fd;
            },
        }),
        'Upload failed',
    );
}

export async function deleteVideo(id: Video['id']): Promise<void> {
    await unwrap(
        api.DELETE('/videos/{video_id}', { params: { path: { video_id: id } } }),
        'Delete failed',
    );
}

export async function updateVideo(
    id: Video['id'], title: string, description: string, tags: string = '',
) {
    return unwrap(
        api.PATCH('/videos/{video_id}', {
            params: {
                path: { video_id: id },
                query: { ...(title.trim() ? { title: title.trim() } : {}), description, tags },
            },
        }),
        'Update failed',
    );
}