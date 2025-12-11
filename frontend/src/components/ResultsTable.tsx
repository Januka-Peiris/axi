import React from 'react';

interface ResultsTableProps {
    data: any[];
    columns: string[];
    loading: boolean;
    error: string | null;
}

export const ResultsTable: React.FC<ResultsTableProps> = ({ data, columns, loading, error }) => {
    if (loading) return <div className="card">Loading...</div>;
    if (error) return <div className="card" style={{ color: 'red' }}>Error: {error}</div>;
    if (!data || data.length === 0) return null;

    return (
        <div className="card" style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
                <thead>
                    <tr style={{ borderBottom: '1px solid var(--border-color)' }}>
                        {columns.map(col => (
                            <th key={col} style={{ textAlign: 'left', padding: '0.75rem', color: 'var(--text-secondary)' }}>
                                {col}
                            </th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {data.map((row, i) => (
                        <tr key={i} style={{ borderBottom: '1px solid var(--border-color)' }}>
                            {columns.map(col => (
                                <td key={col} style={{ padding: '0.75rem' }}>
                                    {String(row[col])}
                                </td>
                            ))}
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
};
