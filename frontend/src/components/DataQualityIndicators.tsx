import { useState, useEffect } from 'react';
import {
    Activity,
    Clock,
    Database,
    AlertTriangle,
    CheckCircle,
    XCircle,
    RefreshCw,
    TrendingUp,
    BarChart3,
    Loader2
} from 'lucide-react';

interface DataQualityMetrics {
    freshness: {
        lastUpdated: Date | null;
        staleness: 'fresh' | 'stale' | 'critical' | 'unknown';
        thresholdHours: number;
    };
    completeness: {
        totalRows: number | null;
        nullRate: number | null;
        completenessScore: number | null;
    };
    validity: {
        schemaValid: boolean;
        hasExpression: boolean;
        hasEntity: boolean;
        hasDimensions: boolean;
    };
    usage: {
        queryCount: number;
        lastQueried: Date | null;
    };
}

interface DataQualityIndicatorsProps {
    entityType: 'metric' | 'dimension' | 'entity';
    entityData: {
        name: string;
        expression?: string;
        entity?: string;
        dimensions?: string[];
        type?: string;
        sql?: string;
    };
    compact?: boolean;
}

// Simulated freshness check - in production this would hit actual metadata
const checkFreshness = (entityType: string): DataQualityMetrics['freshness'] => {
    // Simulate with random data for demo
    const hoursAgo = Math.floor(Math.random() * 72);
    const lastUpdated = new Date(Date.now() - hoursAgo * 60 * 60 * 1000);

    let staleness: 'fresh' | 'stale' | 'critical' | 'unknown' = 'fresh';
    if (hoursAgo > 48) staleness = 'critical';
    else if (hoursAgo > 24) staleness = 'stale';

    return {
        lastUpdated,
        staleness,
        thresholdHours: 24
    };
};

// Simulated completeness check
const checkCompleteness = (): DataQualityMetrics['completeness'] => {
    const totalRows = Math.floor(Math.random() * 1000000) + 10000;
    const nullRate = Math.random() * 0.15; // 0-15% null rate
    const completenessScore = 1 - nullRate;

    return {
        totalRows,
        nullRate,
        completenessScore
    };
};

// Check validity based on entity data
const checkValidity = (entityData: DataQualityIndicatorsProps['entityData']): DataQualityMetrics['validity'] => {
    return {
        schemaValid: true,
        hasExpression: !!(entityData.expression || entityData.sql),
        hasEntity: !!entityData.entity,
        hasDimensions: (entityData.dimensions?.length || 0) > 0
    };
};

// Simulated usage stats
const checkUsage = (): DataQualityMetrics['usage'] => {
    const queryCount = Math.floor(Math.random() * 500);
    const daysAgo = Math.floor(Math.random() * 14);

    return {
        queryCount,
        lastQueried: queryCount > 0 ? new Date(Date.now() - daysAgo * 24 * 60 * 60 * 1000) : null
    };
};

