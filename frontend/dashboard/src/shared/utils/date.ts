import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';
import duration from 'dayjs/plugin/duration';
import 'dayjs/locale/ru';

dayjs.extend(relativeTime);
dayjs.extend(duration);
dayjs.locale('ru');

/** "04.04.2026" */
export function formatDate(value: string | Date): string {
    return dayjs(value).format('DD.MM.YYYY');
}

/** "04.04.2026 22:30" */
export function formatDateTime(value: string | Date): string {
    return dayjs(value).format('DD.MM.YYYY HH:mm');
}

/** "04.04.2026 22:30:15" */
export function formatDateTimeFull(value: string | Date): string {
    return dayjs(value).format('DD.MM.YYYY HH:mm:ss');
}

/** "22:30:15" */
export function formatTime(value: string | Date): string {
    return dayjs(value).format('HH:mm:ss');
}

/** "22:30" */
export function formatTimeShort(value: string | Date): string {
    return dayjs(value).format('HH:mm');
}

/** "4 Apr" */
export function formatDateShort(value: string | Date): string {
    return dayjs(value).format('D MMM');
}

/** "4 April 2026" */
export function formatDateLong(value: string | Date): string {
    return dayjs(value).format('D MMMM YYYY');
}

/** "2 minutes ago" */
export function getRelativeTime(value: string | Date): string {
    return dayjs(value).fromNow();
}

/** Seconds elapsed since the given timestamp */
export function getSecondsAgo(value: string | Date): number {
    return dayjs().diff(dayjs(value), 'second');
}

/** Format a duration in seconds as "Xh Ym Zs" */
export function formatDuration(seconds: number): string {
    const d = dayjs.duration(seconds, 'seconds');
    const h = Math.floor(d.asHours());
    const m = d.minutes();
    const s = d.seconds();
    if (h > 0) return `${h}ч ${m}м ${s}с`;
    if (m > 0) return `${m}м ${s}с`;
    return `${s}с`;
}

/** ISO string for "now minus N minutes" — useful for telemetry queries */
export function minutesAgo(n: number): string {
    return dayjs().subtract(n, 'minute').toISOString();
}

/** ISO string for "now minus N hours" */
export function hoursAgo(n: number): string {
    return dayjs().subtract(n, 'hour').toISOString();
}

/** ISO string for "now" */
export function nowISO(): string {
    return dayjs().toISOString();
}

/** Check if timestamp is older than N seconds */
export function isStale(value: string | Date, thresholdSeconds: number): boolean {
    return getSecondsAgo(value) > thresholdSeconds;
}

/** Get start/end of a day range for a given date */
export function getDayRange(value: string | Date): { start: string; end: string } {
    const d = dayjs(value);
    return {
        start: d.startOf('day').toISOString(),
        end: d.endOf('day').toISOString(),
    };
}

export { dayjs };
