import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    Search,
    Command,
    LayoutDashboard,
    Database,
    Ruler,
    GitFork,
    FileText,
    Settings,
    BarChart3,
    BookOpen,
    ArrowRight,
    Hash,
    Clock,
    Sparkles,
    X
} from 'lucide-react';

interface CommandItem {
    id: string;
    title: string;
    subtitle?: string;
    icon: React.ElementType;
    category: 'navigation' | 'action' | 'recent' | 'search';
    action: () => void;
    keywords?: string[];
}

interface CommandPaletteProps {
    metrics?: { name: string; type: string }[];
    dimensions?: { name: string; type: string }[];
}

export const CommandPalette = ({ metrics = [], dimensions = [] }: CommandPaletteProps) => {
    const [isOpen, setIsOpen] = useState(false);
    const [query, setQuery] = useState('');
    const [selectedIndex, setSelectedIndex] = useState(0);
    const inputRef = useRef<HTMLInputElement>(null);
    const listRef = useRef<HTMLDivElement>(null);
    const navigate = useNavigate();

    // Load recent pages from local storage
    const [recentPages, setRecentPages] = useState<string[]>(() => {
        try {
            return JSON.parse(localStorage.getItem('axi_recent_pages') || '[]');
        } catch {
            return [];
        }
    });

    // Track page visits
    useEffect(() => {
        const currentPath = window.location.hash.replace('#', '') || '/';
        if (!recentPages.includes(currentPath)) {
            const updated = [currentPath, ...recentPages].slice(0, 5);
            setRecentPages(updated);
            localStorage.setItem('axi_recent_pages', JSON.stringify(updated));
        }
    }, []);

    // Base navigation commands
    const navigationCommands: CommandItem[] = useMemo(() => [
        {
            id: 'nav-home',
            title: 'Go to Home',
            subtitle: 'Dashboard overview',
            icon: LayoutDashboard,
            category: 'navigation',
            action: () => navigate('/'),
            keywords: ['home', 'dashboard', 'main']
        },
        {
            id: 'nav-metrics',
            title: 'Go to Metrics',
            subtitle: 'Browse all metrics',
            icon: BarChart3,
            category: 'navigation',
            action: () => navigate('/metrics'),
            keywords: ['metrics', 'kpi', 'measures']
        },
        {
            id: 'nav-dimensions',
            title: 'Go to Dimensions',
            subtitle: 'Browse all dimensions',
            icon: Ruler,
            category: 'navigation',
            action: () => navigate('/dimensions'),
            keywords: ['dimensions', 'attributes', 'fields']
        },
        {
            id: 'nav-models',
            title: 'Go to Models',
            subtitle: 'View data models',
            icon: Database,
            category: 'navigation',
            action: () => navigate('/models'),
            keywords: ['models', 'tables', 'entities']
        },
        {
            id: 'nav-query',
            title: 'Go to Query Builder',
            subtitle: 'Build semantic queries',
            icon: Sparkles,
            category: 'navigation',
            action: () => navigate('/query'),
            keywords: ['query', 'sql', 'search', 'explore']
        },
        {
            id: 'nav-graph',
            title: 'Go to Graph Explorer',
            subtitle: 'Visualize relationships',
            icon: GitFork,
            category: 'navigation',
            action: () => navigate('/graph'),
            keywords: ['graph', 'lineage', 'relationships', 'visual']
        },
        {
            id: 'nav-saved',
            title: 'Go to Saved Queries',
            subtitle: 'View saved queries',
            icon: FileText,
            category: 'navigation',
            action: () => navigate('/saved-queries'),
            keywords: ['saved', 'queries', 'bookmarks']
        },
        {
            id: 'nav-docs',
            title: 'Go to Documentation',
            subtitle: 'Read the docs',
            icon: BookOpen,
            category: 'navigation',
            action: () => navigate('/docs'),
            keywords: ['docs', 'documentation', 'help', 'guide']
        },
        {
            id: 'nav-settings',
            title: 'Go to Settings',
            subtitle: 'Configure AXI',
            icon: Settings,
            category: 'navigation',
            action: () => navigate('/settings'),
            keywords: ['settings', 'config', 'preferences']
        },
        {
            id: 'nav-compare',
            title: 'Compare Metrics',
            subtitle: 'Side-by-side comparison',
            icon: BarChart3,
            category: 'navigation',
            action: () => navigate('/metrics/compare'),
            keywords: ['compare', 'diff', 'versus']
        }
    ], [navigate]);

    // Dynamic metric commands
    const metricCommands: CommandItem[] = useMemo(() =>
        metrics.slice(0, 10).map(metric => ({
            id: `metric-${metric.name}`,
            title: metric.name,
            subtitle: `${metric.type} metric`,
            icon: Hash,
            category: 'search' as const,
            action: () => navigate(`/metrics/${encodeURIComponent(metric.name)}`),
            keywords: [metric.name.toLowerCase(), 'metric']
        })), [metrics, navigate]);

    // Dynamic dimension commands
    const dimensionCommands: CommandItem[] = useMemo(() =>
        dimensions.slice(0, 10).map(dim => ({
            id: `dim-${dim.name}`,
            title: dim.name,
            subtitle: `${dim.type} dimension`,
            icon: Ruler,
            category: 'search' as const,
            action: () => navigate(`/dimensions/${encodeURIComponent(dim.name)}`),
            keywords: [dim.name.toLowerCase(), 'dimension']
        })), [dimensions, navigate]);

    // Action commands
    const actionCommands: CommandItem[] = useMemo(() => [
        {
            id: 'action-new-query',
            title: 'New Query',
            subtitle: 'Start a new semantic query',
            icon: Sparkles,
            category: 'action',
            action: () => navigate('/query'),
            keywords: ['new', 'create', 'query']
        }
    ], [navigate]);

    // Recent page commands
    const recentCommands: CommandItem[] = useMemo(() => {
        const pageNames: Record<string, { title: string; icon: React.ElementType }> = {
            '/': { title: 'Home', icon: LayoutDashboard },
            '/metrics': { title: 'Metrics', icon: BarChart3 },
            '/dimensions': { title: 'Dimensions', icon: Ruler },
            '/models': { title: 'Models', icon: Database },
            '/query': { title: 'Query Builder', icon: Sparkles },
            '/graph': { title: 'Graph Explorer', icon: GitFork },
            '/settings': { title: 'Settings', icon: Settings },
            '/docs': { title: 'Documentation', icon: BookOpen }
        };

        return recentPages.slice(0, 3).map((path, i) => {
            const info = pageNames[path] || { title: path, icon: FileText };
            return {
                id: `recent-${i}`,
                title: info.title,
                subtitle: 'Recently visited',
                icon: Clock,
                category: 'recent' as const,
                action: () => navigate(path),
                keywords: []
            };
        });
    }, [recentPages, navigate]);

    // All commands
    const allCommands = useMemo(() => [
        ...navigationCommands,
        ...actionCommands,
        ...metricCommands,
        ...dimensionCommands
    ], [navigationCommands, actionCommands, metricCommands, dimensionCommands]);

    // Filtered commands based on search
    const filteredCommands = useMemo(() => {
        if (!query.trim()) {
            // Show recent + navigation when no query
            return [...recentCommands, ...navigationCommands.slice(0, 6)];
        }

        const q = query.toLowerCase();
        return allCommands.filter(cmd => {
            const titleMatch = cmd.title.toLowerCase().includes(q);
            const subtitleMatch = cmd.subtitle?.toLowerCase().includes(q);
            const keywordMatch = cmd.keywords?.some(k => k.includes(q));
            return titleMatch || subtitleMatch || keywordMatch;
        }).slice(0, 10);
    }, [query, allCommands, recentCommands, navigationCommands]);

    // Reset selection when filtered results change
    useEffect(() => {
        setSelectedIndex(0);
    }, [filteredCommands.length]);

    // Keyboard shortcut to open
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            // Cmd+K or Ctrl+K to open
            if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
                e.preventDefault();
                setIsOpen(true);
            }
            // Escape to close
            if (e.key === 'Escape' && isOpen) {
                setIsOpen(false);
            }
        };

        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [isOpen]);

    // Focus input when opened
    useEffect(() => {
        if (isOpen) {
            setTimeout(() => inputRef.current?.focus(), 0);
        } else {
            setQuery('');
            setSelectedIndex(0);
        }
    }, [isOpen]);

    // Handle keyboard navigation
    const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault();
                setSelectedIndex(i => Math.min(i + 1, filteredCommands.length - 1));
                break;
            case 'ArrowUp':
                e.preventDefault();
                setSelectedIndex(i => Math.max(i - 1, 0));
                break;
            case 'Enter':
                e.preventDefault();
                if (filteredCommands[selectedIndex]) {
                    filteredCommands[selectedIndex].action();
                    setIsOpen(false);
                }
                break;
            case 'Escape':
                setIsOpen(false);
                break;
        }
    }, [filteredCommands, selectedIndex]);

    // Scroll selected item into view
    useEffect(() => {
        const selected = listRef.current?.querySelector(`[data-index="${selectedIndex}"]`);
        selected?.scrollIntoView({ block: 'nearest' });
    }, [selectedIndex]);

    if (!isOpen) return null;

    const getCategoryLabel = (category: string) => {
        switch (category) {
            case 'recent': return 'Recent';
            case 'navigation': return 'Navigation';
            case 'action': return 'Actions';
            case 'search': return 'Results';
            default: return category;
        }
    };

    // Group commands by category
    const groupedCommands = filteredCommands.reduce((acc, cmd) => {
        if (!acc[cmd.category]) acc[cmd.category] = [];
        acc[cmd.category].push(cmd);
        return acc;
    }, {} as Record<string, CommandItem[]>);

    let globalIndex = 0;

    return (
        <>
            {/* Backdrop */}
            <div
                className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50"
                onClick={() => setIsOpen(false)}
            />

            {/* Modal */}
            <div className="fixed inset-x-4 top-[20%] max-w-xl mx-auto z-50">
                <div className="bg-[#151821] border border-white/10 rounded-2xl shadow-2xl overflow-hidden">
                    {/* Search Input */}
                    <div className="flex items-center gap-3 px-4 py-3 border-b border-white/10">
                        <Search className="w-5 h-5 text-slate-400" />
                        <input
                            ref={inputRef}
                            type="text"
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                            onKeyDown={handleKeyDown}
                            placeholder="Search commands, pages, metrics..."
                            className="flex-1 bg-transparent text-white text-sm placeholder-slate-500 outline-none"
                        />
                        <div className="flex items-center gap-1 px-2 py-1 bg-white/5 rounded text-xs text-slate-500">
                            <Command className="w-3 h-3" />
                            <span>K</span>
                        </div>
                        <button
                            onClick={() => setIsOpen(false)}
                            className="p-1 text-slate-500 hover:text-white transition-colors"
                        >
                            <X className="w-4 h-4" />
                        </button>
                    </div>

                    {/* Results */}
                    <div ref={listRef} className="max-h-[400px] overflow-y-auto p-2">
                        {filteredCommands.length === 0 ? (
                            <div className="p-8 text-center text-slate-500">
                                <Search className="w-8 h-8 mx-auto mb-2 opacity-50" />
                                <p>No results found for "{query}"</p>
                            </div>
                        ) : (
                            Object.entries(groupedCommands).map(([category, commands]) => (
                                <div key={category} className="mb-2">
                                    <div className="px-3 py-1 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                                        {getCategoryLabel(category)}
                                    </div>
                                    {commands.map(cmd => {
                                        const idx = globalIndex++;
                                        const Icon = cmd.icon;
                                        return (
                                            <button
                                                key={cmd.id}
                                                data-index={idx}
                                                onClick={() => {
                                                    cmd.action();
                                                    setIsOpen(false);
                                                }}
                                                onMouseEnter={() => setSelectedIndex(idx)}
                                                className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-left transition-colors ${
                                                    selectedIndex === idx
                                                        ? 'bg-cyan-500/20 text-white'
                                                        : 'text-slate-300 hover:bg-white/5'
                                                }`}
                                            >
                                                <div className={`p-1.5 rounded-lg ${
                                                    selectedIndex === idx
                                                        ? 'bg-cyan-500/30'
                                                        : 'bg-white/5'
                                                }`}>
                                                    <Icon className={`w-4 h-4 ${
                                                        selectedIndex === idx
                                                            ? 'text-cyan-400'
                                                            : 'text-slate-400'
                                                    }`} />
                                                </div>
                                                <div className="flex-1 min-w-0">
                                                    <div className="text-sm font-medium truncate">
                                                        {cmd.title}
                                                    </div>
                                                    {cmd.subtitle && (
                                                        <div className="text-xs text-slate-500 truncate">
                                                            {cmd.subtitle}
                                                        </div>
                                                    )}
                                                </div>
                                                {selectedIndex === idx && (
                                                    <ArrowRight className="w-4 h-4 text-cyan-400" />
                                                )}
                                            </button>
                                        );
                                    })}
                                </div>
                            ))
                        )}
                    </div>

                    {/* Footer */}
                    <div className="border-t border-white/10 px-4 py-2 flex items-center gap-4 text-xs text-slate-500">
                        <span className="flex items-center gap-1">
                            <kbd className="px-1.5 py-0.5 bg-white/5 rounded">↑↓</kbd>
                            navigate
                        </span>
                        <span className="flex items-center gap-1">
                            <kbd className="px-1.5 py-0.5 bg-white/5 rounded">↵</kbd>
                            select
                        </span>
                        <span className="flex items-center gap-1">
                            <kbd className="px-1.5 py-0.5 bg-white/5 rounded">esc</kbd>
                            close
                        </span>
                    </div>
                </div>
            </div>
        </>
    );
};

// Hook for registering keyboard shortcuts elsewhere
export const useKeyboardShortcut = (key: string, callback: () => void, ctrl = false) => {
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            const ctrlPressed = e.metaKey || e.ctrlKey;
            if (ctrlPressed === ctrl && e.key.toLowerCase() === key.toLowerCase()) {
                e.preventDefault();
                callback();
            }
        };

        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [key, callback, ctrl]);
};

export default CommandPalette;
