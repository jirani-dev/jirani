import { useQuery } from '@tanstack/react-query';
import * as audioApi from '../services/api/audio';

export const audioKeys = { all: ['audio'] as const };

export function useAudio() {
    return useQuery({ queryKey: audioKeys.all, queryFn: audioApi.fetchAudioTracks });
}
