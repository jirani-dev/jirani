import { z } from 'zod';

// F6: this module is the only reader of import.meta.env, and it validates at
// startup. Default is the same-origin relative base — the locked topology
// serves the SPA and the API from one nginx (:80), and a relative base is the
// only default that works for LAN clients (an absolute http://localhost/...
// would point every client at its own machine).
const envSchema = z.object({
    // Optional override for the backend-container-less dev flow only.
    VITE_API_BASE: z.string().url().optional(),
});

const env = envSchema.parse({
    VITE_API_BASE: import.meta.env.VITE_API_BASE,
});

const API_BASE: string = env.VITE_API_BASE ?? '/api';

export default API_BASE;
