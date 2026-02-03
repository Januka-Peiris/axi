import React, { useState } from 'react';
import { X, Copy, Check } from 'lucide-react';
import { useSemanticQuery } from '../api/runSemanticQuery';
import type { MetricDetail } from '../api/getMetric';
import Prism from 'prismjs';
import 'prismjs/components/prism-sql';
import 'prismjs/themes/prism-tomorrow.css';

interface GeneratedSqlModalProps {
  metric: MetricDetail;
  isOpen: boolean;
  onClose: () => void;
}

export const GeneratedSqlModal: React.FC<GeneratedSqlModalProps> = ({
  metric,
  isOpen,
  onClose,
}) => {
  const [copied, setCopied] = useState(false);
  const { mutate: runQuery, data: queryResult, isPending, error } = useSemanticQuery();

  const handleGenerate = () => {
    runQuery({
      metrics: [metric.name],
      dimensions: metric.default_dimensions || [],
      filters: [],
    });
  };

  const handleCopy = () => {
    if (queryResult?.sql) {
      navigator.clipboard.writeText(queryResult.sql);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  if (!isOpen) return null;

  const sqlHtml = queryResult?.sql
    ? Prism.highlight(queryResult.sql, Prism.languages.sql, 'sql')
    : '';

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-[#151821] rounded-xl border border-white/10 max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-white/10">
          <h2 className="text-xl font-bold text-white">Semantic query SQL (ad-hoc)</h2>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {!queryResult && !isPending && (
            <div className="text-center py-8">
              <p className="text-slate-400 mb-4">Click Generate to create SQL for this metric</p>
              <button
                onClick={handleGenerate}
                className="px-4 py-2 bg-cyan-500 hover:bg-cyan-600 text-white rounded-lg font-medium transition-colors"
              >
                Generate SQL
              </button>
            </div>
          )}

          {isPending && (
            <div className="text-center py-8">
              <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-cyan-500"></div>
              <p className="text-slate-400 mt-4">Generating SQL...</p>
            </div>
          )}

          {error && (
            <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400">
              Error: {error instanceof Error ? error.message : 'Failed to generate SQL'}
            </div>
          )}

          {queryResult && (
            <>
              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                    Generated SQL
                  </label>
                  <button
                    onClick={handleCopy}
                    className="flex items-center gap-2 px-3 py-1 text-xs bg-white/5 hover:bg-white/10 rounded border border-white/10 transition-colors"
                  >
                    {copied ? (
                      <>
                        <Check className="w-3 h-3" />
                        Copied
                      </>
                    ) : (
                      <>
                        <Copy className="w-3 h-3" />
                        Copy
                      </>
                    )}
                  </button>
                </div>
                <div className="p-4 bg-[#0d0f15] rounded border border-white/5 font-mono text-sm overflow-x-auto">
                  <pre
                    dangerouslySetInnerHTML={{ __html: sqlHtml }}
                    className="!bg-transparent !m-0 !p-0"
                  />
                </div>
              </div>

              {queryResult.preview && queryResult.preview.length > 0 && (
                <div>
                  <label className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2 block">
                    Preview (First 20 rows)
                  </label>
                  <div className="rounded-xl border border-white/10 bg-[#0d0f15] overflow-hidden">
                    <table className="w-full text-left text-sm">
                      <thead className="bg-white/5 border-b border-white/10">
                        <tr>
                          {Object.keys(queryResult.preview[0] || {}).map((key) => (
                            <th key={key} className="p-3 font-semibold text-slate-300">
                              {key}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-white/5">
                        {queryResult.preview.map((row: any, idx: number) => (
                          <tr key={idx} className="hover:bg-white/5">
                            {Object.values(row).map((val: any, i: number) => (
                              <td key={i} className="p-3 text-slate-400 font-mono text-xs">
                                {String(val ?? '—')}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-white/10 flex justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-white/5 hover:bg-white/10 text-white rounded-lg font-medium transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

