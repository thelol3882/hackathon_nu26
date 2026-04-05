'use client';

import { createContext, useContext, useState, type ReactNode } from 'react';

export interface ReplayState {
    enabled: boolean;
    start: string | null; // ISO string or Mantine DateStringValue
    end: string | null;
    cursor: string | null; // current "playhead" time as ISO string
}

interface LocomotiveContextValue {
    locomotiveId: string | null;
    setLocomotiveId: (id: string | null) => void;
    replay: ReplayState;
    setReplay: (replay: ReplayState) => void;
}

const defaultReplay: ReplayState = { enabled: false, start: null, end: null, cursor: null };

const LocomotiveContext = createContext<LocomotiveContextValue>({
    locomotiveId: null,
    setLocomotiveId: () => {},
    replay: defaultReplay,
    setReplay: () => {},
});

export function LocomotiveProvider({ children }: { children: ReactNode }) {
    const [locomotiveId, setLocomotiveId] = useState<string | null>(null);
    const [replay, setReplay] = useState<ReplayState>(defaultReplay);
    return (
        <LocomotiveContext value={{ locomotiveId, setLocomotiveId, replay, setReplay }}>
            {children}
        </LocomotiveContext>
    );
}

export function useLocomotive() {
    return useContext(LocomotiveContext);
}
