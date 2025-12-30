import React, { useEffect } from 'react';
import { api, endpoints } from '../api/client';
import { Code, Play } from 'lucide-react';

interface SqlPreviewProps {
    metric: string | null;
    dimensions: string[];
    usersSql: string;
    onSqlChange: (sql: string) => void;
    onRun: () => void;
}

export const SqlPreview: React.FC<SqlPreviewProps> = ({ metric, dimensions, usersSql, onSqlChange, onRun }) => {

    useEffect(() => {
        if (metric) {
            api.post(endpoints.semanticSql, { metric, dimensions }).then(res => {
                if (res.data.sql) {
                    onSqlChange(res.data.sql);
                }
            });
        }
    }, [metric, dimensions, onSqlChange]);

    return (
        <div className="card" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                <h3 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <Code size={20} />
                    Generated SQL
                </h3>
                <button className="btn btn-primary" onClick={onRun} disabled={!usersSql}>
                    <Play size={16} style={{ marginRight: '0.5rem' }} />
                    Run in Snowflake
                </button>
            </div>
            <textarea
                value={usersSql}
                readOnly
                style={{
                    flex: 1,
                    width: '100%',
                    backgroundColor: '#0f172a',
                    color: '#f8fafc',
                    border: '1px solid var(--border-color)',
                    borderRadius: '0.375rem',
                    padding: '1rem',
                    fontFamily: 'monospace',
                    fontSize: '0.875rem',
                    lineHeight: 1.5,
                    resize: 'none',
                    minHeight: '200px'
                }}
            />
        </div>
    );
};
