import { fireEvent, render } from '@testing-library/react';
import { createRef } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { PdfCanvas } from './PdfCanvas';

// jsdom-free Touch fixtures: handlers only read clientX/clientY, so a cast
// (isolated to this helper) is the pragmatic typed shape.
const touch = (clientX: number, clientY = 0) =>
    ({ clientX, clientY, identifier: 0 }) as unknown as Touch;

const setup = () => {
    const onSwipeNext = vi.fn();
    const onSwipePrev = vi.fn();
    const { container } = render(
        <PdfCanvas
            containerRef={createRef<HTMLDivElement>()}
            canvasRef={createRef<HTMLCanvasElement>()}
            loading={false}
            error={null}
            rendering={false}
            onSwipeNext={onSwipeNext}
            onSwipePrev={onSwipePrev}
        />,
    );
    const surface = container.firstElementChild as HTMLElement;
    return { surface, onSwipeNext, onSwipePrev };
};

describe('PdfCanvas swipe handling', () => {
    it('swipe left (dx < -40) advances to the next page', () => {
        const { surface, onSwipeNext } = setup();
        fireEvent.touchStart(surface, { touches: [touch(200, 10)] });
        fireEvent.touchEnd(surface, { changedTouches: [touch(100, 10)] });
        expect(onSwipeNext).toHaveBeenCalledTimes(1);
    });

    it('swipe right (dx > +40) returns to the previous page', () => {
        const { surface, onSwipePrev } = setup();
        fireEvent.touchStart(surface, { touches: [touch(100, 10)] });
        fireEvent.touchEnd(surface, { changedTouches: [touch(220, 10)] });
        expect(onSwipePrev).toHaveBeenCalledTimes(1);
    });

    it('touchEnd with an empty changedTouches list is ignored (no crash, no swipe)', () => {
        const { surface, onSwipeNext, onSwipePrev } = setup();
        fireEvent.touchStart(surface, { touches: [touch(200, 10)] });
        fireEvent.touchEnd(surface, { changedTouches: [] });
        expect(onSwipeNext).not.toHaveBeenCalled();
        expect(onSwipePrev).not.toHaveBeenCalled();
    });
});
