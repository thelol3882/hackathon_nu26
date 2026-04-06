'use client';

/**
 * Thin React wrapper around uPlot for the trends panel.
 *
 * Why uPlot and not Recharts here:
 *  - Canvas-based renderer comfortably handles 1000+ points at 60 fps
 *    (Recharts/SVG starts dropping frames around ~600 points).
 *  - `null` in the data array natively breaks the line — exactly what we
 *    need for smart-gap rendering, no per-point dot-render callbacks.
 *  - Built-in drag-to-zoom on the time scale, no event plumbing required.
 *
 * The wrapper is intentionally generic: a single y-series with an area
 * fill, a tooltip plugin styled to match the dashboard's Mantine theme,
 * and a controlled `selection` callback so the parent owns the zoom stack.
 */

import { useEffect, useLayoutEffect, useMemo, useRef } from 'react';
import uPlot from 'uplot';
import type { AlignedData, Options } from 'uplot';
import 'uplot/dist/uPlot.min.css';
import { dayjs } from '@/shared/utils/date';

export interface UPlotChartProps {
    /** Epoch-seconds timestamps. Must be sorted ascending. */
    timestamps: number[];
    /** Same length as `timestamps`; `null` means a real gap (line break). */
    values: Array<number | null>;
    /** Optional matching min/max series for the tooltip — not plotted. */
    minValues?: Array<number | null>;
    maxValues?: Array<number | null>;
    /** Forces the visible x-window even if data is missing on the left. */
    xMin: number;
    xMax: number;
    /** Series stroke colour (any CSS color). */
    color: string;
    /** Tooltip metadata. */
    sensorLabel: string;
    unit: string;
    /** Format string for the y-axis tick labels. */
    yTickFormatter?: (v: number) => string;
    /** Called when the user releases a drag-to-zoom selection. */
    onZoomSelect?: (xMinSec: number, xMaxSec: number) => void;
    /** Total chart height in px. */
    height?: number;
}

const FONT_FAMILY =
    "var(--font-sans), -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";

/** Hex/CSS color → rgba string with given alpha. Cheaper than reading
 *  computed style for every render. Accepts only #rrggbb / #rgb / rgb(...).*/
function withAlpha(color: string, alpha: number): string {
    if (color.startsWith('#')) {
        const hex = color.length === 4
            ? color.slice(1).split('').map((c) => c + c).join('')
            : color.slice(1);
        const r = parseInt(hex.slice(0, 2), 16);
        const g = parseInt(hex.slice(2, 4), 16);
        const b = parseInt(hex.slice(4, 6), 16);
        return `rgba(${r},${g},${b},${alpha})`;
    }
    if (color.startsWith('rgb(')) {
        return color.replace('rgb(', 'rgba(').replace(')', `,${alpha})`);
    }
    // CSS variable or named color — fall back to a uniform shade.
    return color;
}

/** Read a CSS color out of an element so we can resolve `var(--…)` strings. */
function resolveColor(probe: HTMLElement, value: string): string {
    if (!value.includes('var(')) return value;
    probe.style.color = value;
    return getComputedStyle(probe).color || value;
}

/** Pick a "nice" tick step (in seconds) for a window length, the same way
 *  DigitalOcean does: 5 min for 1 h, 30 min for 6 h, 2 h for 24 h … */
function niceTickStepSec(windowSec: number): number {
    const m = 60;
    const h = 60 * m;
    if (windowSec <= 5 * m) return 30;
    if (windowSec <= 15 * m) return 2 * m;
    if (windowSec <= 30 * m) return 5 * m;
    if (windowSec <= 60 * m) return 5 * m;
    if (windowSec <= 3 * h) return 15 * m;
    if (windowSec <= 6 * h) return 30 * m;
    if (windowSec <= 12 * h) return 1 * h;
    return 2 * h;
}

/**
 * Build explicit X-axis tick positions for the visible window. We snap to
 * local-TZ multiples of `stepSec` (so labels read 17:35, 17:40, …, not
 * 17:32, 17:37). Without this uPlot's auto split picker can produce
 * dozens of identical "17:48" labels for a small window.
 */
function buildTimeSplits(xMin: number, xMax: number, stepSec: number): number[] {
    if (xMax <= xMin || stepSec <= 0) return [];
    // getTimezoneOffset() returns minutes; positive when local is *behind*
    // UTC, so for UTC+5 the value is -300.  local = utc - tzShift.
    const tzShiftSec = new Date(xMin * 1000).getTimezoneOffset() * 60;
    const firstLocalTick = Math.ceil((xMin - tzShiftSec) / stepSec) * stepSec;
    const out: number[] = [];
    for (let local = firstLocalTick; ; local += stepSec) {
        const utc = local + tzShiftSec;
        if (utc > xMax) break;
        if (utc >= xMin) out.push(utc);
        if (out.length > 64) break; // safety cap
    }
    return out;
}

interface TooltipState {
    el: HTMLDivElement;
    titleEl: HTMLDivElement;
    valueEl: HTMLDivElement;
    rangeEl: HTMLDivElement;
}

