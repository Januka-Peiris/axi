import React from 'react';
import Prism from 'prismjs';
import 'prismjs/components/prism-sql';
import 'prismjs/themes/prism-tomorrow.css';

interface MetricExpressionProps {
  expression: string;
}

export const MetricExpression: React.FC<MetricExpressionProps> = ({ expression }) => {
  const html = Prism.highlight(expression, Prism.languages.sql, 'sql');

  return (
    <div className="p-6 rounded-xl bg-[#151821] border border-white/10">
      <label className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2 block">
        Expression
      </label>
      <div className="p-3 bg-[#0d0f15] rounded border border-white/5 font-mono text-sm overflow-x-auto">
        <pre dangerouslySetInnerHTML={{ __html: html }} className="!bg-transparent !m-0 !p-0" />
      </div>
    </div>
  );
};

