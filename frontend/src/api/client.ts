import axios from 'axios';

export const endpoints = {
    models: '/api/models',
    metrics: '/api/metrics',
    dimensions: '/api/dimensions',
    graph: '/api/graph',
    query: '/api/semantic/sql',
    semanticSql: '/api/semantic/sql',
    runQuery: '/api/query/run',
    promotion: '/api/promotion',
};

export const api = axios.create({
    baseURL: '/',
    headers: {
        'Content-Type': 'application/json',
    },
});

export default api;
