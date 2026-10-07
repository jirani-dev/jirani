import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import App from './App';
import { AuthProvider } from './context/AuthContext';

const renderAt = (path: string) =>
    render(
        <MemoryRouter initialEntries={[path]}>
            <AuthProvider>
                <App />
            </AuthProvider>
        </MemoryRouter>,
    );

describe('App routing', () => {
    it('renders the login page at /', () => {
        renderAt('/');
        expect(
            screen.getByRole('heading', { name: /offlib llc/i }),
        ).toBeInTheDocument();
    });

    it('/video is no longer a route (Decision A)', () => {
        renderAt('/video');
        expect(
            screen.queryByRole('heading', { name: /offlib llc/i }),
        ).toBeNull();
    });
});
