import { useState } from 'react';
import { api, endpoints } from '../api/client';
import { MetricList } from '../components/MetricList';
import { DimensionSelector } from '../components/DimensionSelector';
import { SqlPreview } from '../components/SqlPreview';
import { ResultsTable } from '../components/ResultsTable';

export const MetricsPage = () => {
    const [metric, setMetric] = useState<string | null>(null);
    const [dims, setDims] = useState<string[]>([]);
    const [sql, setSql] = useState('');

    const [rows, setRows] = useState<any[]>([]);
    const [cols, setCols] = useState<string[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleMetricSelect = (m: string) => {
        setMetric(m);
        setDims([]);
        setRows([]);
        setCols([]);
        setError(null);
    };

    const handleRun = async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await api.post(endpoints.runQuery, { sql });
            if (res.data.error) {
                setError(res.data.error);
            } else {
                setRows(res.data.rows);
                setCols(res.data.columns);
            }
        } catch (e: any) {
            setError(e.message);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
            <header>
                <h1 style={{ margin: 0, fontSize: '1.875rem' }}>Semantic Explorer</h1>
                <p style={{ color: 'var(--text-secondary)', marginTop: '0.5rem' }}>
                    Explore metrics, automatically generate joins across models, and visualize results.
                </p>
            </header>

            <div style={{ display: 'grid', gridTemplateColumns: 'minmax(250px, 1fr) minmax(250px, 1fr) 2fr', gap: '1.5rem', alignItems: 'start' }}>
                <MetricList selectedMetric={metric} onSelect={handleMetricSelect} />
                <DimensionSelector metric={metric} selectedDims={dims} onChange={setDims} />
                <SqlPreview
                    metric={metric}
                    dimensions={dims}
                    usersSql={sql}
                    onSqlChange={setSql}
                    onRun={handleRun}
                />
            </div>

            <ResultsTable data={rows} columns={cols} loading={loading} error={error} />
        </div>
    );
};
