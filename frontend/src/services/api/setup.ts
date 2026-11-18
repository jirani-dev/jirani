// src/services/api/setup.ts
import { api, unwrap } from '../../api/client';

// GET /setup: one-time admin bootstrap. Succeeds once, then permanently
// 403s on every call after (backend sets a REVEALED_FLAG on disk).
export async function runSetup() {
    return unwrap(api.GET('/setup'), 'Setup failed.');
}