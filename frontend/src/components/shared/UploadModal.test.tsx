import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { UploadModal } from './UploadModal';

// One entry per request received, in order.
let uploadBodies: string[] = [];

const server = setupServer(
    http.post('*/audio/upload', async ({ request }) => {
        // undici's multipart parser asserts on jsdom-realm File objects
        // (`webidl.is.File`), so read the raw body; the multipart parts
        // (name + content) are asserted below.
        uploadBodies.push(await request.text());
        // The client does not validate the response shape; a minimal body is enough.
        return HttpResponse.json({ id: uploadBodies.length });
    }),
);

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => {
    server.resetHandlers();
    uploadBodies = [];
});
afterAll(() => server.close());

// undici serialises a jsdom-realm File as an anonymous Blob, so neither the
// file name nor its bytes survive into the request text; the MIME type does,
// and is what tells two files apart below.
const track = (name: string, type: string) => new File(['tone'], name, { type });

const fileInput = (): HTMLInputElement => {
    const input = document.querySelector('input[type="file"]');
    if (!(input instanceof HTMLInputElement)) throw new Error('file input not found');
    return input;
};

describe('UploadModal — single-file audio upload (strict index-access path)', () => {
    it('POSTs the selected file to /audio/upload and reports success', async () => {
        const user = userEvent.setup();
        const onSuccess = vi.fn();
        const onClose = vi.fn();
        render(<UploadModal type="audio" onClose={onClose} onSuccess={onSuccess} />);

        await user.upload(fileInput(), track('a.mp3', 'audio/mpeg'));

        await user.click(screen.getByRole('button', { name: /upload/i }));

        await waitFor(() => expect(uploadBodies).toHaveLength(1));
        expect(uploadBodies[0]).toContain('name="file"');
        // undici serializes the jsdom-realm File as a generic Blob (filename
        // "blob"), so the file's type is the stable cross-realm assertion.
        expect(uploadBodies[0]).toContain('Content-Type: audio/mpeg');
        await waitFor(() => expect(onSuccess).toHaveBeenCalledTimes(1));
        expect(onClose).toHaveBeenCalledTimes(1);
    });
});

describe('UploadModal — several files', () => {
    it('sends one request per file and puts the tags on every one', async () => {
        // The batch endpoint has no tags field, so tags typed for several
        // audio or video files used to be dropped without a word.
        const user = userEvent.setup();
        const onSuccess = vi.fn();
        const onClose = vi.fn();
        render(<UploadModal type="audio" onClose={onClose} onSuccess={onSuccess} />);

        await user.upload(fileInput(), [track('a.mp3', 'audio/mpeg'), track('b.wav', 'audio/wav')]);
        await user.type(screen.getByPlaceholderText(/history, science/i), 'math');
        await user.click(screen.getByRole('button', { name: /upload/i }));

        await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
        expect(uploadBodies).toHaveLength(2);
        expect(uploadBodies[0]).toContain('Content-Type: audio/mpeg');
        expect(uploadBodies[1]).toContain('Content-Type: audio/wav');
        for (const body of uploadBodies) {
            expect(body).toMatch(/name="tags"\r\n\r\nmath\r\n/);
        }
        expect(onSuccess).toHaveBeenCalledTimes(1);
    });

    it('after a partial failure keeps only the failed file, so a retry cannot duplicate the rest', async () => {
        server.use(
            http.post('*/audio/upload', async ({ request }) => {
                const body = await request.text();
                uploadBodies.push(body);
                // The .wav is refused the first time round and accepted on the retry.
                return body.includes('Content-Type: audio/wav') && uploadBodies.length <= 2
                    ? HttpResponse.json({ detail: 'Invalid media file' }, { status: 400 })
                    : HttpResponse.json({ id: uploadBodies.length });
            }),
        );
        const user = userEvent.setup();
        const onSuccess = vi.fn();
        const onClose = vi.fn();
        render(<UploadModal type="audio" onClose={onClose} onSuccess={onSuccess} />);

        await user.upload(fileInput(), [track('a.mp3', 'audio/mpeg'), track('b.wav', 'audio/wav')]);
        await user.click(screen.getByRole('button', { name: /upload/i }));

        // The stored file is announced (so the list refreshes) but the dialog stays.
        expect(await screen.findByText('1 of 2 files were not uploaded: Invalid media file')).toBeInTheDocument();
        expect(onSuccess).toHaveBeenCalledTimes(1);
        expect(onClose).not.toHaveBeenCalled();
        expect(screen.getByText('b.wav')).toBeInTheDocument();
        expect(screen.queryByText('a.mp3')).toBeNull();

        await user.click(screen.getByRole('button', { name: /upload/i }));

        await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
        expect(uploadBodies).toHaveLength(3);
        expect(uploadBodies[2]).toContain('Content-Type: audio/wav');
        expect(uploadBodies.filter(body => body.includes('Content-Type: audio/mpeg'))).toHaveLength(1);
    });

    it('shows the plain reason when the only file fails', async () => {
        server.use(
            http.post('*/audio/upload', () =>
                HttpResponse.json({ detail: 'File type .txt not allowed' }, { status: 400 }),
            ),
        );
        const user = userEvent.setup();
        const onSuccess = vi.fn();
        const onClose = vi.fn();
        render(<UploadModal type="audio" onClose={onClose} onSuccess={onSuccess} />);

        await user.upload(fileInput(), track('a.mp3', 'audio/mpeg'));
        await user.click(screen.getByRole('button', { name: /upload/i }));

        expect(await screen.findByText('File type .txt not allowed')).toBeInTheDocument();
        expect(onSuccess).not.toHaveBeenCalled();
        expect(onClose).not.toHaveBeenCalled();
    });
});
