import { render } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import API_BASE from '../../config';
import { VideoPlayerModal } from './VideoPlayerModal';
import type { Video } from '../../types';

const video: Video = { id: 7, title: 'Lesson one' };

describe('VideoPlayerModal media source (F5)', () => {
    it('points the native tag straight at the stream endpoint, not a blob: URL', () => {
        const { container } = render(<VideoPlayerModal video={video} onClose={vi.fn()} />);

        // Built from API_BASE so a developer's local .env override can't break the test.
        const source = container.querySelector('video source');
        expect(source).toHaveAttribute('src', `${API_BASE}/videos/stream/7`);
    });
});
