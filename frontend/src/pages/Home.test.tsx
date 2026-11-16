import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it } from 'vitest';
import { AuthProvider } from '../context/AuthContext';
import Home from './Home';

const renderHome = () =>
    render(
        <MemoryRouter>
            <AuthProvider>
                <Home />
            </AuthProvider>
        </MemoryRouter>,
    );

beforeEach(() => localStorage.clear());

describe('Home (sign-in page)', () => {
    it('offers one sign-in for every role and no guest entry', () => {
        // Every library endpoint needs an account, so a "continue without
        // signing in" button could only bounce straight back here.
        renderHome();
        expect(screen.getByRole('button', { name: 'Sign In' })).toBeInTheDocument();
        expect(screen.queryByRole('button', { name: /continue as/i })).toBeNull();
    });

    it('"Forgot password?" says who can reset it', async () => {
        renderHome();

        await userEvent.setup().click(screen.getByRole('button', { name: /forgot password/i }));

        expect(screen.getByText(/ask a teacher or the administrator to reset your password/i)).toBeInTheDocument();
    });

    it('labels its inputs for assistive technology and password managers', () => {
        renderHome();
        expect(screen.getByLabelText('Username')).toHaveAttribute('autocomplete', 'username');
        expect(screen.getByLabelText('Password')).toHaveAttribute('autocomplete', 'current-password');
    });

    it('asks for both fields before contacting the server', async () => {
        renderHome();

        await userEvent.setup().click(screen.getByRole('button', { name: 'Sign In' }));

        expect(screen.getByRole('alert')).toHaveTextContent(/enter username and password/i);
    });
});
