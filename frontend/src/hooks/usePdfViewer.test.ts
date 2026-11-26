import { act, renderHook, waitFor } from '@testing-library/react';
import * as pdfjsLib from 'pdfjs-dist';
import type { PDFDocumentProxy, RenderTask } from 'pdfjs-dist';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fetchBookFile } from '../services/api/books';
import { usePdfViewer } from './usePdfViewer';

vi.mock('pdfjs-dist', () => ({ GlobalWorkerOptions: {}, getDocument: vi.fn() }));
vi.mock('../services/api/books', () => ({ fetchBookFile: vi.fn() }));

const deferred = <T,>() => {
    let resolve!: (value: T) => void;
    let reject!: (reason: unknown) => void;
    const promise = new Promise<T>((res, rej) => {
        resolve = res;
        reject = rej;
    });
    return { promise, resolve, reject };
};

const finishedTask = (): RenderTask =>
    ({ promise: Promise.resolve(), cancel: vi.fn() }) as unknown as RenderTask;

// A render task the test finishes by hand; cancel() rejects it the way pdf.js does.
const heldTask = () => {
    const done = deferred<void>();
    const cancel = vi.fn(() =>
        done.reject({ name: 'RenderingCancelledException', message: 'Rendering cancelled' }),
    );
    const task = { promise: done.promise, cancel } as unknown as RenderTask;
    return { task, cancel, finish: () => done.resolve() };
};

// A page is 100 x 200 at scale 1.
const fakePage = () => ({
    getViewport: ({ scale }: { scale: number }) => ({ width: 100 * scale, height: 200 * scale }),
    render: vi.fn((): RenderTask => finishedTask()),
});
type FakePage = ReturnType<typeof fakePage>;

const fakeDocument = (page: FakePage, numPages = 3) => ({
    numPages,
    getPage: vi.fn((): Promise<FakePage> => Promise.resolve(page)),
    destroy: vi.fn((): Promise<void> => Promise.resolve()),
});
type FakeDocument = ReturnType<typeof fakeDocument>;

const loadingTask = (promise: Promise<unknown>) =>
    ({ promise }) as unknown as ReturnType<typeof pdfjsLib.getDocument>;

const serve = (doc: FakeDocument) =>
    vi.mocked(pdfjsLib.getDocument).mockImplementation(() =>
        loadingTask(Promise.resolve(doc as unknown as PDFDocumentProxy)),
    );

const reader = () => {
    const canvas = { width: 0, height: 0, getContext: () => ({}) } as unknown as HTMLCanvasElement;
    const container = { clientWidth: 800, clientHeight: 500 } as unknown as HTMLDivElement;
    return { canvas, container, canvasRef: { current: canvas }, containerRef: { current: container } };
};

const bytes = new ArrayBuffer(8);

beforeEach(() => {
    vi.mocked(pdfjsLib.getDocument).mockReset();
    vi.mocked(fetchBookFile).mockReset().mockResolvedValue(bytes);
});

