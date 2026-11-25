import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AuthProvider } from '../context/AuthContext';
import Library from './Library';

vi.mock('pdfjs-dist', () => ({ GlobalWorkerOptions: {} }));

vi.mock('../hooks/useBookSearch', () => ({
    bookKeys: { all: ['books'] },
    useBookSearch: () => ({
        data: { items: [], total: 0, limit: 100, offset: 0 },
        isLoading: false,
    }),
    useBookTags: () => ({
        data: { items: [], total: 0, limit: 100, offset: 0 },
    }),
}));
vi.mock('../hooks/useVideos', () => ({
    videoKeys: { all: ['videos'] },
    useVideos: () => ({ data: [], isLoading: false }),
}));
vi.mock('../hooks/useAudio', () => ({
    audioKeys: { all: ['audio'] },
    useAudio: () => ({ data: [], isLoading: false }),
}));
vi.mock('../components/shared/UploadModal', () => ({
    UploadModal: ({ onSuccess }: { onSuccess: () => void }) => (
        <button onClick={onSuccess}>finish upload</button>
    ),
}));

const makeClient = () =>
    new QueryClient({ defaultOptions: { queries: { retry: false } } });

const renderLibrary = (client: QueryClient = makeClient()) =>
    render(
        <QueryClientProvider client={client}>
            <MemoryRouter>
                <AuthProvider>
                    <Library />
                </AuthProvider>
            </MemoryRouter>
        </QueryClientProvider>,
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

describe('Library server state', () => {
    it('invalidates books, videos and audio after an upload succeeds', async () => {
        localStorage.setItem(
            'auth',
            JSON.stringify({ access_token: 't', username: 'admin', role: 'admin' }),
        );
        const client = makeClient();
        const invalidate = vi.spyOn(client, 'invalidateQueries');
        renderLibrary(client);

        await userEvent.click(await screen.findByRole('button', { name: /upload book/i }));
        await userEvent.click(screen.getByRole('button', { name: /finish upload/i }));

        expect(invalidate).toHaveBeenCalledWith({ queryKey: ['books'] });
        expect(invalidate).toHaveBeenCalledWith({ queryKey: ['videos'] });
        expect(invalidate).toHaveBeenCalledWith({ queryKey: ['audio'] });
    });
});
