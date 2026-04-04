'use client';

import { createContext, useContext, useState, type ReactNode } from 'react';

interface LocomotiveContextValue {
    locomotiveId: string | null;
    setLocomotiveId: (id: string | null) => void;
}

const LocomotiveContext = createContext<LocomotiveContextValue>({
    locomotiveId: null,
    setLocomotiveId: () => {},
});

export function LocomotiveProvider({ children }: { children: ReactNode }) {
    const [locomotiveId, setLocomotiveId] = useState<string | null>(null);
    return (
        <LocomotiveContext value={{ locomotiveId, setLocomotiveId }}>
            {children}
        </LocomotiveContext>
    );
}

export function useLocomotive() {
    return useContext(LocomotiveContext);
}
