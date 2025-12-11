import React, { useEffect, useState } from 'react';
import { api, endpoints } from '../api/client';
import { BarChart2 } from 'lucide-react';

interface Metric {
    name: string;
    model: string;
    expression: string;
}

interface MetricListProps {
    selectedMetric: string | null;
    onSelect: (metric: string) => void;
}

export const MetricList: React.FC<MetricListProps> = ({ selectedMetric, onSelect }) => {
    const [metrics, setMetrics] = useState<Metric[]>([]);

    useEffect(() => {
        api.get(endpoints.metrics).then(res => setMetrics(res.data));
    }, []);

    return (
        <div className="card">
            <h3 style={{ marginTop: 0, marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <BarChart2 size={20} />
                Metrics
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {metrics.map(m => (
                    <div
                        key={m.name}
                        onClick={() => onSelect(m.name)}
                        style={{
                            padding: '0.75rem',
                            borderRadius: '0.375rem',
                            cursor: 'pointer',
                            backgroundColor: selectedMetric === m.name ? 'var(--accent-primary)' : 'var(--bg-tertiary)',
                            color: selectedMetric === m.name ? 'white' : 'var(--text-primary)',
                            transition: 'background-color 0.2s'
                        }}
                    >
                        <div style={{ fontWeight: 600 }}>{m.name}</div>
                        <div style={{ fontSize: '0.75rem', opacity: 0.8 }}>{m.model}</div>
                    </div>
                ))}
            </div>
        </div>
    );
};
