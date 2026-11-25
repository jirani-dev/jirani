import { useQuery } from '@tanstack/react-query';
import * as videosApi from '../services/api/videos';

export const videoKeys = { all: ['videos'] as const };

export function useVideos() {
    return useQuery({ queryKey: videoKeys.all, queryFn: videosApi.fetchVideos });
}
