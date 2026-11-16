import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { ChangePasswordModal } from './ChangePasswordModal';
import type { Role } from '../../types';

let requests: unknown[] = [];

const server = setupServer(
    http.post('*/auth/change-password', async ({ request }) => {
        requests.push(await request.json());
        return HttpResponse.json({ message: 'Password changed successfully' });
    }),
);

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => {
    server.resetHandlers();
    requests = [];
});
afterAll(() => server.close());

const open = (role: Role = 'teacher') => {
    const onChanged = vi.fn();
    const onSignOut = vi.fn();
    render(<ChangePasswordModal role={role} onChanged={onChanged} onSignOut={onSignOut} />);
    return { onChanged, onSignOut, user: userEvent.setup() };
};

const fill = async (user: ReturnType<typeof userEvent.setup>, current: string, next: string, confirm = next) => {
    await user.type(screen.getByLabelText(/temporary password/i), current);
    await user.type(screen.getByLabelText(/^new password \(/i), next);
    await user.type(screen.getByLabelText(/new password again/i), confirm);
    await user.click(screen.getByRole('button', { name: /save password/i }));
};

describe('ChangePasswordModal', () => {
    it('sends the old and new password and reports success', async () => {
        const { onChanged, user } = open();

        await fill(user, 'teacher123', 'a-better-secret');

        await waitFor(() => expect(onChanged).toHaveBeenCalledTimes(1));
        expect(requests).toEqual([{ old_password: 'teacher123', new_password: 'a-better-secret' }]);
    });

    it.each<[Role, string, RegExp]>([
        ['teacher', 'short77', /at least 8 characters/i],
        ['admin', 'short77', /at least 8 characters/i],
        ['student', 'abc', /at least 4 characters/i],
    ])('holds a %s to the same minimum length as the API', async (role, tooShort, message) => {
        const { onChanged, user } = open(role);

        await fill(user, 'temporary1', tooShort);

        expect(await screen.findByRole('alert')).toHaveTextContent(message);
        expect(requests).toEqual([]);
        expect(onChanged).not.toHaveBeenCalled();
    });

    it('lets a student use a 4-character password', async () => {
        const { onChanged, user } = open('student');

        await fill(user, 'student123', 'cats');

        await waitFor(() => expect(onChanged).toHaveBeenCalledTimes(1));
    });

    it('rejects a mistyped confirmation before asking the server', async () => {
        const { user } = open();

        await fill(user, 'teacher123', 'a-better-secret', 'a-better-secrte');

        expect(await screen.findByRole('alert')).toHaveTextContent(/do not match/i);
        expect(requests).toEqual([]);
    });

    it('rejects keeping the temporary password', async () => {
        const { user } = open();

        await fill(user, 'teacher123', 'teacher123');

        expect(await screen.findByRole('alert')).toHaveTextContent(/different from the temporary one/i);
        expect(requests).toEqual([]);
    });

    it('shows why the server refused, and stays open', async () => {
        server.use(
            http.post('*/auth/change-password', () =>
                HttpResponse.json({ detail: 'Incorrect current password' }, { status: 400 }),
            ),
        );
        const { onChanged, user } = open();

        await fill(user, 'wrong-guess', 'a-better-secret');

        expect(await screen.findByRole('alert')).toHaveTextContent('Incorrect current password');
        expect(onChanged).not.toHaveBeenCalled();
    });

    it('can be left by signing out, but not dismissed', async () => {
        const { onSignOut, user } = open();

        expect(screen.queryByRole('button', { name: /close|cancel/i })).toBeNull();
        await user.click(screen.getByRole('button', { name: /sign out instead/i }));

        expect(onSignOut).toHaveBeenCalledTimes(1);
    });
});
