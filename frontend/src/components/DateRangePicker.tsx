import { useState, useMemo } from 'react';
import { Calendar, ChevronDown, Check } from 'lucide-react';

export interface DateRange {
    start: string;
    end: string;
    label?: string;
    preset?: string;
}

interface DateRangePickerProps {
    value?: DateRange;
    onChange: (range: DateRange) => void;
    className?: string;
}

type PresetKey = 'today' | 'yesterday' | 'last7' | 'last30' | 'last90' | 'mtd' | 'qtd' | 'ytd' | 'lastMonth' | 'lastQuarter' | 'lastYear' | 'custom';

interface Preset {
    key: PresetKey;
    label: string;
    getRange: () => { start: string; end: string };
}

const formatDate = (date: Date): string => {
    return date.toISOString().split('T')[0];
};

const PRESETS: Preset[] = [
    {
        key: 'today',
        label: 'Today',
        getRange: () => {
            const today = formatDate(new Date());
            return { start: today, end: today };
        }
    },
    {
        key: 'yesterday',
        label: 'Yesterday',
        getRange: () => {
            const yesterday = new Date();
            yesterday.setDate(yesterday.getDate() - 1);
            const date = formatDate(yesterday);
            return { start: date, end: date };
        }
    },
    {
        key: 'last7',
        label: 'Last 7 Days',
        getRange: () => {
            const end = new Date();
            const start = new Date();
            start.setDate(start.getDate() - 6);
            return { start: formatDate(start), end: formatDate(end) };
        }
    },
    {
        key: 'last30',
        label: 'Last 30 Days',
        getRange: () => {
            const end = new Date();
            const start = new Date();
            start.setDate(start.getDate() - 29);
            return { start: formatDate(start), end: formatDate(end) };
        }
    },
    {
        key: 'last90',
        label: 'Last 90 Days',
        getRange: () => {
            const end = new Date();
            const start = new Date();
            start.setDate(start.getDate() - 89);
            return { start: formatDate(start), end: formatDate(end) };
        }
    },
    {
        key: 'mtd',
        label: 'Month to Date',
        getRange: () => {
            const end = new Date();
            const start = new Date(end.getFullYear(), end.getMonth(), 1);
            return { start: formatDate(start), end: formatDate(end) };
        }
    },
    {
        key: 'qtd',
        label: 'Quarter to Date',
        getRange: () => {
            const end = new Date();
            const quarter = Math.floor(end.getMonth() / 3);
            const start = new Date(end.getFullYear(), quarter * 3, 1);
            return { start: formatDate(start), end: formatDate(end) };
        }
    },
    {
        key: 'ytd',
        label: 'Year to Date',
        getRange: () => {
            const end = new Date();
            const start = new Date(end.getFullYear(), 0, 1);
            return { start: formatDate(start), end: formatDate(end) };
        }
    },
    {
        key: 'lastMonth',
        label: 'Last Month',
        getRange: () => {
            const now = new Date();
            const start = new Date(now.getFullYear(), now.getMonth() - 1, 1);
            const end = new Date(now.getFullYear(), now.getMonth(), 0);
            return { start: formatDate(start), end: formatDate(end) };
        }
    },
    {
        key: 'lastQuarter',
        label: 'Last Quarter',
        getRange: () => {
            const now = new Date();
            const currentQuarter = Math.floor(now.getMonth() / 3);
            const lastQuarter = currentQuarter - 1;
            const year = lastQuarter < 0 ? now.getFullYear() - 1 : now.getFullYear();
            const quarter = lastQuarter < 0 ? 3 : lastQuarter;
            const start = new Date(year, quarter * 3, 1);
            const end = new Date(year, quarter * 3 + 3, 0);
            return { start: formatDate(start), end: formatDate(end) };
        }
    },
    {
        key: 'lastYear',
        label: 'Last Year',
        getRange: () => {
            const now = new Date();
            const start = new Date(now.getFullYear() - 1, 0, 1);
            const end = new Date(now.getFullYear() - 1, 11, 31);
            return { start: formatDate(start), end: formatDate(end) };
        }
    },
];

