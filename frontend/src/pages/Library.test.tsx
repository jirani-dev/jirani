import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AuthProvider } from '../context/AuthContext';
import Library from './Library';

vi.mock('../hooks/useBookSearch', () => ({
    useBookSearch: () => ({
        books: [],
        total: 0,
        refresh: vi.fn().mockResolvedValue(undefined),
        setBooks: vi.fn(),
    }),
}));
vi.mock('../hooks/useVideos', () => ({
    useVideos: () => ({
        videos: [],
        refresh: vi.fn().mockResolvedValue(undefined),
        setVideos: vi.fn(),
    }),
}));
vi.mock('../hooks/useAudio', () => ({
    useAudio: () => ({
        audioTracks: [],
        refresh: vi.fn().mockResolvedValue(undefined),
        setAudioTracks: vi.fn(),
    }),
}));
vi.mock('../services/api/books', () => ({
    searchBooks: vi
        .fn()
        .mockResolvedValue({ items: [], total: 0, limit: 100, offset: 0 }),
}));

const renderLibrary = () =>
    render(
        <MemoryRouter>
            <AuthProvider>
                <Library />
            </AuthProvider>
        </MemoryRouter>,
    );

beforeEach(() => localStorage.clear());

describe('Library role gating', () => {
    it('admin sees Add Teacher and Upload', async () => {
        localStorage.setItem(
            'auth',
            JSON.stringify({ access_token: 't', username: 'admin', role: 'admin' }),
        );
        renderLibrary();
        expect(await screen.findByRole('button', { name: /add teacher/i })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /upload book/i })).toBeInTheDocument();
    });

    it('student sees neither control', async () => {
        localStorage.setItem(
            'auth',
            JSON.stringify({ access_token: 't', username: 'student', role: 'student' }),
        );
        renderLibrary();
        await screen.findByText(/no books yet/i);
        expect(screen.queryByRole('button', { name: /add teacher/i })).toBeNull();
        expect(screen.queryByRole('button', { name: /upload book/i })).toBeNull();
    });
});
