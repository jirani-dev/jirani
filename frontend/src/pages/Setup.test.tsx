import { StrictMode } from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest';
import Setup from './Setup';

const CREDENTIALS =
    'Admin credentials - Username: admin, Password: s3cret-pw. Please change the password after first login.';

// Same contract as the backend: the first call reveals, every later one is a 403.
let setupHits = 0;
const server = setupServer(
    http.get('*/setup', () => {
        setupHits += 1;
        return setupHits === 1
            ? HttpResponse.json({ message: CREDENTIALS })
            : HttpResponse.json(
                { detail: 'admin credentials have already been revealed.' },
                { status: 403 },
            );
    }),
);

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => {
    server.resetHandlers();
    setupHits = 0;
});
afterAll(() => server.close());

const renderSetup = () =>
    render(
        <StrictMode>
            <MemoryRouter>
                <Setup />
            </MemoryRouter>
        </StrictMode>,
    );

describe('Setup page', () => {
    it('asks for the one-time credentials once, even though StrictMode mounts twice', async () => {
        renderSetup();

        expect(await screen.findByText(CREDENTIALS)).toBeInTheDocument();
        // Let a second, unwanted request land if one was sent.
        await new Promise(resolve => setTimeout(resolve, 50));

        expect(setupHits).toBe(1);
        expect(screen.getByText(CREDENTIALS)).toBeInTheDocument();
        expect(screen.queryByText(/setup already complete/i)).toBeNull();
    });

    it('says so when setup was already completed', async () => {
        setupHits = 1;
        renderSetup();

        expect(await screen.findByText(/setup already complete/i)).toBeInTheDocument();
        expect(screen.queryByText(CREDENTIALS)).toBeNull();
    });
});
