import { render, screen } from '@testing-library/react';
import { BookOpen } from 'lucide-react';
import { describe, expect, it, vi } from 'vitest';
import { EmptyState } from './EmptyState';

describe('EmptyState role gating', () => {
    it('a manager (admin or teacher) sees the add action', () => {
        render(
            <EmptyState
                icon={BookOpen}
                label="books"
                onUpload={vi.fn()}
                canManage
            />,
        );
        expect(screen.getByRole('button', { name: /add books/i })).toBeInTheDocument();
    });

    it('student sees guidance but no add action', () => {
        render(
            <EmptyState
                icon={BookOpen}
                label="books"
                onUpload={vi.fn()}
                canManage={false}
            />,
        );
        expect(screen.queryByRole('button', { name: /add books/i })).toBeNull();
        expect(screen.getByText(/nothing here yet/i)).toBeInTheDocument();
    });
});
