import React from 'react';
import Prism from 'prismjs';
import 'prismjs/components/prism-sql';
import 'prismjs/themes/prism-tomorrow.css';
import type { GlossaryMetric } from '../../api/glossary';

interface Props {
    metric: GlossaryMetric;
}

export const MetricDefinitionCard: React.FC<Props> = ({ metric }) => {
    const html = Prism.highlight(metric.expression, Prism.languages.sql, 'sql');

    return (
        <div className="p-6 rounded-xl bg-[#151821] border border-white/10">
            <h3 className="text-xl font-bold text-white mb-2">{metric.name}</h3>
            {metric.description && <p className="text-slate-400 mb-4">{metric.description}</p>}

            <div className="space-y-4">
                <div>
                    <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">Expression</label>
                    <div className="mt-1 p-3 bg-[#0d0f15] rounded border border-white/5 font-mono text-sm overflow-x-auto">
                        <pre dangerouslySetInnerHTML={{ __html: html }} className="!bg-transparent !m-0 !p-0" />
                    </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                    <div>
                        <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">Type</label>
                        <p className="font-mono text-violet-400">{metric.metric_type}</p>
                    </div>
                    <div>
                        <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">Grain</label>
                        <p className="text-slate-300">{metric.grain || 'N/A'}</p>
                    </div>
                </div>

                {(Array.isArray(metric.default_filters) ? metric.default_filters : []).length > 0 && (
                    <div>
                        <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">Default Filters</label>
                        <div className="flex flex-wrap gap-2 mt-1">
                            {(Array.isArray(metric.default_filters) ? metric.default_filters : []).map((f, i) => (
                                <span key={i} className="px-2 py-1 rounded bg-red-500/10 text-red-400 font-mono text-xs border border-red-500/20">{f}</span>
                            ))}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};
