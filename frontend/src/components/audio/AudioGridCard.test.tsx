import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { AudioGridCard } from './AudioGridCard';
import type { Audio } from '../../types';

// Any request this file does not expect (a fetch of the stream, say) is an error.
const server = setupServer();

beforeAll(() => {
    // jsdom has no media playback; the card only ever calls pause().
    vi.spyOn(HTMLMediaElement.prototype, 'pause').mockImplementation(() => {});
    server.listen({ onUnhandledRequest: 'error' });
});
afterEach(() => server.resetHandlers());
afterAll(() => {
    server.close();
    vi.restoreAllMocks();
});

const track: Audio = { id: 7, title: 'Morning song', tags: [{ id: 1, name: 'music' }] };

const renderCard = (canManage: boolean, onDelete = vi.fn(), onError = vi.fn()) =>
    render(
        <AudioGridCard
            audio={track}
            canManage={canManage}
            onDelete={onDelete}
            onUpdate={vi.fn()}
            onPlay={vi.fn()}
            onError={onError}
            currentlyPlaying={null}
        />,
    );

describe('AudioGridCard', () => {
    it('lets the browser stream the track: src on the element, nothing fetched up front', () => {
        // The card used to download every track in full through apiFetch and
        // hand the element a blob URL via a <source> child, which a media
        // element does not pick up once it is mounted.
        const fetchSpy = vi.spyOn(globalThis, 'fetch');
        const { container } = renderCard(false);

        const audio = container.querySelector('audio');
        expect(audio).toHaveAttribute('src', '/api/audio/stream/7');
        expect(audio).toHaveAttribute('preload', 'none');
        expect(container.querySelector('source')).toBeNull();
        expect(fetchSpy).not.toHaveBeenCalled();
    });

    it('offers edit and delete only to someone who may manage content', () => {
        renderCard(false);
        expect(screen.queryByRole('button', { name: /edit audio/i })).toBeNull();
        expect(screen.queryByRole('button', { name: /delete audio/i })).toBeNull();
    });

    it('reports a refused delete instead of failing silently', async () => {
        server.use(
            http.delete('*/audio/7', () =>
                HttpResponse.json({ detail: 'Insufficient permissions' }, { status: 403 }),
            ),
        );
        const onDelete = vi.fn();
        const onError = vi.fn();
        renderCard(true, onDelete, onError);

        await userEvent.setup().click(screen.getByRole('button', { name: /delete audio/i }));

        await waitFor(() => expect(onError).toHaveBeenCalledWith('Insufficient permissions'));
        expect(onDelete).not.toHaveBeenCalled();
    });
});
