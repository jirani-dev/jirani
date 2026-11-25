import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import { AuthProvider } from '../context/AuthContext';
import Home from './Home';

describe('Home (Decision B)', () => {
    it('offers login as the only entry — no unauthenticated guest button', () => {
        render(
            <MemoryRouter>
                <AuthProvider>
                    <Home />
                </AuthProvider>
            </MemoryRouter>,
        );

        expect(screen.getByRole('heading', { name: /offlib llc/i })).toBeInTheDocument();
        expect(screen.queryByRole('button', { name: /continue as student/i })).toBeNull();
    });
});
