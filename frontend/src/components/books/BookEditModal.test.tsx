import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { BookEditModal } from './BookEditModal';
import type { Book } from '../../types';

let bodies: string[] = [];

const server = setupServer(
    http.put('*/books/b1', async ({ request }) => {
        // Raw multipart text: field names and values are what matter here.
        bodies.push(await request.text());
        return HttpResponse.json({ uid: 'b1', title: 'Saved', extension: 'pdf', tags: [] });
    }),
);

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => {
    server.resetHandlers();
    bodies = [];
});
afterAll(() => server.close());

const book: Book = {
    uid: 'b1',
    title: 'Things Fall Apart',
    extension: 'pdf',
    tags: [{ id: 1, name: 'history' }, { id: 2, name: 'fiction' }],
};

const open = () => {
    const onUpdate = vi.fn();
    const onClose = vi.fn();
    render(<BookEditModal book={book} onClose={onClose} onUpdate={onUpdate} />);
    return { onUpdate, onClose, user: userEvent.setup() };
};

describe('BookEditModal', () => {
    it('starts from the book\'s current title and tags', () => {
        open();
        expect(screen.getByPlaceholderText(/book title/i)).toHaveValue('Things Fall Apart');
        expect(screen.getByPlaceholderText(/history, science/i)).toHaveValue('history, fiction');
    });

    it('a rename does not send the tags field, so the tags are left alone', async () => {
        // An empty tags field means "remove every tag" to the API.
        const { onUpdate, user } = open();

        const title = screen.getByPlaceholderText(/book title/i);
        await user.clear(title);
        await user.type(title, 'Renamed');
        await user.click(screen.getByRole('button', { name: /save/i }));

        await waitFor(() => expect(onUpdate).toHaveBeenCalledTimes(1));
        expect(bodies[0]).toMatch(/name="title"\r\n\r\nRenamed\r\n/);
        expect(bodies[0]).not.toContain('name="tags"');
    });

    it('emptying the tags box sends an empty tags field, which clears them', async () => {
        const { onUpdate, user } = open();

        await user.clear(screen.getByPlaceholderText(/history, science/i));
        await user.click(screen.getByRole('button', { name: /save/i }));

        await waitFor(() => expect(onUpdate).toHaveBeenCalledTimes(1));
        expect(bodies[0]).toMatch(/name="tags"\r\n\r\n\r\n/);
    });

    it('shows the server\'s reason when the save is refused', async () => {
        server.use(
            http.put('*/books/b1', () =>
                HttpResponse.json({ detail: 'Invalid book data' }, { status: 400 }),
            ),
        );
        const { onUpdate, onClose, user } = open();

        await user.click(screen.getByRole('button', { name: /save/i }));

        expect(await screen.findByText('Invalid book data')).toBeInTheDocument();
        expect(onUpdate).not.toHaveBeenCalled();
        expect(onClose).not.toHaveBeenCalled();
    });
});