export default function UPlotChart({
    timestamps,
    values,
    minValues,
    maxValues,
    xMin,
    xMax,
    color,
    sensorLabel,
    unit,
    yTickFormatter,
    onZoomSelect,
    height = 300,
}: UPlotChartProps) {
    const containerRef = useRef<HTMLDivElement | null>(null);
    const plotRef = useRef<uPlot | null>(null);
    const tooltipRef = useRef<TooltipState | null>(null);
    // We pass the latest tooltip-related closures into uPlot via a ref so
    // we don't have to tear down the plot each time the parent rerenders.
    const metaRef = useRef({ sensorLabel, unit, minValues, maxValues, color });
    metaRef.current = { sensorLabel, unit, minValues, maxValues, color };

    const onZoomRef = useRef(onZoomSelect);
    onZoomRef.current = onZoomSelect;

    const data: AlignedData = useMemo(
        () => [Float64Array.from(timestamps), Float64Array.from(values.map((v) => (v == null ? NaN : v)))],
        [timestamps, values],
    );

    // Build/destroy lifecycle. We rebuild on color/dimension/format changes;
    // for data updates we call setData() in a separate effect to keep the
    // canvas warm and avoid layout thrash.
    useLayoutEffect(() => {
        const container = containerRef.current;
        if (!container) return;

        // Resolve any CSS-var colours up front against a probe element so
        // uPlot's canvas paths get a real concrete colour string.
        const probe = document.createElement('span');
        probe.style.display = 'none';
        container.appendChild(probe);
        const strokeColor = resolveColor(probe, color);
        const fillTop = withAlpha(strokeColor, 0.28);
        const fillBot = withAlpha(strokeColor, 0);
        const gridColor = resolveColor(probe, 'var(--dashboard-border)') ||
            'rgba(255,255,255,0.08)';
        const axisColor = resolveColor(probe, 'var(--dashboard-text-secondary)') ||
            'rgba(255,255,255,0.55)';
        container.removeChild(probe);

        // ---------- tooltip plugin ----------
        const tooltip = document.createElement('div');
        tooltip.style.cssText = [
            'position:absolute',
            'pointer-events:none',
            'display:none',
            'background:var(--dashboard-surface)',
            'border:1px solid var(--dashboard-border)',
            'border-radius:8px',
            'padding:8px 12px',
            'font-size:12px',
            'line-height:1.6',
            'box-shadow:0 4px 12px rgba(0,0,0,0.18)',
            'z-index:10',
            'white-space:nowrap',
            'transform:translate(-50%, calc(-100% - 12px))',
        ].join(';');
        const titleEl = document.createElement('div');
        titleEl.style.cssText =
            'font-weight:600;margin-bottom:2px;color:var(--dashboard-text-secondary)';
        const valueEl = document.createElement('div');
        valueEl.style.cssText = 'color:var(--dashboard-text-primary)';
        const rangeEl = document.createElement('div');
        rangeEl.style.cssText =
            'color:var(--dashboard-text-secondary);font-size:11px;margin-top:2px';
        tooltip.append(titleEl, valueEl, rangeEl);
        container.appendChild(tooltip);
        tooltipRef.current = { el: tooltip, titleEl, valueEl, rangeEl };

        const tooltipPlugin: uPlot.Plugin = {
            hooks: {
                setCursor: [
                    (u) => {
                        const idx = u.cursor.idx;
                        if (idx == null || idx < 0) {
                            tooltip.style.display = 'none';
                            return;
                        }
                        const xs = u.data[0];
                        const ys = u.data[1];
                        const ts = xs[idx];
                        const v = ys[idx];
                        if (ts == null || v == null || Number.isNaN(v)) {
                            tooltip.style.display = 'none';
                            return;
                        }
                        const meta = metaRef.current;
                        titleEl.textContent = dayjs(ts * 1000).format(
                            'DD.MM.YYYY HH:mm:ss',
                        );
                        valueEl.innerHTML = `${escapeHtml(meta.sensorLabel)}: <strong>${(v as number).toFixed(2)}</strong> ${escapeHtml(meta.unit)}`;
                        const min = meta.minValues?.[idx];
                        const max = meta.maxValues?.[idx];
                        if (min != null && max != null) {
                            rangeEl.textContent = `мин ${min.toFixed(2)} / макс ${max.toFixed(2)} ${meta.unit}`;
                            rangeEl.style.display = '';
                        } else {
                            rangeEl.style.display = 'none';
                        }
                        const left = u.valToPos(ts, 'x');
                        const top = u.valToPos(v as number, 'y');
                        tooltip.style.left = `${left}px`;
                        tooltip.style.top = `${top}px`;
                        tooltip.style.display = 'block';
                    },
                ],
            },
        };

        // ---------- selection plugin (drag-to-zoom) ----------
        // uPlot already has built-in drag selection; we just listen on
        // setSelect to feed our parent and reset the visual selection.
        const selectPlugin: uPlot.Plugin = {
            hooks: {
                setSelect: [
                    (u) => {
                        const sel = u.select;
                        if (!sel || sel.width <= 2) return;
                        const left = u.posToVal(sel.left, 'x');
                        const right = u.posToVal(sel.left + sel.width, 'x');
                        // Clear the visual selection rect immediately —
                        // the parent will rerender with a new xMin/xMax.
                        u.setSelect({ left: 0, top: 0, width: 0, height: 0 }, false);
                        if (right - left > 1 && onZoomRef.current) {
                            onZoomRef.current(
                                Math.min(left, right),
                                Math.max(left, right),
                            );
                        }
                    },
                ],
            },
        };

        const opts: Options = {
            width: container.clientWidth || 600,
            height,
            cursor: {
                // Crosshair: vertical line that follows the mouse, no
                // horizontal — same as DigitalOcean.
                x: true,
                y: false,
                drag: { x: true, y: false, setScale: false },
                points: {
                    // The hover marker that snaps to the nearest data point.
                    // Bigger and ringed for visibility, like the DO charts.
                    show: true,
                    size: 9,
                    width: 2,
                    stroke: strokeColor,
                    fill: 'var(--dashboard-surface)',
                },
            },
            select: { show: true, left: 0, top: 0, width: 0, height: 0 },
            scales: {
                x: { time: true, min: xMin, max: xMax },
                y: { auto: true },
            },
            axes: [
                {
                    stroke: axisColor,
                    grid: { stroke: gridColor, width: 1, dash: [3, 3] },
                    ticks: { show: false },
                    space: 60,
                    font: `11px ${FONT_FAMILY}`,
                    // Force tick positions onto round local-TZ boundaries.
                    // Without this uPlot's auto-split sprays sub-minute ticks
                    // across the window and the HH:mm formatter collapses
                    // them all to the same label ("17:48 17:48 17:48 …").
                    splits: (u, _ax, sMin, sMax) => {
                        const w = sMax - sMin;
                        return buildTimeSplits(sMin, sMax, niceTickStepSec(w));
                    },
                    values: (_u, splits) => {
                        const w = xMax - xMin;
                        const stepSec = niceTickStepSec(w);
                        // Use HH:mm:ss only when the tick step itself is
                        // sub-minute. Otherwise HH:mm reads cleaner.
                        const useSec = stepSec < 60;
                        return splits.map((s) =>
                            dayjs(s * 1000).format(useSec ? 'HH:mm:ss' : 'HH:mm'),
                        );
                    },
                },
                {
                    stroke: axisColor,
                    grid: { stroke: gridColor, width: 1, dash: [3, 3] },
                    ticks: { show: false },
                    size: 60,
                    font: `11px ${FONT_FAMILY}`,
                    values: (_u, splits) =>
                        splits.map((s) =>
                            yTickFormatter ? yTickFormatter(s) : `${s}`,
                        ),
                },
            ],
            series: [
                {},
                {
                    label: sensorLabel,
                    stroke: strokeColor,
                    width: 2,
                    fill: (u) => {
                        const ctx = u.ctx;
                        const grad = ctx.createLinearGradient(
                            0,
                            u.bbox.top,
                            0,
                            u.bbox.top + u.bbox.height,
                        );
                        grad.addColorStop(0, fillTop);
                        grad.addColorStop(1, fillBot);
                        return grad;
                    },
                    spanGaps: false,
                    points: { show: false },
                    paths: uPlot.paths.spline?.(),
                    value: (_u, v) =>
                        v == null || Number.isNaN(v)
                            ? '—'
                            : `${(v as number).toFixed(2)} ${unit}`,
                },
            ],
            plugins: [tooltipPlugin, selectPlugin],
            legend: { show: false },
            padding: [10, 10, 0, 0],
        };

        const u = new uPlot(opts, data, container);
        plotRef.current = u;

        // Resize observer — uPlot doesn't track its parent on its own.
        const ro = new ResizeObserver(() => {
            if (!container || !plotRef.current) return;
            plotRef.current.setSize({
                width: container.clientWidth,
                height,
            });
        });
        ro.observe(container);

        return () => {
            ro.disconnect();
            tooltip.remove();
            u.destroy();
            plotRef.current = null;
            tooltipRef.current = null;
        };
        // We intentionally rebuild only when these "structural" props change.
        // Data and x-range updates flow through the effect below via setData.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [color, height, sensorLabel, unit, yTickFormatter]);

    // Push fresh data + window into the live plot without rebuilding it.
    useEffect(() => {
        const u = plotRef.current;
        if (!u) return;
        u.setScale('x', { min: xMin, max: xMax });
        u.setData(data);
    }, [data, xMin, xMax]);

    return (
        <div
            ref={containerRef}
            style={{ position: 'relative', width: '100%', height }}
        />
    );
}

function escapeHtml(s: string): string {
    return s
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

// Re-export the tick step helper so the parent can stay in sync if it
// needs to know how the X axis is being subdivided (e.g. for the bucket
// auto-selection that drives the network request).
export { niceTickStepSec };
