import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
    formatDate,
    formatDateTime,
    formatDateTimeFull,
    formatTime,
    formatTimeShort,
    formatDateShort,
    formatDateLong,
    getRelativeTime,
    getSecondsAgo,
    formatDuration,
    minutesAgo,
    hoursAgo,
    nowISO,
    isStale,
    getDayRange,
    dayjs,
} from '../date';

const FIXED_NOW = '2026-04-04T15:30:00.000Z';

beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(FIXED_NOW));
});

afterEach(() => {
    vi.useRealTimers();
});

describe('formatDate', () => {
    it('formats ISO string as DD.MM.YYYY', () => {
        expect(formatDate('2026-04-04T12:00:00Z')).toBe('04.04.2026');
    });
});

describe('formatDateTime', () => {
    it('formats as DD.MM.YYYY HH:mm', () => {
        const result = formatDateTime('2026-04-04T12:30:00Z');
        expect(result).toMatch(/04\.04\.2026 \d{2}:30/);
    });
});

describe('formatDateTimeFull', () => {
    it('includes seconds', () => {
        const result = formatDateTimeFull('2026-04-04T12:30:45Z');
        expect(result).toMatch(/04\.04\.2026 \d{2}:30:45/);
    });
});

describe('formatTime', () => {
    it('formats as HH:mm:ss', () => {
        const result = formatTime('2026-04-04T12:30:45Z');
        expect(result).toMatch(/\d{2}:30:45/);
    });
});

describe('formatTimeShort', () => {
    it('formats as HH:mm', () => {
        const result = formatTimeShort('2026-04-04T12:30:45Z');
        expect(result).toMatch(/\d{2}:30/);
    });
});

describe('formatDateShort', () => {
    it('returns short date like "4 апр"', () => {
        const result = formatDateShort('2026-04-04T12:00:00Z');
        expect(result).toContain('4');
        expect(result).toContain('апр');
    });
});

describe('formatDateLong', () => {
    it('returns long date like "4 апреля 2026"', () => {
        const result = formatDateLong('2026-04-04T12:00:00Z');
        expect(result).toContain('4');
        expect(result).toContain('апрел');
        expect(result).toContain('2026');
    });
});

describe('getRelativeTime', () => {
    it('returns relative string for recent time', () => {
        const fiveMinAgo = dayjs(FIXED_NOW).subtract(5, 'minute').toISOString();
        const result = getRelativeTime(fiveMinAgo);
        expect(result).toContain('5');
        expect(result).toContain('минут');
    });
});

describe('getSecondsAgo', () => {
    it('returns seconds elapsed', () => {
        const twoMinAgo = dayjs(FIXED_NOW).subtract(120, 'second').toISOString();
        expect(getSecondsAgo(twoMinAgo)).toBe(120);
    });
});

describe('formatDuration', () => {
    it('formats seconds only', () => {
        expect(formatDuration(45)).toBe('45с');
    });

    it('formats minutes and seconds', () => {
        expect(formatDuration(125)).toBe('2м 5с');
    });

    it('formats hours, minutes, seconds', () => {
        expect(formatDuration(3665)).toBe('1ч 1м 5с');
    });
});

describe('minutesAgo', () => {
    it('returns ISO string N minutes before now', () => {
        const result = minutesAgo(10);
        const diff = dayjs(FIXED_NOW).diff(dayjs(result), 'minute');
        expect(diff).toBe(10);
    });
});

describe('hoursAgo', () => {
    it('returns ISO string N hours before now', () => {
        const result = hoursAgo(2);
        const diff = dayjs(FIXED_NOW).diff(dayjs(result), 'hour');
        expect(diff).toBe(2);
    });
});

describe('nowISO', () => {
    it('returns current time as ISO', () => {
        expect(nowISO()).toBe(FIXED_NOW);
    });
});

describe('isStale', () => {
    it('returns true when older than threshold', () => {
        const old = dayjs(FIXED_NOW).subtract(60, 'second').toISOString();
        expect(isStale(old, 30)).toBe(true);
    });

    it('returns false when within threshold', () => {
        const recent = dayjs(FIXED_NOW).subtract(10, 'second').toISOString();
        expect(isStale(recent, 30)).toBe(false);
    });
});

describe('getDayRange', () => {
    it('returns start and end of day as ISO strings', () => {
        const { start, end } = getDayRange('2026-04-04T12:00:00Z');
        expect(dayjs(start).hour()).toBe(0);
        expect(dayjs(start).minute()).toBe(0);
        expect(dayjs(end).hour()).toBe(23);
        expect(dayjs(end).minute()).toBe(59);
    });
});
