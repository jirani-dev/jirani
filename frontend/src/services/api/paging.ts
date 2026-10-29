// Backend bounds: book_router.py Query(limit, ge=1, le=100), Query(offset, ge=0).
export const DEFAULT_PAGE_SIZE = 100;
export const MAX_PAGE_SIZE = 100;

export interface PageRequest {
    page?: number;
    size?: number;
}

export interface PageQuery {
    limit: number;
    offset: number;
}

export function pageQuery({
    page = 1,
    size = DEFAULT_PAGE_SIZE,
}: PageRequest = {}): PageQuery {
    const safePage = Number.isFinite(page) ? Math.max(1, Math.trunc(page)) : 1;
    const safeSize = Number.isFinite(size)
        ? Math.min(MAX_PAGE_SIZE, Math.max(1, Math.trunc(size)))
        : DEFAULT_PAGE_SIZE;

    return { limit: safeSize, offset: (safePage - 1) * safeSize };
}
