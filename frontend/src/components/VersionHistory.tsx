import { useState, useEffect } from 'react';
import { History, GitCommit, ChevronDown, ChevronRight, RotateCcw, Diff } from 'lucide-react';

interface VersionEntry {
    id: string;
    version: number;
    timestamp: Date;
    author: string;
    changes: {
        field: string;
        oldValue: any;
        newValue: any;
    }[];
    snapshot: Record<string, any>;
}

interface VersionHistoryProps {
    entityType: 'metric' | 'dimension' | 'entity';
    entityId: string;
    currentData: Record<string, any>;
    onRestore?: (snapshot: Record<string, any>) => void;
}

// Local storage key for version history
const getStorageKey = (entityType: string, entityId: string) =>
    `axi_versions_${entityType}_${entityId}`;

export const VersionHistory = ({
    entityType,
    entityId,
    currentData,
    onRestore
}: VersionHistoryProps) => {
    const [versions, setVersions] = useState<VersionEntry[]>([]);
    const [expandedVersion, setExpandedVersion] = useState<string | null>(null);
    const [comparing, setComparing] = useState<string | null>(null);

    // Load versions from local storage
    useEffect(() => {
        const key = getStorageKey(entityType, entityId);
        const stored = localStorage.getItem(key);
        if (stored) {
            try {
                const parsed = JSON.parse(stored);
                setVersions(parsed.map((v: any) => ({
                    ...v,
                    timestamp: new Date(v.timestamp)
                })));
            } catch {
                setVersions([]);
            }
        }
    }, [entityType, entityId]);

    // Record a new version when currentData changes significantly
    useEffect(() => {
        if (!currentData || Object.keys(currentData).length === 0) return;

        const key = getStorageKey(entityType, entityId);
        const stored = localStorage.getItem(key);
        let existingVersions: VersionEntry[] = [];

        if (stored) {
            try {
                existingVersions = JSON.parse(stored).map((v: any) => ({
                    ...v,
                    timestamp: new Date(v.timestamp)
                }));
            } catch {
                existingVersions = [];
            }
        }

        // Check if we should create a new version
        const latestVersion = existingVersions[0];
        if (latestVersion) {
            const changes = detectChanges(latestVersion.snapshot, currentData);
            if (changes.length === 0) return; // No changes
        }

        // Create new version
        const newVersion: VersionEntry = {
            id: `v_${Date.now()}`,
            version: existingVersions.length + 1,
            timestamp: new Date(),
            author: 'System',
            changes: latestVersion ? detectChanges(latestVersion.snapshot, currentData) : [],
            snapshot: { ...currentData }
        };

        const newVersions = [newVersion, ...existingVersions].slice(0, 20); // Keep last 20 versions
        localStorage.setItem(key, JSON.stringify(newVersions));
        setVersions(newVersions);
    }, [currentData, entityType, entityId]);

    const detectChanges = (oldData: Record<string, any>, newData: Record<string, any>) => {
        const changes: VersionEntry['changes'] = [];
        const allKeys = new Set([...Object.keys(oldData), ...Object.keys(newData)]);

        allKeys.forEach(key => {
            const oldVal = oldData[key];
            const newVal = newData[key];

            if (JSON.stringify(oldVal) !== JSON.stringify(newVal)) {
                changes.push({
                    field: key,
                    oldValue: oldVal,
                    newValue: newVal
                });
            }
        });

        return changes;
    };

    const formatDate = (date: Date) => {
        return date.toLocaleString(undefined, {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    };

    const formatValue = (value: any): string => {
        if (value === null || value === undefined) return 'null';
        if (typeof value === 'object') return JSON.stringify(value);
        return String(value);
    };

    const handleRestore = (version: VersionEntry) => {
        if (onRestore) {
            onRestore(version.snapshot);
        }
    };

    return (
        <div className="rounded-xl border border-white/10 bg-[#151821]">
            {/* Header */}
            <div className="flex items-center gap-2 p-4 border-b border-white/10">
                <History className="w-5 h-5 text-cyan-400" />
                <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider">
                    Version History
                </h3>
                <span className="text-xs text-slate-500">({versions.length} versions)</span>
            </div>

            {/* Version List */}
            <div className="max-h-[400px] overflow-y-auto">
                {versions.length === 0 ? (
                    <div className="p-8 text-center text-slate-500">
                        <History className="w-8 h-8 mx-auto mb-2 opacity-50" />
                        <p>No version history yet</p>
                    </div>
                ) : (
                    <div className="divide-y divide-white/5">
                        {versions.map((version, index) => (
                            <div key={version.id} className="relative">
                                {/* Timeline connector */}
                                {index < versions.length - 1 && (
                                    <div className="absolute left-6 top-10 bottom-0 w-0.5 bg-white/10" />
                                )}

                                <div
                                    className={`p-4 hover:bg-white/5 transition-colors cursor-pointer ${
                                        expandedVersion === version.id ? 'bg-white/5' : ''
                                    }`}
                                    onClick={() => setExpandedVersion(
                                        expandedVersion === version.id ? null : version.id
                                    )}
                                >
                                    <div className="flex items-start gap-3">
                                        {/* Version indicator */}
                                        <div className={`w-4 h-4 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5 ${
                                            index === 0 ? 'bg-cyan-500' : 'bg-white/20'
                                        }`}>
                                            <GitCommit className="w-2.5 h-2.5 text-white" />
                                        </div>

                                        <div className="flex-1 min-w-0">
                                            <div className="flex items-center gap-2">
                                                <span className="text-sm font-medium text-white">
                                                    Version {version.version}
                                                </span>
                                                {index === 0 && (
                                                    <span className="px-1.5 py-0.5 text-[10px] bg-cyan-500/20 text-cyan-400 rounded">
                                                        Current
                                                    </span>
                                                )}
                                                {expandedVersion === version.id ? (
                                                    <ChevronDown className="w-4 h-4 text-slate-400" />
                                                ) : (
                                                    <ChevronRight className="w-4 h-4 text-slate-400" />
                                                )}
                                            </div>

                                            <div className="flex items-center gap-2 mt-1 text-xs text-slate-500">
                                                <span>{formatDate(version.timestamp)}</span>
                                                <span>by {version.author}</span>
                                            </div>

                                            {version.changes.length > 0 && expandedVersion !== version.id && (
                                                <div className="mt-1 text-xs text-slate-400">
                                                    {version.changes.length} change{version.changes.length > 1 ? 's' : ''}
                                                </div>
                                            )}
                                        </div>

                                        {/* Actions */}
                                        {index > 0 && onRestore && (
                                            <button
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    handleRestore(version);
                                                }}
                                                className="p-1.5 text-slate-500 hover:text-cyan-400 hover:bg-cyan-500/10 rounded transition-colors"
                                                title="Restore this version"
                                            >
                                                <RotateCcw className="w-4 h-4" />
                                            </button>
                                        )}
                                    </div>

                                    {/* Expanded changes */}
                                    {expandedVersion === version.id && version.changes.length > 0 && (
                                        <div className="mt-4 ml-7 space-y-2">
                                            {version.changes.map((change, i) => (
                                                <div
                                                    key={i}
                                                    className="p-3 bg-black/30 rounded-lg border border-white/5"
                                                >
                                                    <div className="text-xs font-medium text-slate-400 mb-2">
                                                        {change.field}
                                                    </div>
                                                    <div className="flex gap-2 text-xs">
                                                        <div className="flex-1 p-2 bg-red-500/10 rounded border border-red-500/20">
                                                            <span className="text-red-400">- </span>
                                                            <code className="text-red-300">
                                                                {formatValue(change.oldValue)}
                                                            </code>
                                                        </div>
                                                        <div className="flex-1 p-2 bg-green-500/10 rounded border border-green-500/20">
                                                            <span className="text-green-400">+ </span>
                                                            <code className="text-green-300">
                                                                {formatValue(change.newValue)}
                                                            </code>
                                                        </div>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
};

export default VersionHistory;
