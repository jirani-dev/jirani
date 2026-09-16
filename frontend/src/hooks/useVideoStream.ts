import { useEffect, useState } from 'react';
import { Video } from '../types';
import { streamVideo } from '../services/api/videos';

export function useVideoStream(id: Video['id']): string | null {
    const [url, setUrl] = useState<string | null>(null);

    useEffect(() => {
        let active = true;
        let blobUrl: string | null = null;
        streamVideo(id)
            .then(blob => {
                if (!active) return;
                blobUrl = URL.createObjectURL(blob);
                setUrl(blobUrl);
            })
            .catch(() => {
                if (active) setUrl(null);
            });
        return () => {
            active = false;
            if (blobUrl) URL.revokeObjectURL(blobUrl);
        };
    }, [id]);

    return url;
}