describe('usePdfViewer', () => {
    it('loads the book, fits page 1 to the reader and renders it', async () => {
        const page = fakePage();
        serve(fakeDocument(page));
        const { canvas, canvasRef, containerRef } = reader();

        const { result } = renderHook(() => usePdfViewer('bk1', containerRef, canvasRef));

        await waitFor(() => expect(page.render).toHaveBeenCalledTimes(1));
        await waitFor(() => expect(result.current.rendering).toBe(false));
        expect(result.current).toMatchObject({ loading: false, error: null, currentPage: 1, totalPages: 3 });
        expect(fetchBookFile).toHaveBeenCalledWith('bk1');
        const scale = result.current.scale ?? Number.NaN;
        expect(scale).toBeGreaterThan(0);
        expect(canvas.width).toBe(100 * scale);
    });

    // GHSA-wgrm-67xf-hhpq: with eval allowed, pdf.js 3.x runs script hidden in a
    // crafted font. Books are uploaded by staff and opened by every reader.
    it('never lets pdf.js evaluate code from the file', async () => {
        serve(fakeDocument(fakePage()));
        const { canvasRef, containerRef } = reader();

        renderHook(() => usePdfViewer('bk1', containerRef, canvasRef));

        await waitFor(() => expect(pdfjsLib.getDocument).toHaveBeenCalledTimes(1));
        expect(vi.mocked(pdfjsLib.getDocument).mock.calls[0]).toEqual([
            { data: bytes, isEvalSupported: false },
        ]);
    });

    it('reports a file pdf.js cannot open instead of spinning forever', async () => {
        vi.mocked(pdfjsLib.getDocument).mockImplementation(() =>
            loadingTask(Promise.reject(new Error('Invalid PDF structure'))),
        );
        const { canvasRef, containerRef } = reader();

        const { result } = renderHook(() => usePdfViewer('bk1', containerRef, canvasRef));

        await waitFor(() => expect(result.current.loading).toBe(false));
        expect(result.current.error).toBe('Failed to load book: Invalid PDF structure');
    });

    it('reports a failed download instead of spinning forever', async () => {
        vi.mocked(fetchBookFile).mockRejectedValue(new Error('Failed to fetch book (404)'));
        const { canvasRef, containerRef } = reader();

        const { result } = renderHook(() => usePdfViewer('bk1', containerRef, canvasRef));

        await waitFor(() => expect(result.current.loading).toBe(false));
        expect(result.current.error).toBe('Failed to load book: Failed to fetch book (404)');
        expect(pdfjsLib.getDocument).not.toHaveBeenCalled();
    });

    it('discards a render that a newer one replaced while it waited for its page', async () => {
        const page = fakePage();
        const doc = fakeDocument(page);
        const pageForFirstRender = deferred<FakePage>();
        doc.getPage
            .mockImplementationOnce(() => Promise.resolve(page)) // measuring page 1 to fit it
            .mockImplementationOnce(() => pageForFirstRender.promise);
        serve(doc);
        const { canvas, canvasRef, containerRef } = reader();
        const { result } = renderHook(() => usePdfViewer('bk1', containerRef, canvasRef));
        await waitFor(() => expect(doc.getPage).toHaveBeenCalledTimes(2));
        expect(result.current.rendering).toBe(true);
        const fitted = result.current.scale;

        act(() => result.current.zoom(1));
        await waitFor(() => expect(page.render).toHaveBeenCalledTimes(1));
        await waitFor(() => expect(result.current.rendering).toBe(false));
        const zoomed = result.current.scale ?? Number.NaN;
        expect(zoomed).not.toBe(fitted);

        // The replaced render gets its page only now, after the newer one drew.
        await act(async () => pageForFirstRender.resolve(page));

        expect(page.render).toHaveBeenCalledTimes(1);
        expect(canvas.width).toBe(100 * zoomed);
        expect(result.current).toMatchObject({ rendering: false, error: null });
    });

    it('cancels the drawing a newer render replaces, without reporting the cancellation', async () => {
        const page = fakePage();
        const first = heldTask();
        page.render.mockImplementationOnce(() => first.task);
        serve(fakeDocument(page));
        const { canvas, canvasRef, containerRef } = reader();
        const { result } = renderHook(() => usePdfViewer('bk1', containerRef, canvasRef));
        await waitFor(() => expect(page.render).toHaveBeenCalledTimes(1));

        act(() => result.current.zoom(1));

        await waitFor(() => expect(page.render).toHaveBeenCalledTimes(2));
        await waitFor(() => expect(result.current.rendering).toBe(false));
        expect(first.cancel).toHaveBeenCalledTimes(1);
        expect(result.current.error).toBeNull();
        expect(canvas.width).toBe(100 * (result.current.scale ?? Number.NaN));
    });

    it('turns pages inside the book, one render at a time', async () => {
        const page = fakePage();
        const first = heldTask();
        page.render.mockImplementationOnce(() => first.task);
        const doc = fakeDocument(page);
        serve(doc);
        const { canvasRef, containerRef } = reader();
        const { result } = renderHook(() => usePdfViewer('bk1', containerRef, canvasRef));
        await waitFor(() => expect(page.render).toHaveBeenCalledTimes(1));

        act(() => result.current.goTo(2));
        expect(result.current.currentPage).toBe(1);

        await act(async () => first.finish());
        expect(result.current.rendering).toBe(false);
        act(() => result.current.goTo(2));
        await waitFor(() => expect(page.render).toHaveBeenCalledTimes(2));
        expect(result.current.currentPage).toBe(2);
        expect(doc.getPage).toHaveBeenLastCalledWith(2);

        await waitFor(() => expect(result.current.rendering).toBe(false));
        act(() => result.current.goTo(0));
        act(() => result.current.goTo(4));
        expect(result.current.currentPage).toBe(2);
    });

    it('fits the page again when the reader is resized', async () => {
        const page = fakePage();
        serve(fakeDocument(page));
        const { canvasRef, container, containerRef } = reader();
        const { result } = renderHook(() => usePdfViewer('bk1', containerRef, canvasRef));
        await waitFor(() => expect(page.render).toHaveBeenCalledTimes(1));
        const before = result.current.scale;

        Object.assign(container, { clientWidth: 1600, clientHeight: 1000 });
        act(() => {
            window.dispatchEvent(new Event('resize'));
        });

        await waitFor(() => expect(result.current.scale).not.toBe(before));
        await waitFor(() => expect(page.render).toHaveBeenCalledTimes(2));
    });

    it('on unmount, destroys the document and stops listening for resizes', async () => {
        const added = vi.spyOn(window, 'addEventListener');
        const removed = vi.spyOn(window, 'removeEventListener');
        const page = fakePage();
        const doc = fakeDocument(page);
        serve(doc);
        const { canvasRef, containerRef } = reader();
        const { result, unmount } = renderHook(() => usePdfViewer('bk1', containerRef, canvasRef));
        await waitFor(() => expect(page.render).toHaveBeenCalledTimes(1));
        await waitFor(() => expect(result.current.rendering).toBe(false));

        unmount();

        expect(doc.destroy).toHaveBeenCalledTimes(1);
        const resizeListeners = (spy: typeof added | typeof removed) =>
            new Set(spy.mock.calls.filter(([type]) => type === 'resize').map(([, listener]) => listener));
        expect(resizeListeners(added).size).toBeGreaterThan(0);
        expect(resizeListeners(removed)).toEqual(resizeListeners(added));
        added.mockRestore();
        removed.mockRestore();
    });

    it('destroys a document that finishes loading after the reader closed', async () => {
        const doc = fakeDocument(fakePage());
        const pending = deferred<PDFDocumentProxy>();
        vi.mocked(pdfjsLib.getDocument).mockImplementation(() => loadingTask(pending.promise));
        const { canvasRef, containerRef } = reader();
        const { unmount } = renderHook(() => usePdfViewer('bk1', containerRef, canvasRef));
        await waitFor(() => expect(pdfjsLib.getDocument).toHaveBeenCalledTimes(1));

        unmount();
        await act(async () => pending.resolve(doc as unknown as PDFDocumentProxy));

        expect(doc.destroy).toHaveBeenCalledTimes(1);
        expect(doc.getPage).not.toHaveBeenCalled();
    });

    it('releases the previous book when the reader moves to another one mid-render', async () => {
        const firstPage = fakePage();
        const stillDrawing = heldTask();
        firstPage.render.mockImplementationOnce(() => stillDrawing.task);
        const firstDoc = fakeDocument(firstPage);
        const secondPage = fakePage();
        const secondDoc = fakeDocument(secondPage, 5);
        vi.mocked(pdfjsLib.getDocument)
            .mockImplementationOnce(() => loadingTask(Promise.resolve(firstDoc as unknown as PDFDocumentProxy)))
            .mockImplementationOnce(() => loadingTask(Promise.resolve(secondDoc as unknown as PDFDocumentProxy)));
        const { canvasRef, containerRef } = reader();
        const { result, rerender } = renderHook(
            ({ uid }) => usePdfViewer(uid, containerRef, canvasRef),
            { initialProps: { uid: 'bk1' } },
        );
        await waitFor(() => expect(firstPage.render).toHaveBeenCalledTimes(1));

        rerender({ uid: 'bk2' });

        await waitFor(() => expect(secondPage.render).toHaveBeenCalledTimes(1));
        await waitFor(() => expect(result.current.rendering).toBe(false));
        expect(result.current).toMatchObject({ totalPages: 5, currentPage: 1, error: null });
        expect(fetchBookFile).toHaveBeenLastCalledWith('bk2');
        // The first book's drawing was stopped, not reported as a failure.
        expect(stillDrawing.cancel).toHaveBeenCalledTimes(1);
        expect(firstDoc.destroy).toHaveBeenCalledTimes(1);
        expect(secondDoc.destroy).not.toHaveBeenCalled();
    });
    it('a replaced render does not end the render that replaced it', async () => {
        const page = fakePage();
        const first = heldTask();
        const second = heldTask();
        page.render.mockImplementationOnce(() => first.task).mockImplementationOnce(() => second.task);
        serve(fakeDocument(page));
        const { canvasRef, containerRef } = reader();
        const { result } = renderHook(() => usePdfViewer('bk1', containerRef, canvasRef));
        await waitFor(() => expect(page.render).toHaveBeenCalledTimes(1));

        act(() => result.current.zoom(1));
        await waitFor(() => expect(page.render).toHaveBeenCalledTimes(2));

        // The first drawing was cancelled and has settled; the second still draws.
        expect(first.cancel).toHaveBeenCalledTimes(1);
        expect(result.current.rendering).toBe(true);
        act(() => result.current.goTo(2));
        expect(result.current.currentPage).toBe(1);

        await act(async () => second.finish());
        expect(result.current.rendering).toBe(false);
    });

    it('a replaced render that wakes late leaves the newer drawing cancellable', async () => {
        const page = fakePage();
        const doc = fakeDocument(page);
        const pageForFirstRender = deferred<FakePage>();
        doc.getPage
            .mockImplementationOnce(() => Promise.resolve(page)) // measuring page 1 to fit it
            .mockImplementationOnce(() => pageForFirstRender.promise);
        const second = heldTask();
        page.render.mockImplementationOnce(() => second.task);
        serve(doc);
        const { canvasRef, containerRef } = reader();
        const { result } = renderHook(() => usePdfViewer('bk1', containerRef, canvasRef));
        await waitFor(() => expect(doc.getPage).toHaveBeenCalledTimes(2));

        act(() => result.current.zoom(1));
        await waitFor(() => expect(page.render).toHaveBeenCalledTimes(1));
        await act(async () => pageForFirstRender.resolve(page));

        act(() => result.current.zoom(1));
        await waitFor(() => expect(page.render).toHaveBeenCalledTimes(2));
        expect(second.cancel).toHaveBeenCalledTimes(1);
    });
});
