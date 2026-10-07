import { afterEach, describe, expect, it, vi } from 'vitest';

const loadApiBase = async (): Promise<string> => {
    vi.resetModules();
    const mod = await import('./config');
    return mod.default;
};

afterEach(() => {
    vi.unstubAllEnvs();
});

describe('config (F6: typed, validated, the only env reader)', () => {
    it("defaults to same-origin '/api' when VITE_API_BASE is unset", async () => {
        vi.stubEnv('VITE_API_BASE', undefined);
        expect(await loadApiBase()).toBe('/api');
    });

    it('honours an absolute VITE_API_BASE override', async () => {
        vi.stubEnv('VITE_API_BASE', 'http://localhost:8000');
        expect(await loadApiBase()).toBe('http://localhost:8000');
    });

    it('rejects a non-URL override at startup', async () => {
        vi.stubEnv('VITE_API_BASE', 'not-a-url');
        await expect(loadApiBase()).rejects.toThrow();
    });
});
