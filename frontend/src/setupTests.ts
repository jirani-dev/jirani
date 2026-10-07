import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';

// RTL's automatic cleanup only registers itself when vitest exposes globals
// (`globals: true`). This suite uses explicit vitest imports, so register it.
afterEach(() => {
    cleanup();
});
