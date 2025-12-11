import { useEffect, useState } from 'react';
import { api, endpoints } from '../api/client';
import { Database, Activity, GitGraph, Code } from 'lucide-react';
import { Link } from 'react-router-dom';

const StatCard = ({ label, value, icon: Icon, to }: any) => (
    <Link to={to} className="card hover:border-accent-cyan transition-colors group">
        <div className="flex items-center justify-between">
            <div>
                <p className="text-sm text-text-secondary">{label}</p>
                <p className="text-2xl font-bold mt-1 text-text-primary group-hover:text-accent-cyan transition-colors">{value}</p>
            </div>
            <div className="p-2 bg-background rounded-full text-text-secondary group-hover:text-accent-cyan group-hover:bg-accent-cyan/10 transition-colors">
                <Icon size={24} />
            </div>
        </div>
    </Link>
);

export const Dashboard = () => {
    const [stats, setStats] = useState({ models: 0, metrics: 0 });

    useEffect(() => {
        const fetchStats = async () => {
            const m = await api.get(endpoints.models);
            const me = await api.get(endpoints.metrics);
            setStats({
                models: Array.isArray(m.data) ? m.data.length : 0,
                metrics: Array.isArray(me.data) ? me.data.length : 0,
            });
        };
        fetchStats();
    }, []);

    return (
        <div className="p-8 max-w-7xl mx-auto">
            <h2 className="text-2xl font-bold mb-6">Overview</h2>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
                <StatCard label="Total Models" value={stats.models} icon={Database} to="/models" />
                <StatCard label="Total Metrics" value={stats.metrics} icon={Activity} to="/metrics" />
                <StatCard label="Graph Nodes" value={stats.models + stats.metrics} icon={GitGraph} to="/graph" />
                <StatCard label="Run Query" value=">" icon={Code} to="/query" />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="card h-64 flex items-center justify-center border-dashed border-2 bg-transparent">
                    <p className="text-text-secondary">Recent Activity (Comming Soon)</p>
                </div>
                <div className="card h-64 flex items-center justify-center border-dashed border-2 bg-transparent">
                    <p className="text-text-secondary">System Health (Coming Soon)</p>
                </div>
            </div>
        </div>
    );
};
