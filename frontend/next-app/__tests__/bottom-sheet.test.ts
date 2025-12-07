import { clampShift, nextState } from '@/lib/bottomSheet';

describe('bottom sheet utils', () => {
  it('cycles states', () => {
    expect(nextState('collapsed')).toBe('half');
    expect(nextState('half')).toBe('full');
    expect(nextState('full')).toBe('collapsed');
  });

  it('clamps shift to bounds', () => {
    expect(clampShift(-10, 400)).toBe(0);
    expect(clampShift(999, 200)).toBeGreaterThan(0);
    expect(clampShift(50, 200)).toBe(50);
  });
});
