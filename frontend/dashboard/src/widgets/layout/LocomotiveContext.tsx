'use client';

import { createContext, useContext, useState, type ReactNode } from 'react';

export interface ReplayState {
    enabled: boolean;
    start: string | null;
    end: string | null;
    cursor: string | null;
}

interface LocomotiveContextValue {
    locomotiveId: string | null;
    locomotiveLabel: string | null;
    setLocomotive: (id: string | null, label?: string | null) => void;
    replay: ReplayState;
    setReplay: (replay: ReplayState) => void;
}

const defaultReplay: ReplayState = { enabled: false, start: null, end: null, cursor: null };

const LocomotiveContext = createContext<LocomotiveContextValue>({
    locomotiveId: null,
    locomotiveLabel: null,
    setLocomotive: () => {},
    replay: defaultReplay,
    setReplay: () => {},
});

export function LocomotiveProvider({ children }: { children: ReactNode }) {
    const [locomotiveId, setLocomotiveId] = useState<string | null>(null);
    const [locomotiveLabel, setLocomotiveLabel] = useState<string | null>(null);
    const [replay, setReplay] = useState<ReplayState>(defaultReplay);

    const setLocomotive = (id: string | null, label?: string | null) => {
        setLocomotiveId(id);
        setLocomotiveLabel(label ?? null);
    };

    return (
        <LocomotiveContext
            value={{ locomotiveId, locomotiveLabel, setLocomotive, replay, setReplay }}
        >
            {children}
        </LocomotiveContext>
    );
}

export function useLocomotive() {
    return useContext(LocomotiveContext);
}
