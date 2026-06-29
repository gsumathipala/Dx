import React from 'react';

interface Column<T> {
    header: string;
    accessor: (item: T) => React.ReactNode;
    className?: string;
}

interface TableProps<T> {
    data: T[];
    columns: Column<T>[];
    keyField: keyof T;
    onRowClick?: (item: T) => void;
    emptyMessage?: string;
}

export function Table<T>({ data, columns, keyField, onRowClick, emptyMessage = "No data found." }: TableProps<T>) {
    return (
        <div className="overflow-x-auto rounded-lg border border-slate-200 shadow-sm">
            <table className="min-w-full divide-y divide-slate-200">
                <thead className="bg-slate-50">
                    <tr>
                        {columns.map((col, idx) => (
                            <th
                                key={idx}
                                className={`px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider ${col.className || ''}`}
                            >
                                {col.header}
                            </th>
                        ))}
                    </tr>
                </thead>
                <tbody className="bg-white divide-y divide-slate-200">
                    {data.length === 0 ? (
                        <tr>
                            <td colSpan={columns.length} className="px-6 py-8 text-center text-slate-500 text-sm">
                                {emptyMessage}
                            </td>
                        </tr>
                    ) : (
                        data.map((item, idx) => (
                            <tr
                                key={String(item[keyField])}
                                onClick={onRowClick ? () => onRowClick(item) : undefined}
                                className={onRowClick ? "cursor-pointer hover:bg-slate-50 transition-colors" : ""}
                            >
                                {columns.map((col, cIdx) => (
                                    <td key={cIdx} className="px-4 py-3 whitespace-nowrap text-sm text-slate-700">
                                        {col.accessor(item)}
                                    </td>
                                ))}
                            </tr>
                        ))
                    )}
                </tbody>
            </table>
        </div>
    );
}
