import { useState, useEffect, useCallback } from 'react';
import { Audio } from '../types';
import * as audioApi from '../services/api/audio';

export function useAudio() {
    const [audioTracks, setAudioTracks] = useState<Audio[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const refresh = useCallback(async () => {
        try {
            setAudioTracks(await audioApi.fetchAudioTracks());
            setError(null);
        } catch (e) {
            setError((e as Error).message || 'Failed to fetch audio');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { refresh(); }, [refresh]);

    return { audioTracks, loading, error, refresh, setAudioTracks };
}
