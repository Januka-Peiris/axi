import { useEffect, useState } from 'react';
import { api, endpoints } from '../api/client';
import { Database } from 'lucide-react';

interface Model {
    name: string;
    path?: string;
    source_tables?: string[];
    dimensions?: string[];
}

export const ModelsPage = () => {
    const [models, setModels] = useState<Model[]>([]);

    useEffect(() => {
        api.get(endpoints.models).then(res => {
            if (Array.isArray(res.data)) {
                // Handle both string array and object array formats
                const modelData = res.data.map((item: any) => {
                    if (typeof item === 'string') {
                        return { name: item };
                    }
                    return item;
                });
                setModels(modelData);
            }
        }).catch(err => {
            console.error('Failed to load models:', err);
            setModels([]);
        });
    }, []);

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
            <header>
                <h1 style={{ margin: 0, fontSize: '1.875rem' }}>Models</h1>
                <p style={{ color: 'var(--text-secondary)', marginTop: '0.5rem' }}>
                    Registered semantic models and their metadata.
                </p>
            </header>

            {models.length === 0 ? (
                <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
                    No models found. Run <code>axi extract</code> to extract models from your SQL files.
                </div>
            ) : (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '1.5rem' }}>
                    {models.map(m => <ModelCard key={m.name} model={m} />)}
                </div>
            )}
        </div>
    );
};

const ModelCard = ({ model }: { model: Model }) => {
    const sourceTables = model.source_tables || [];
    const dimensions = model.dimensions || [];

    return (
        <div className="card">
            <h3 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: 0 }}>
                <Database size={20} className="text-blue-500" style={{ color: 'var(--accent-primary)' }} />
                {model.name}
            </h3>
            <div style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', marginTop: '0.5rem' }}>
                {sourceTables.length > 0 && (
                    <div style={{ marginBottom: '0.5rem' }}>
                        <strong>Source tables:</strong> {sourceTables.join(', ')}
                    </div>
                )}
                {dimensions.length > 0 && (
                    <div>
                        <strong>Dimensions:</strong> {dimensions.length} dimension{dimensions.length !== 1 ? 's' : ''}
                    </div>
                )}
                {sourceTables.length === 0 && dimensions.length === 0 && (
                    <div>Metadata loaded.</div>
                )}
            </div>
        </div>
    );
};
