import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { VideoGridCard } from './VideoGridCard';
import { VideoPlayerModal } from './VideoPlayerModal';
import type { Video } from '../../types';

const renderCard = (video: Video, canManage = false) =>
    render(
        <VideoGridCard
            video={video}
            canManage={canManage}
            onDelete={vi.fn()}
            onUpdate={vi.fn()}
            onPlay={vi.fn()}
            onError={vi.fn()}
        />,
    );

describe('VideoGridCard thumbnail', () => {
    it('uses the stored poster when the server made one, with no video request at all', () => {
        const fetchSpy = vi.spyOn(globalThis, 'fetch');
        const { container } = renderCard({ id: 3, title: 'Lesson', poster_url: '/static/covers/p.jpg' });

        expect(container.querySelector('img')).toHaveAttribute('src', '/static/covers/p.jpg');
        expect(container.querySelector('video')).toBeNull();
        expect(fetchSpy).not.toHaveBeenCalled();
        fetchSpy.mockRestore();
    });

    it('otherwise shows a frame of the stream itself, loading metadata only', () => {
        // It used to download the whole file per card just to draw this frame.
        const fetchSpy = vi.spyOn(globalThis, 'fetch');
        const { container } = renderCard({ id: 3, title: 'Lesson', poster_url: null });

        const video = container.querySelector('video');
        expect(video).toHaveAttribute('src', '/api/videos/stream/3#t=1');
        expect(video).toHaveAttribute('preload', 'metadata');
        expect(fetchSpy).not.toHaveBeenCalled();
        fetchSpy.mockRestore();
    });

    it('offers edit and delete only to someone who may manage content', () => {
        renderCard({ id: 3, title: 'Lesson' }, false);
        expect(screen.queryByRole('button', { name: /edit video/i })).toBeNull();
        expect(screen.queryByRole('button', { name: /delete video/i })).toBeNull();
    });

    it('a manager gets both', () => {
        renderCard({ id: 3, title: 'Lesson' }, true);
        expect(screen.getByRole('button', { name: /edit video/i })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /delete video/i })).toBeInTheDocument();
    });
});

describe('VideoPlayerModal', () => {
    it('streams from the API by setting src on the video element', () => {
        const { container } = render(
            <VideoPlayerModal video={{ id: 3, title: 'Lesson', poster_url: '/static/covers/p.jpg' }} onClose={vi.fn()} />,
        );

        const video = container.querySelector('video');
        expect(video).toHaveAttribute('src', '/api/videos/stream/3');
        expect(video).toHaveAttribute('poster', '/static/covers/p.jpg');
        expect(container.querySelector('source')).toBeNull();
    });
});
