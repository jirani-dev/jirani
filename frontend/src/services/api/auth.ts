// src/services/api/auth.ts
import { apiFetch, parseErrorDetail } from './client';
import { LoginResponse } from '../../types';

export async function login(username: string, password: string): Promise<LoginResponse> {
    const res = await apiFetch('/auth/token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
    });
    if (!res.ok) throw new Error(await parseErrorDetail(res, 'Invalid username or password.'));
    return res.json();
}

export async function changePassword(oldPassword: string, newPassword: string): Promise<void> {
    const res = await apiFetch('/auth/change-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
    });
    if (!res.ok) throw new Error(await parseErrorDetail(res, 'Failed to change password.'));
}

// signup / admin-exists / make-admin / forgot-password-verify-code have no
// matching backend route yet — intentionally left out, not guessed.