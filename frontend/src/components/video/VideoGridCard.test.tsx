import { render } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import API_BASE from '../../config';
import { VideoGridCard } from './VideoGridCard';
import type { Video } from '../../types';

const video: Video = { id: 7, title: 'Lesson one' };

describe('VideoGridCard media source (F5)', () => {
    it('uses the stream endpoint with a #t=1 poster frame, not a blob: URL', () => {
        const { container } = render(
            <VideoGridCard
                video={video}
                isAdmin={false}
                onDelete={vi.fn()}
                onUpdate={vi.fn()}
                onPlay={vi.fn()}
            />,
        );

        // Built from API_BASE so a developer's local .env override can't break the test.
        const source = container.querySelector('video source');
        expect(source).toHaveAttribute('src', `${API_BASE}/videos/stream/7#t=1`);
    });
});
