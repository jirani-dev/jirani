// src/services/api/audio.ts
import { api, multipart, unwrap } from '../../api/client';
import type { components } from '../../api/generated/schema';
import { Audio } from '../../types';
import API_BASE from '../../config';

type Schemas = components['schemas'];

// For a native <audio src>: the browser streams it with range requests and
// authenticates with the httpOnly cookie, so no token (or API client) is involved.
export function getAudioStreamUrl(id: Audio['id']): string {
    return `${API_BASE}/audio/stream/${id}`;
}

export async function fetchAudioTracks(): Promise<Audio[]> {
    return unwrap(api.GET('/audio/'), 'Failed to fetch audio');
}

export async function uploadAudio(file: File, tags?: string): Promise<Audio> {
    return unwrap(
        api.POST('/audio/upload', {
            body: multipart<Schemas['Body_upload_track_audio_upload_post']>({
                file,
                tags: tags?.trim() || null,
            }),
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
): Promise<Audio> {
    return unwrap(
        api.PATCH('/audio/{audio_id}', {
            params: {
                path: { audio_id: id },
                // A blank title is not sent (the title is kept); description
                // and tags always are, so that clearing them works.
                query: { title: title.trim() || null, description, tags },
            },
        }),
        'Update failed',
    );
}
