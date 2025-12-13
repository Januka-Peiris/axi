import { useEffect, useState } from 'react';
import { api } from '../api/client';
import { Server, Database, Snowflake, CheckCircle, XCircle, RefreshCw } from 'lucide-react';

interface HealthStatus {
    api: 'connected' | 'disconnected' | 'checking';
    snowflake: 'connected' | 'disconnected' | 'checking' | 'not_configured';
}

interface ApiInfo {
    service?: string;
    status?: string;
}

const StatusBadge = ({ status }: { status: string }) => {
    const config: Record<string, { color: string; icon: any; label: string }> = {
        connected: { color: 'text-green-400 bg-green-400/10', icon: CheckCircle, label: 'Connected' },
        disconnected: { color: 'text-red-400 bg-red-400/10', icon: XCircle, label: 'Disconnected' },
        checking: { color: 'text-yellow-400 bg-yellow-400/10', icon: RefreshCw, label: 'Checking...' },
        not_configured: { color: 'text-slate-400 bg-slate-400/10', icon: XCircle, label: 'Not Configured' },
    };
    const cfg = config[status] || config.disconnected;
    const Icon = cfg.icon;

    return (
        <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${cfg.color}`}>
            <Icon className={`w-3.5 h-3.5 ${status === 'checking' ? 'animate-spin' : ''}`} />
            {cfg.label}
        </span>
    );
};

export const SettingsPage = () => {
    const [health, setHealth] = useState<HealthStatus>({ api: 'checking', snowflake: 'checking' });
    const [apiInfo, setApiInfo] = useState<ApiInfo>({});

    const checkHealth = async () => {
        setHealth({ api: 'checking', snowflake: 'checking' });

        // Check API health
        try {
            const res = await api.get('/health');
            setApiInfo(res.data);
            setHealth(prev => ({ ...prev, api: 'connected' }));

            // Check Snowflake from health response
            if (res.data.snowflake_available === false) {
                setHealth(prev => ({ ...prev, snowflake: 'not_configured' }));
            } else if (res.data.snowflake_available === true) {
                setHealth(prev => ({ ...prev, snowflake: 'connected' }));
            } else {
                // Try to infer from response
                setHealth(prev => ({ ...prev, snowflake: 'not_configured' }));
            }
        } catch (err) {
            setHealth({ api: 'disconnected', snowflake: 'disconnected' });
        }
    };

    useEffect(() => {
        checkHealth();
    }, []);

    return (
        <div className="p-8 max-w-4xl mx-auto">
            <div className="flex items-center justify-between mb-8">
                <h1 className="text-2xl font-bold">Settings</h1>
                <button
                    onClick={checkHealth}
                    className="flex items-center gap-2 px-4 py-2 bg-white/5 hover:bg-white/10 rounded-lg text-sm transition-colors"
                >
                    <RefreshCw className="w-4 h-4" />
                    Refresh Status
                </button>
            </div>

            {/* Connection Status */}
            <div className="card mb-6">
                <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                    <Server className="w-5 h-5 text-cyan-400" />
                    Connection Status
                </h2>
                <div className="space-y-4">
                    <div className="flex items-center justify-between p-3 bg-black/20 rounded-lg">
                        <div className="flex items-center gap-3">
                            <Database className="w-5 h-5 text-slate-400" />
                            <div>
                                <p className="font-medium">AXI API</p>
                                <p className="text-xs text-slate-500">Backend service</p>
                            </div>
                        </div>
                        <StatusBadge status={health.api} />
                    </div>

                    <div className="flex items-center justify-between p-3 bg-black/20 rounded-lg">
                        <div className="flex items-center gap-3">
                            <Snowflake className="w-5 h-5 text-slate-400" />
                            <div>
                                <p className="font-medium">Snowflake</p>
                                <p className="text-xs text-slate-500">Data warehouse</p>
                            </div>
                        </div>
                        <StatusBadge status={health.snowflake} />
                    </div>
                </div>
            </div>

            {/* API Info */}
            <div className="card mb-6">
                <h2 className="text-lg font-semibold mb-4">API Information</h2>
                <div className="grid grid-cols-2 gap-4 text-sm">
                    <div className="p-3 bg-black/20 rounded-lg">
                        <p className="text-slate-500 text-xs mb-1">Service</p>
                        <p className="font-mono">{apiInfo.service || 'AXI Semantic Layer'}</p>
                    </div>
                    <div className="p-3 bg-black/20 rounded-lg">
                        <p className="text-slate-500 text-xs mb-1">Status</p>
                        <p className="font-mono">{apiInfo.status || (health.api === 'connected' ? 'ok' : 'unknown')}</p>
                    </div>
                </div>
            </div>

            {/* Configuration Help */}
            <div className="card border-dashed">
                <h2 className="text-lg font-semibold mb-4">Configuration</h2>
                <div className="text-sm text-slate-400 space-y-3">
                    <p>
                        AXI is configured via <code className="px-1.5 py-0.5 bg-black/30 rounded text-cyan-400">axi.yml</code> in your project root.
                    </p>
                    <p>
                        Snowflake credentials can be set via environment variables:
                    </p>
                    <pre className="p-3 bg-black/30 rounded-lg text-xs overflow-x-auto">
{`AXI_SNOWFLAKE_ACCOUNT=your_account
AXI_SNOWFLAKE_USER=your_user
AXI_SNOWFLAKE_PASSWORD=your_password
AXI_SNOWFLAKE_WAREHOUSE=your_warehouse
AXI_SNOWFLAKE_DATABASE=your_database`}
                    </pre>
                    <p className="text-xs">
                        See the <a href="#/docs" className="text-cyan-400 hover:underline">documentation</a> for more details.
                    </p>
                </div>
            </div>
        </div>
    );
};
