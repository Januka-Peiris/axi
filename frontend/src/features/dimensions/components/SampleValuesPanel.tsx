import React, { useState } from 'react';
import { ChevronDown, ChevronUp, Loader2 } from 'lucide-react';
import { useDimensionSamples } from '../api/getDimensionSamples';

interface SampleValuesPanelProps {
  dimensionId: string;
}

export const SampleValuesPanel: React.FC<SampleValuesPanelProps> = ({ dimensionId }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const { data: samples, isLoading, error } = useDimensionSamples(dimensionId, isExpanded);

  return (
    <div className="rounded-xl border border-white/10 bg-[#151821] overflow-hidden">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full p-4 flex items-center justify-between hover:bg-white/5 transition-colors"
      >
        <div className="flex items-center gap-2">
          <h3 className="text-lg font-bold text-white">Sample Values</h3>
          <span className="text-xs text-slate-500">
            (First 50 values from warehouse)
          </span>
        </div>
        {isExpanded ? (
          <ChevronUp className="w-5 h-5 text-slate-400" />
        ) : (
          <ChevronDown className="w-5 h-5 text-slate-400" />
        )}
      </button>

      {isExpanded && (
        <div className="border-t border-white/10">
          {isLoading ? (
            <div className="p-10 flex justify-center">
              <Loader2 className="animate-spin text-cyan-500 w-6 h-6" />
            </div>
          ) : error ? (
            <div className="p-8 text-center text-red-400">
              Failed to load sample values
            </div>
          ) : samples && samples.length > 0 ? (
            <div className="max-h-96 overflow-y-auto">
              <table className="w-full text-left">
                <thead className="bg-white/5 border-b border-white/10 sticky top-0">
                  <tr>
                    <th className="p-4 font-semibold text-slate-300">Value</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {samples.map((sample, idx) => (
                    <tr key={idx} className="hover:bg-white/5 transition-colors">
                      <td className="p-4 font-mono text-cyan-400 text-sm">{sample.value}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="p-8 text-center text-slate-500 italic">
              No sample values available
            </div>
          )}
        </div>
      )}
    </div>
  );
};

