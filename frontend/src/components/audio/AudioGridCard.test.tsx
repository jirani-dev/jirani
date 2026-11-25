import { render } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import API_BASE from '../../config';
import { AudioGridCard } from './AudioGridCard';
import type { Audio } from '../../types';

const audio: Audio = { id: 3, title: 'Morning song' };

describe('AudioGridCard media source (F5)', () => {
    // Pins the API_BASE prefix: without it the native tag would bypass the proxy
    // and request /audio/stream/{id} from the SPA root. (config.test.ts pins that
    // API_BASE defaults to '/api'.)
    it('prefixes the stream URL with API_BASE, not a blob: URL', () => {
        const { container } = render(
            <AudioGridCard
                audio={audio}
                isAdmin={false}
                onDelete={vi.fn()}
                onUpdate={vi.fn()}
                onPlay={vi.fn()}
                currentlyPlaying={audio.id}
            />,
        );

        const source = container.querySelector('audio source');
        expect(source).toHaveAttribute('src', `${API_BASE}/audio/stream/3`);
    });
});