export const DateRangePicker = ({ value, onChange, className = '' }: DateRangePickerProps) => {
    const [isOpen, setIsOpen] = useState(false);
    const [customStart, setCustomStart] = useState(value?.start || '');
    const [customEnd, setCustomEnd] = useState(value?.end || '');

    const displayLabel = useMemo(() => {
        if (!value) return 'Select date range';
        if (value.label) return value.label;
        return `${value.start} to ${value.end}`;
    }, [value]);

    const handlePresetClick = (preset: Preset) => {
        const range = preset.getRange();
        onChange({
            ...range,
            label: preset.label,
            preset: preset.key
        });
        setIsOpen(false);
    };

    const handleCustomApply = () => {
        if (customStart && customEnd) {
            onChange({
                start: customStart,
                end: customEnd,
                label: `${customStart} to ${customEnd}`,
                preset: 'custom'
            });
            setIsOpen(false);
        }
    };

    return (
        <div className={`relative ${className}`}>
            {/* Trigger Button */}
            <button
                onClick={() => setIsOpen(!isOpen)}
                className="flex items-center gap-2 px-4 py-2 bg-[#151821] border border-white/10 rounded-lg hover:border-cyan-500/50 transition-colors w-full"
            >
                <Calendar className="w-4 h-4 text-cyan-400" />
                <span className="text-sm text-slate-300 flex-1 text-left">{displayLabel}</span>
                <ChevronDown className={`w-4 h-4 text-slate-400 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
            </button>

            {/* Dropdown */}
            {isOpen && (
                <>
                    {/* Backdrop */}
                    <div
                        className="fixed inset-0 z-40"
                        onClick={() => setIsOpen(false)}
                    />

                    {/* Panel */}
                    <div className="absolute top-full left-0 mt-2 bg-[#151821] border border-white/10 rounded-xl shadow-xl z-50 min-w-[320px]">
                        <div className="p-4">
                            <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
                                Quick Select
                            </h4>

                            {/* Presets Grid */}
                            <div className="grid grid-cols-2 gap-2 mb-4">
                                {PRESETS.map(preset => (
                                    <button
                                        key={preset.key}
                                        onClick={() => handlePresetClick(preset)}
                                        className={`px-3 py-2 text-sm rounded-lg text-left transition-colors flex items-center justify-between ${
                                            value?.preset === preset.key
                                                ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/30'
                                                : 'bg-white/5 text-slate-300 hover:bg-white/10 border border-transparent'
                                        }`}
                                    >
                                        {preset.label}
                                        {value?.preset === preset.key && (
                                            <Check className="w-4 h-4" />
                                        )}
                                    </button>
                                ))}
                            </div>

                            {/* Custom Range */}
                            <div className="border-t border-white/10 pt-4">
                                <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
                                    Custom Range
                                </h4>
                                <div className="flex gap-2 mb-3">
                                    <div className="flex-1">
                                        <label className="text-xs text-slate-500 mb-1 block">Start</label>
                                        <input
                                            type="date"
                                            value={customStart}
                                            onChange={(e) => setCustomStart(e.target.value)}
                                            className="w-full px-3 py-2 bg-black/30 border border-white/10 rounded-lg text-sm text-white focus:outline-none focus:border-cyan-500"
                                        />
                                    </div>
                                    <div className="flex-1">
                                        <label className="text-xs text-slate-500 mb-1 block">End</label>
                                        <input
                                            type="date"
                                            value={customEnd}
                                            onChange={(e) => setCustomEnd(e.target.value)}
                                            className="w-full px-3 py-2 bg-black/30 border border-white/10 rounded-lg text-sm text-white focus:outline-none focus:border-cyan-500"
                                        />
                                    </div>
                                </div>
                                <button
                                    onClick={handleCustomApply}
                                    disabled={!customStart || !customEnd}
                                    className="w-full px-4 py-2 bg-cyan-500 hover:bg-cyan-600 disabled:bg-slate-700 disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg transition-colors"
                                >
                                    Apply Custom Range
                                </button>
                            </div>
                        </div>
                    </div>
                </>
            )}
        </div>
    );
};

// Comparison Selector
interface ComparisonOption {
    key: string;
    label: string;
    description: string;
}

const COMPARISON_OPTIONS: ComparisonOption[] = [
    { key: 'none', label: 'No Comparison', description: 'Show data for selected period only' },
    { key: 'previous_period', label: 'Previous Period', description: 'Compare to immediately preceding period' },
    { key: 'previous_year', label: 'Previous Year', description: 'Compare to same period last year (YoY)' },
    { key: 'previous_month', label: 'Previous Month', description: 'Compare to same period last month (MoM)' },
    { key: 'previous_quarter', label: 'Previous Quarter', description: 'Compare to same period last quarter (QoQ)' },
];

interface ComparisonSelectorProps {
    value: string;
    onChange: (value: string) => void;
}

export const ComparisonSelector = ({ value, onChange }: ComparisonSelectorProps) => {
    const [isOpen, setIsOpen] = useState(false);
    const selected = COMPARISON_OPTIONS.find(o => o.key === value) || COMPARISON_OPTIONS[0];

    return (
        <div className="relative">
            <button
                onClick={() => setIsOpen(!isOpen)}
                className="flex items-center gap-2 px-4 py-2 bg-[#151821] border border-white/10 rounded-lg hover:border-cyan-500/50 transition-colors"
            >
                <span className="text-sm text-slate-300">{selected.label}</span>
                <ChevronDown className={`w-4 h-4 text-slate-400 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
            </button>

            {isOpen && (
                <>
                    <div className="fixed inset-0 z-40" onClick={() => setIsOpen(false)} />
                    <div className="absolute top-full left-0 mt-2 bg-[#151821] border border-white/10 rounded-xl shadow-xl z-50 min-w-[280px]">
                        <div className="p-2">
                            {COMPARISON_OPTIONS.map(option => (
                                <button
                                    key={option.key}
                                    onClick={() => {
                                        onChange(option.key);
                                        setIsOpen(false);
                                    }}
                                    className={`w-full px-3 py-2 rounded-lg text-left transition-colors ${
                                        value === option.key
                                            ? 'bg-cyan-500/20 text-cyan-400'
                                            : 'hover:bg-white/5 text-slate-300'
                                    }`}
                                >
                                    <div className="text-sm font-medium">{option.label}</div>
                                    <div className="text-xs text-slate-500">{option.description}</div>
                                </button>
                            ))}
                        </div>
                    </div>
                </>
            )}
        </div>
    );
};

export default DateRangePicker;
