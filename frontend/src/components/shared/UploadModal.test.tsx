import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { UploadModal } from './UploadModal';

let uploadHits = 0;
let lastBodyText: string | null = null;

const server = setupServer(
    http.post('*/audio/upload', async ({ request }) => {
        uploadHits += 1;
        // undici's multipart parser asserts on jsdom-realm File objects
        // (`webidl.is.File`), so read the raw body; the multipart part
        // (name + filename + content) is asserted below.
        lastBodyText = await request.text();
        // The client does not validate the response shape; a minimal body is enough.
        return HttpResponse.json({ id: 1 });
    }),
);

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => {
    server.resetHandlers();
    uploadHits = 0;
    lastBodyText = null;
});
afterAll(() => server.close());

describe('UploadModal — single-file audio upload (strict index-access path)', () => {
    it('POSTs the selected file to /audio/upload and reports success', async () => {
        const user = userEvent.setup();
        const onSuccess = vi.fn();
        const onClose = vi.fn();
        render(<UploadModal type="audio" onClose={onClose} onSuccess={onSuccess} />);

        const input = document.querySelector('input[type="file"]');
        if (!(input instanceof HTMLInputElement)) throw new Error('file input not found');
        await user.upload(input, new File(['tone'], 'a.mp3', { type: 'audio/mpeg' }));

        await user.click(screen.getByRole('button', { name: /upload/i }));

        await waitFor(() => expect(uploadHits).toBe(1));
        expect(lastBodyText).toContain('name="file"');
        // undici serializes the jsdom-realm File as a generic Blob (filename
        // "blob"), so the file's type is the stable cross-realm assertion.
        expect(lastBodyText).toContain('Content-Type: audio/mpeg');
        await waitFor(() => expect(onSuccess).toHaveBeenCalledTimes(1));
        expect(onClose).toHaveBeenCalledTimes(1);
    });
});
