import { useState, useEffect, useCallback } from 'react';
import { Video } from '../types';
import * as videosApi from '../services/api/videos';

export function useVideos() {
    const [videos, setVideos] = useState<Video[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const refresh = useCallback(async () => {
        try {
            setVideos(await videosApi.fetchVideos());
            setError(null);
        } catch (e) {
            setError((e as Error).message || 'Failed to fetch videos');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { refresh(); }, [refresh]);

    return { videos, loading, error, refresh, setVideos };
}
