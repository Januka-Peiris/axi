import axios from 'axios';
import { demoModels, demoMetrics, demoGraph } from '../demo/data';

const API_BASE = '/api';

export const isDemoMode = import.meta.env.VITE_AXI_DEMO_MODE === 'true';

export const endpoints = {
    models: `${API_BASE}/models`,
    metrics: `${API_BASE}/metrics`,
    dimensions: `${API_BASE}/dimensions`,
    graph: `${API_BASE}/graph`,
    query: `${API_BASE}/semantic/sql`,
    semanticSql: `${API_BASE}/semantic/sql`,
    runQuery: `${API_BASE}/query/run`,
    promotion: `${API_BASE}/promotion`,
};

// Mock Client
const mockApi = {
    get: async (url: string, _config?: any) => {
        await new Promise(r => setTimeout(r, 500)); // Latency

        if (url === endpoints.models) return { data: demoModels };
        if (url === endpoints.metrics) return { data: demoMetrics };

        if (url === endpoints.dimensions) {
            // Return dummy dims
            return { data: { "orders": ["date", "market", "channel"] } };
        }

        if (url === endpoints.graph) return { data: demoGraph };

        return { data: {} };
    },
    post: async (url: string, _data?: any) => {
        await new Promise(r => setTimeout(r, 500));
        if (url.includes('sql')) {
            return { data: { sql: "SELECT * FROM demo_table WHERE 1=1;" } };
        }
        return { data: {} };
    },
    put: async (_url: string, _data?: any) => {
        await new Promise(r => setTimeout(r, 300));
        return { data: { ok: true } };
    },
    delete: async (_url: string) => {
        await new Promise(r => setTimeout(r, 300));
        return { data: { ok: true } };
    }
};

export const api = isDemoMode ? mockApi : axios.create({
    baseURL: '/',
    headers: {
        'Content-Type': 'application/json',
    },
});

export default api;
