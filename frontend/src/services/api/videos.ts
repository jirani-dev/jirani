// src/services/api/videos.ts
import { api, multipart, unwrap } from '../../api/client';
import type { components } from '../../api/generated/schema';
import { Video } from '../../types';
import API_BASE from '../../config';

type Schemas = components['schemas'];

// For a native <video src>: the browser streams it with range requests and
// authenticates with the httpOnly cookie, so no token (or API client) is involved.
export function getVideoStreamUrl(id: Video['id']): string {
    return `${API_BASE}/videos/stream/${id}`;
}

export async function fetchVideos(): Promise<Video[]> {
    return unwrap(api.GET('/videos/'), 'Failed to fetch videos');
}

export async function uploadVideo(file: File, tags?: string): Promise<Video> {
    return unwrap(
        api.POST('/videos/upload', {
            body: multipart<Schemas['Body_upload_video_videos_upload_post']>({
                file,
                title: file.name.replace(/\.[^/.]+$/, ''),
                tags: tags?.trim() || null,
            }),
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
): Promise<Video> {
    return unwrap(
        api.PATCH('/videos/{video_id}', {
            params: {
                path: { video_id: id },
                // A blank title is not sent (the title is kept); description
                // and tags always are, so that clearing them works.
                query: { title: title.trim() || null, description, tags },
            },
        }),
        'Update failed',
    );
}
