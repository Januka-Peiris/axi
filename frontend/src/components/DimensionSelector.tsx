import React, { useEffect, useState } from 'react';
import { api, endpoints } from '../api/client';
import { Split } from 'lucide-react';

interface DimensionSelectorProps {
    metric: string | null;
    selectedDims: string[];
    onChange: (dims: string[]) => void;
}

interface ReachableDimensions {
    [model: string]: string[];
}

export const DimensionSelector: React.FC<DimensionSelectorProps> = ({ metric, selectedDims, onChange }) => {
    const [reachable, setReachable] = useState<ReachableDimensions>({});

    useEffect(() => {
        const abortController = new AbortController();
        
        if (metric) {
            api.get(endpoints.dimensions, { params: { metric }, signal: abortController.signal })
                .then(res => {
                    if (!abortController.signal.aborted) {
                        setReachable(res.data || {});
                    }
                })
                .catch(error => {
                    if (error.name !== 'AbortError') {
                        console.error('Failed to load dimensions:', error);
                        setReachable({});
                    }
                });
        } else {
            setReachable({});
        }
        
        return () => {
            abortController.abort();
        };
    }, [metric]);

    const toggleDim = (dim: string) => {
        if (selectedDims.includes(dim)) {
            onChange(selectedDims.filter(d => d !== dim));
        } else {
            onChange([...selectedDims, dim]);
        }
    };

    if (!metric) return <div className="card" style={{ opacity: 0.5 }}>Select a metric to view dimensions</div>;

    return (
        <div className="card">
            <h3 style={{ marginTop: 0, marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Split size={20} />
                Dimensions
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                {Object.entries(reachable).map(([model, dims]) => {
                    if (!Array.isArray(dims)) return null;
                    return (
                        <div key={model}>
                            <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--text-secondary)', fontWeight: 600, marginBottom: '0.5rem' }}>
                                {model}
                            </div>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                                {dims.map(d => {
                                    const fullDim = model === metric ? d : `${model}.${d}`;
                                    const isSelected = selectedDims.includes(fullDim);
                                    return (
                                        <div
                                            key={d}
                                            onClick={() => toggleDim(fullDim)}
                                            className="badge"
                                            style={{
                                                cursor: 'pointer',
                                                border: isSelected ? '1px solid var(--accent-primary)' : '1px solid transparent',
                                                backgroundColor: isSelected ? 'rgba(59, 130, 246, 0.2)' : 'var(--bg-tertiary)',
                                                color: isSelected ? 'var(--accent-primary)' : 'var(--text-secondary)'
                                            }}
                                        >
                                            {d}
                                        </div>
                                    )
                                })}
                            </div>
                        </div>
                    )
                })}
            </div>
        </div>
    );
};
