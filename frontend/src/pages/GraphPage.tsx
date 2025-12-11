import { GraphView } from '../components/GraphView';

export const GraphPage = () => {
    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
            <header>
                <h1 style={{ margin: 0, fontSize: '1.875rem' }}>Semantic Graph</h1>
                <p style={{ color: 'var(--text-secondary)', marginTop: '0.5rem' }}>
                    Visualizing models and valid join paths.
                </p>
            </header>
            <GraphView />
        </div>
    );
};
