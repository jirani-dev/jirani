import { describe, expect, it } from 'vitest';
import { DEFAULT_PAGE_SIZE, pageQuery } from './paging';

describe('pageQuery', () => {
    it('defaults to page 1 and the full backend maximum', () => {
        expect(pageQuery()).toEqual({
            limit: DEFAULT_PAGE_SIZE,
            offset: 0,
        });
    });

    it('converts a 1-based page to a zero-based offset', () => {
        expect(pageQuery({ page: 3, size: 25 })).toEqual({
            limit: 25,
            offset: 50,
        });
    });

    it('clamps size to the backend 1..100 bounds', () => {
        expect(pageQuery({ size: 0 }).limit).toBe(1);
        expect(pageQuery({ size: 999 }).limit).toBe(100);
    });

    it('clamps a page below 1 and ignores non-finite input', () => {
        expect(pageQuery({ page: 0, size: 10 }).offset).toBe(0);
        expect(pageQuery({ page: Number.NaN }).offset).toBe(0);
        expect(pageQuery({ size: Number.NaN }).limit).toBe(DEFAULT_PAGE_SIZE);
    });
});
