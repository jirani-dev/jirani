// src/services/api/audio.ts
import { api, formData, unwrap } from '../../api/client';
import { Audio } from '../../types';

const BASE = '/audio';

export function getAudioStreamUrl(id: Audio['id']): string {
    return `${BASE}/stream/${id}`;
}

export async function streamAudio(id: Audio['id']): Promise<Blob> {
    return unwrap(
        api.GET('/audio/stream/{audio_id}', {
            params: { path: { audio_id: id } },
            parseAs: 'blob',
        }),
        'Failed to stream audio',
    ) as Promise<Blob>;
}

export async function fetchAudioTracks() {
    return unwrap(api.GET('/audio/'), 'Failed to fetch audio');
}

export async function uploadAudio(file: File, tags?: string) {
    return unwrap(
        api.POST('/audio/upload', {
            body: {} as never,
            bodySerializer: () => formData({ file, tags: tags?.trim() || undefined }),
        }),
        'Upload failed',
    );
}

export async function uploadAudioTracks(files: File[]) {
    return unwrap(
        api.POST('/audio/upload_multiple', {
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

export async function deleteAudio(id: Audio['id']): Promise<void> {
    await unwrap(
        api.DELETE('/audio/{audio_id}', { params: { path: { audio_id: id } } }),
        'Delete failed',
    );
}

export async function updateAudio(
    id: Audio['id'], title: string, description: string, tags: string = '',
) {
    return unwrap(
        api.PATCH('/audio/{audio_id}', {
            params: {
                path: { audio_id: id },
                query: { ...(title.trim() ? { title: title.trim() } : {}), description, tags },
            },
        }),
        'Update failed',
    );
}