export const DataQualityIndicators = ({
    entityType,
    entityData,
    compact = false
}: DataQualityIndicatorsProps) => {
    const [metrics, setMetrics] = useState<DataQualityMetrics | null>(null);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);

    const loadMetrics = () => {
        setRefreshing(true);
        // Simulate API call delay
        setTimeout(() => {
            setMetrics({
                freshness: checkFreshness(entityType),
                completeness: checkCompleteness(),
                validity: checkValidity(entityData),
                usage: checkUsage()
            });
            setLoading(false);
            setRefreshing(false);
        }, 500);
    };

    useEffect(() => {
        loadMetrics();
    }, [entityData.name]);

    const formatNumber = (num: number): string => {
        if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`;
        if (num >= 1000) return `${(num / 1000).toFixed(1)}K`;
        return num.toString();
    };

    const formatTimeAgo = (date: Date): string => {
        const hours = Math.floor((Date.now() - date.getTime()) / (1000 * 60 * 60));
        if (hours < 1) return 'Just now';
        if (hours < 24) return `${hours}h ago`;
        const days = Math.floor(hours / 24);
        return `${days}d ago`;
    };

    const getStalenessColor = (staleness: string) => {
        switch (staleness) {
            case 'fresh': return 'text-green-400 bg-green-500/20';
            case 'stale': return 'text-yellow-400 bg-yellow-500/20';
            case 'critical': return 'text-red-400 bg-red-500/20';
            default: return 'text-slate-400 bg-slate-500/20';
        }
    };

    const getStalenessIcon = (staleness: string) => {
        switch (staleness) {
            case 'fresh': return CheckCircle;
            case 'stale': return AlertTriangle;
            case 'critical': return XCircle;
            default: return Clock;
        }
    };

    const getCompletenessColor = (score: number) => {
        if (score >= 0.95) return 'text-green-400';
        if (score >= 0.85) return 'text-yellow-400';
        return 'text-red-400';
    };

    const calculateOverallScore = (): number => {
        if (!metrics) return 0;

        let score = 0;
        let factors = 0;

        // Freshness score
        if (metrics.freshness.staleness === 'fresh') score += 100;
        else if (metrics.freshness.staleness === 'stale') score += 60;
        else if (metrics.freshness.staleness === 'critical') score += 20;
        factors++;

        // Completeness score
        if (metrics.completeness.completenessScore !== null) {
            score += metrics.completeness.completenessScore * 100;
            factors++;
        }

        // Validity score
        const validityChecks = [
            metrics.validity.schemaValid,
            metrics.validity.hasExpression,
            metrics.validity.hasEntity
        ];
        const validityScore = validityChecks.filter(Boolean).length / validityChecks.length;
        score += validityScore * 100;
        factors++;

        return Math.round(score / factors);
    };

    if (loading) {
        return (
            <div className="rounded-xl border border-white/10 bg-[#151821] p-4">
                <div className="flex items-center justify-center gap-2 text-slate-400">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span className="text-sm">Loading quality metrics...</span>
                </div>
            </div>
        );
    }

    if (!metrics) return null;

    const overallScore = calculateOverallScore();
    const StalenessIcon = getStalenessIcon(metrics.freshness.staleness);

    // Compact view for sidebar/cards
    if (compact) {
        return (
            <div className="flex items-center gap-3">
                <div className={`flex items-center gap-1 px-2 py-1 rounded-full text-xs ${getStalenessColor(metrics.freshness.staleness)}`}>
                    <StalenessIcon className="w-3 h-3" />
                    <span className="capitalize">{metrics.freshness.staleness}</span>
                </div>
                {metrics.completeness.totalRows && (
                    <div className="flex items-center gap-1 text-xs text-slate-400">
                        <Database className="w-3 h-3" />
                        <span>{formatNumber(metrics.completeness.totalRows)} rows</span>
                    </div>
                )}
                <div className={`text-xs font-medium ${
                    overallScore >= 80 ? 'text-green-400' :
                    overallScore >= 60 ? 'text-yellow-400' : 'text-red-400'
                }`}>
                    {overallScore}% quality
                </div>
            </div>
        );
    }

    // Full view
    return (
        <div className="rounded-xl border border-white/10 bg-[#151821]">
            {/* Header */}
            <div className="flex items-center justify-between p-4 border-b border-white/10">
                <div className="flex items-center gap-2">
                    <Activity className="w-5 h-5 text-cyan-400" />
                    <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider">
                        Data Quality
                    </h3>
                </div>
                <div className="flex items-center gap-3">
                    {/* Overall Score */}
                    <div className={`flex items-center gap-2 px-3 py-1 rounded-full ${
                        overallScore >= 80 ? 'bg-green-500/20 text-green-400' :
                        overallScore >= 60 ? 'bg-yellow-500/20 text-yellow-400' : 'bg-red-500/20 text-red-400'
                    }`}>
                        <span className="text-lg font-bold">{overallScore}</span>
                        <span className="text-xs">/ 100</span>
                    </div>
                    <button
                        onClick={loadMetrics}
                        disabled={refreshing}
                        className="p-1.5 text-slate-500 hover:text-cyan-400 hover:bg-cyan-500/10 rounded transition-colors disabled:opacity-50"
                    >
                        <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
                    </button>
                </div>
            </div>

            {/* Metrics Grid */}
            <div className="grid grid-cols-2 gap-4 p-4">
                {/* Freshness */}
                <div className="p-3 rounded-lg bg-black/20 border border-white/5">
                    <div className="flex items-center gap-2 mb-2">
                        <Clock className="w-4 h-4 text-cyan-400" />
                        <span className="text-xs font-medium text-slate-400">Freshness</span>
                    </div>
                    <div className={`flex items-center gap-2 ${getStalenessColor(metrics.freshness.staleness)} px-2 py-1 rounded-lg w-fit`}>
                        <StalenessIcon className="w-4 h-4" />
                        <span className="text-sm font-medium capitalize">{metrics.freshness.staleness}</span>
                    </div>
                    {metrics.freshness.lastUpdated && (
                        <p className="text-xs text-slate-500 mt-2">
                            Updated {formatTimeAgo(metrics.freshness.lastUpdated)}
                        </p>
                    )}
                </div>

                {/* Completeness */}
                <div className="p-3 rounded-lg bg-black/20 border border-white/5">
                    <div className="flex items-center gap-2 mb-2">
                        <Database className="w-4 h-4 text-cyan-400" />
                        <span className="text-xs font-medium text-slate-400">Completeness</span>
                    </div>
                    {metrics.completeness.completenessScore !== null && (
                        <div className="mb-2">
                            <div className="flex items-center justify-between text-sm mb-1">
                                <span className={getCompletenessColor(metrics.completeness.completenessScore)}>
                                    {(metrics.completeness.completenessScore * 100).toFixed(1)}%
                                </span>
                                <span className="text-xs text-slate-500">
                                    {metrics.completeness.nullRate !== null &&
                                        `${(metrics.completeness.nullRate * 100).toFixed(1)}% nulls`
                                    }
                                </span>
                            </div>
                            <div className="h-1.5 bg-black/40 rounded-full overflow-hidden">
                                <div
                                    className={`h-full ${
                                        metrics.completeness.completenessScore >= 0.95 ? 'bg-green-500' :
                                        metrics.completeness.completenessScore >= 0.85 ? 'bg-yellow-500' : 'bg-red-500'
                                    }`}
                                    style={{ width: `${metrics.completeness.completenessScore * 100}%` }}
                                />
                            </div>
                        </div>
                    )}
                    {metrics.completeness.totalRows !== null && (
                        <p className="text-xs text-slate-500">
                            {formatNumber(metrics.completeness.totalRows)} total rows
                        </p>
                    )}
                </div>

                {/* Validity */}
                <div className="p-3 rounded-lg bg-black/20 border border-white/5">
                    <div className="flex items-center gap-2 mb-2">
                        <CheckCircle className="w-4 h-4 text-cyan-400" />
                        <span className="text-xs font-medium text-slate-400">Validity</span>
                    </div>
                    <div className="space-y-1">
                        <ValidityCheck label="Schema Valid" valid={metrics.validity.schemaValid} />
                        <ValidityCheck label="Has Expression" valid={metrics.validity.hasExpression} />
                        <ValidityCheck label="Has Entity" valid={metrics.validity.hasEntity} />
                        <ValidityCheck label="Has Dimensions" valid={metrics.validity.hasDimensions} />
                    </div>
                </div>

                {/* Usage */}
                <div className="p-3 rounded-lg bg-black/20 border border-white/5">
                    <div className="flex items-center gap-2 mb-2">
                        <BarChart3 className="w-4 h-4 text-cyan-400" />
                        <span className="text-xs font-medium text-slate-400">Usage</span>
                    </div>
                    <div className="flex items-center gap-2 mb-2">
                        <TrendingUp className="w-4 h-4 text-purple-400" />
                        <span className="text-sm text-white font-medium">
                            {metrics.usage.queryCount} queries
                        </span>
                    </div>
                    {metrics.usage.lastQueried && (
                        <p className="text-xs text-slate-500">
                            Last queried {formatTimeAgo(metrics.usage.lastQueried)}
                        </p>
                    )}
                </div>
            </div>
        </div>
    );
};

const ValidityCheck = ({ label, valid }: { label: string; valid: boolean }) => (
    <div className="flex items-center gap-2">
        {valid ? (
            <CheckCircle className="w-3 h-3 text-green-400" />
        ) : (
            <XCircle className="w-3 h-3 text-red-400" />
        )}
        <span className={`text-xs ${valid ? 'text-slate-300' : 'text-slate-500'}`}>
            {label}
        </span>
    </div>
);

export default DataQualityIndicators;
