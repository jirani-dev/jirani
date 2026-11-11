import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it } from 'vitest';
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

beforeEach(() => localStorage.clear());

describe('App routing', () => {
    it('renders the login page at /', () => {
        renderAt('/');
        expect(
            screen.getByRole('heading', { name: /offlib llc/i }),
        ).toBeInTheDocument();
    });

    it('/video is not a route', () => {
        const { container } = renderAt('/video');
        expect(container).toBeEmptyDOMElement();
    });

    // Every library endpoint answers 401 to a guest, so these pages would only
    // flash and bounce back; the router sends guests to sign in directly.
    it.each(['/library', '/read/some-book'])('sends a guest who opens %s to the sign-in page', (path) => {
        renderAt(path);
        expect(
            screen.getByRole('heading', { name: /offlib llc/i }),
        ).toBeInTheDocument();
    });
});
