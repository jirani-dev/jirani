import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { BookGridCard } from './BookGridCard';
import type { Book } from '../../types';

vi.mock('pdfjs-dist', () => ({ GlobalWorkerOptions: {} }));

const book: Book = { id: 1, uid: 'b1', title: 'Things Fall Apart', extension: 'pdf', created_at: '2026-01-01T00:00:00Z', cover_url: null, tags: [] };

const renderCard = (isAdmin: boolean) =>
    render(
        <MemoryRouter>
            <BookGridCard
                book={book}
                isAdmin={isAdmin}
                onDelete={vi.fn()}
                onEdit={vi.fn()}
            />
        </MemoryRouter>,
    );

describe('BookGridCard role gating', () => {
    it('admin sees edit and delete affordances', () => {
        renderCard(true);
        expect(screen.getByRole('button', { name: /edit book/i })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /delete book/i })).toBeInTheDocument();
    });

    it('student sees no management affordances', () => {
        renderCard(false);
        expect(screen.queryByRole('button', { name: /edit book/i })).toBeNull();
        expect(screen.queryByRole('button', { name: /delete book/i })).toBeNull();
    });
});
