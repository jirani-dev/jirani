import { act, renderHook } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import type { ReactNode } from 'react';
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import type { LoginResponse } from '../types';
import { AuthProvider, useAuth } from './AuthContext';

let logoutHits = 0;

const server = setupServer(
    // Wildcard origin: matches both http://localhost/api/auth/logout (today's
    // config default) and /api/auth/logout (Task 5's same-origin default).
    http.post('*/auth/logout', () => {
        logoutHits += 1;
        return new HttpResponse(null, { status: 200 });
    }),
);

const loginResponse: LoginResponse = {
    access_token: 'tok.student',
    token_type: 'bearer',
    username: 'amina',
    role: 'student',
    first_login: false,
};

const wrapper = ({ children }: { children: ReactNode }) => (
    <AuthProvider>{children}</AuthProvider>
);

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => {
    server.resetHandlers();
    localStorage.clear();
    logoutHits = 0;
});
afterAll(() => server.close());

describe('AuthContext (characterization — pins frontend/AGENTS.md §Backend Integration)', () => {
    it('login stores token, username and role from the response body', () => {
        const { result } = renderHook(() => useAuth(), { wrapper });

        act(() => result.current.login(loginResponse));

        expect(result.current.auth).toEqual({
            access_token: 'tok.student',
            username: 'amina',
            role: 'student',
        });
        expect(JSON.parse(localStorage.getItem('auth') ?? 'null')).toMatchObject({
            access_token: 'tok.student',
            role: 'student',
        });
    });

    it('logout drops the stored token AND calls the cookie-clearing endpoint', async () => {
        localStorage.setItem(
            'auth',
            JSON.stringify({ access_token: 'tok', username: 'u', role: 'student' }),
        );
        const { result } = renderHook(() => useAuth(), { wrapper });

        act(() => result.current.logout());

        expect(localStorage.getItem('auth')).toBeNull();
        expect(result.current.auth).toBeNull();
        await vi.waitFor(() => expect(logoutHits).toBe(1));
    });

    it('restores the session from localStorage on mount', () => {
        localStorage.setItem(
            'auth',
            JSON.stringify({ access_token: 'tok', username: 'u', role: 'teacher' }),
        );
        const { result } = renderHook(() => useAuth(), { wrapper });

        expect(result.current.isTeacher).toBe(true);
        expect(result.current.isAdmin).toBe(false);
        expect(result.current.isGuest).toBe(false);
    });

    it('a fresh visitor is a guest', () => {
        const { result } = renderHook(() => useAuth(), { wrapper });
        expect(result.current.isGuest).toBe(true);
    });
});
