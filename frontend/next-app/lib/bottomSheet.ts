export type SheetState = 'collapsed' | 'half' | 'full';

export function nextState(current: SheetState): SheetState {
  if (current === 'collapsed') return 'half';
  if (current === 'half') return 'full';
  return 'collapsed';
}

export function clampShift(shift: number, height: number) {
  const max = Math.max(height - 56, 120);
  if (shift < 0) return 0;
  if (shift > max) return max;
  return shift;
}
