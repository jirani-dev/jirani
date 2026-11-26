// src/services/api/setup.ts
import { api, unwrap } from '../../api/client';

export interface SetupResponse {
    message: string;
}

// GET /setup — one-time admin bootstrap. Succeeds once, then permanently
// 403s on every call after (backend sets a REVEALED_FLAG on disk).
export async function runSetup(): Promise<SetupResponse> {
    const data = await unwrap(api.GET('/setup'), 'Setup failed.');
    return { message: data.message ?? '' };
}
