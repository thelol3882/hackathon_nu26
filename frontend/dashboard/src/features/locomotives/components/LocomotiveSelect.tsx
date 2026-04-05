'use client';

import { useState, useCallback, useRef } from 'react';
import {
    Box,
    Combobox,
    InputBase,
    ScrollArea,
    SegmentedControl,
    Loader,
    CloseButton,
    Group,
    Text,
    useCombobox,
} from '@mantine/core';
import { useDebouncedValue } from '@mantine/hooks';
import { IconSearch } from '@tabler/icons-react';
import { useGetLocomotivesQuery } from '../api/locomotivesApi';

const PAGE_SIZE = 50;
const MODEL_FILTERS = [
    { value: '', label: 'Все' },
    { value: 'TE33A', label: 'TE33A' },
    { value: 'KZ8A', label: 'KZ8A' },
];

interface LocomotiveSelectProps {
    value: string | null;
    onChange: (value: string | null, label?: string | null) => void;
    /** Allow selecting "all" (null) — shows "Все" option at the top */
    allowAll?: boolean;
    label?: string;
    placeholder?: string;
    w?: number | string;
}

export function LocomotiveSelect({
    value,
    onChange,
    allowAll = false,
    label,
    placeholder = 'Выберите локомотив',
    w = 280,
}: LocomotiveSelectProps) {
    const combobox = useCombobox({
        onDropdownClose: () => combobox.resetSelectedOption(),
    });

    const [search, setSearch] = useState('');
    const [modelFilter, setModelFilter] = useState('');
    const [offset, setOffset] = useState(0);
    const [debouncedSearch] = useDebouncedValue(search, 300);
    const viewportRef = useRef<HTMLDivElement>(null);

    const { data, isFetching } = useGetLocomotivesQuery({
        offset,
        limit: PAGE_SIZE,
        search: debouncedSearch || undefined,
        model: modelFilter || undefined,
    });

    const items = data?.items ?? [];
    const total = data?.total ?? 0;
    const hasMore = items.length < total;

    const selectedLoco = items.find((l) => l.id === value);
    const selectedLabel = selectedLoco
        ? `${selectedLoco.model} — ${selectedLoco.serial_number}`
        : value
          ? `Локомотив ${value.slice(0, 8)}…`
          : allowAll
            ? 'Все'
            : null;

    const handleScrollPositionChange = useCallback(
        (pos: { x: number; y: number }) => {
            const viewport = viewportRef.current;
            if (!viewport || isFetching || !hasMore) return;
            const { scrollHeight, clientHeight } = viewport;
            if (pos.y + clientHeight >= scrollHeight - 20) {
                setOffset(items.length);
            }
        },
        [isFetching, hasMore, items.length],
    );

    const options = items.map((loco) => (
        <Combobox.Option key={loco.id} value={loco.id} active={loco.id === value}>
            <Group gap="xs" wrap="nowrap">
                <Text size="xs" c="dimmed" fw={600} w={48} style={{ flexShrink: 0 }}>
                    {loco.model}
                </Text>
                <Text size="sm" truncate>
                    {loco.serial_number}
                </Text>
            </Group>
        </Combobox.Option>
    ));

    return (
        <Combobox
            store={combobox}
            onOptionSubmit={(val) => {
                if (val === '__all__') {
                    onChange(null, null);
                } else if (val === value) {
                    onChange(null, null);
                } else {
                    const loco = items.find((l) => l.id === val);
                    const label = loco ? `${loco.model} — ${loco.serial_number}` : null;
                    onChange(val, label);
                }
                combobox.closeDropdown();
            }}
            withinPortal
        >
            <Combobox.Target>
                <InputBase
                    component="button"
                    type="button"
                    pointer
                    label={label}
                    rightSection={
                        value ? (
                            <CloseButton
                                size="sm"
                                onClick={(e) => {
                                    e.stopPropagation();
                                    onChange(null);
                                }}
                            />
                        ) : (
                            <Combobox.Chevron />
                        )
                    }
                    rightSectionPointerEvents={value ? 'auto' : 'none'}
                    onClick={() => combobox.toggleDropdown()}
                    w={w}
                >
                    {selectedLabel || (
                        <Text size="sm" c="dimmed">
                            {placeholder}
                        </Text>
                    )}
                </InputBase>
            </Combobox.Target>

            <Combobox.Dropdown>
                <Box
                    p={4}
                    style={{ borderBottom: '1px solid var(--mantine-color-default-border)' }}
                >
                    <Combobox.Search
                        value={search}
                        onChange={(e) => {
                            setSearch(e.currentTarget.value);
                            setOffset(0);
                        }}
                        placeholder="Поиск..."
                        leftSection={<IconSearch size={14} />}
                        mb={6}
                    />
                    <SegmentedControl
                        data={MODEL_FILTERS}
                        value={modelFilter}
                        onChange={(v) => {
                            setModelFilter(v);
                            setOffset(0);
                        }}
                        size="xs"
                        fullWidth
                    />
                </Box>

                <Combobox.Options>
                    <ScrollArea.Autosize
                        mah={280}
                        type="scroll"
                        viewportRef={viewportRef}
                        onScrollPositionChange={handleScrollPositionChange}
                    >
                        {allowAll && (
                            <Combobox.Option value="__all__" active={value === null}>
                                <Text size="sm" fw={500}>
                                    Все
                                </Text>
                            </Combobox.Option>
                        )}
                        {options.length > 0 ? (
                            options
                        ) : (
                            <Combobox.Empty>
                                {isFetching ? 'Загрузка...' : 'Ничего не найдено'}
                            </Combobox.Empty>
                        )}
                        {isFetching && items.length > 0 && (
                            <Box ta="center" py={8}>
                                <Loader size="xs" />
                            </Box>
                        )}
                    </ScrollArea.Autosize>
                </Combobox.Options>
            </Combobox.Dropdown>
        </Combobox>
    );
}
