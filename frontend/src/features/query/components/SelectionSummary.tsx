import React from 'react';
import { X } from 'lucide-react';

interface SelectionSummaryProps {
  metrics: string[];
  dimensions: string[];
  onRemoveMetric: (metric: string) => void;
  onRemoveDimension: (dimension: string) => void;
}

export const SelectionSummary: React.FC<SelectionSummaryProps> = ({
  metrics,
  dimensions,
  onRemoveMetric,
  onRemoveDimension,
}) => {
  if (metrics.length === 0 && dimensions.length === 0) {
    return null;
  }

  return (
    <div className="p-4 bg-[#151821] border border-white/10 rounded-lg space-y-3">
      {metrics.length > 0 && (
        <div>
          <div className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">
            Metrics ({metrics.length})
          </div>
          <div className="flex flex-wrap gap-2">
            {metrics.map((metric) => (
              <span
                key={metric}
                className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 text-sm"
              >
                {metric}
                <button
                  onClick={() => onRemoveMetric(metric)}
                  className="hover:text-cyan-300 transition-colors"
                >
                  <X className="w-3 h-3" />
                </button>
              </span>
            ))}
          </div>
        </div>
      )}

      {dimensions.length > 0 && (
        <div>
          <div className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">
            Dimensions ({dimensions.length})
          </div>
          <div className="flex flex-wrap gap-2">
            {dimensions.map((dimension) => (
              <span
                key={dimension}
                className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-violet-500/10 text-violet-400 border border-violet-500/20 text-sm"
              >
                {dimension}
                <button
                  onClick={() => onRemoveDimension(dimension)}
                  className="hover:text-violet-300 transition-colors"
                >
                  <X className="w-3 h-3" />
                </button>
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

