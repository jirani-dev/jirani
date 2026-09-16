import { useEffect, useState } from 'react';
import { Audio } from '../types';
import { streamAudio } from '../services/api/audio';

export function useAudioStream(id: Audio['id']): string | null {
    const [url, setUrl] = useState<string | null>(null);

    useEffect(() => {
        let active = true;
        let blobUrl: string | null = null;
        streamAudio(id)
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
