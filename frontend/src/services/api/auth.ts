// src/services/api/auth.ts
import { api, unwrap } from '../../api/client';
import { Role } from '../../types';

export async function login(username: string, password: string) {
    return unwrap(
        api.POST('/auth/token', { body: { username, password } }),
        'Invalid username or password.',
    );
}

// Clears the access_token cookie server-side (localStorage/context state
// is the caller's job, see AuthContext.logout). Best-effort: logging out
// must still work from the user's point of view even if this call fails.
export async function logout(): Promise<void> {
    await api.POST('/auth/logout').catch(() => {});
}

export async function changePassword(oldPassword: string, newPassword: string): Promise<void> {
    await unwrap(
        api.POST('/auth/change-password', {
            body: { old_password: oldPassword, new_password: newPassword },
        }),
        'Failed to change password.',
    );
}

export interface CreateUserRequest {
    username: string;
    first_name: string;
    last_name: string;
    role: Role;
}

export interface CreateUserResponse {
    username: string;
    credential: string;
}

// Maps to POST /auth/users. Caller must already be admin/teacher
// (enforced server-side via RoleChecker). Admin accounts cannot be
// created through this endpoint, only student/teacher.
export async function createUser(data: CreateUserRequest) {
    return unwrap(api.POST('/auth/users', { body: data }), 'Failed to create account.');
}

// No backend route for OTP/forgot-password or self-signup. First-admin
// bootstrap happens once via GET /setup (server-side, not from this UI).