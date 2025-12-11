import React from 'react';
import { Type } from 'lucide-react';

interface Props {
    attributes: string[];
}

export const DimensionTable: React.FC<Props> = ({ attributes = [] }) => {
    const safeAttrs = Array.isArray(attributes) ? attributes : [];

    return (
        <div className="w-full overflow-hidden rounded-lg border border-white/10 bg-[#151821]">
            <table className="w-full text-left text-sm">
                <thead>
                    <tr className="border-b border-white/10 bg-white/5">
                        <th className="p-3 font-semibold text-slate-300">Attribute Name</th>
                        <th className="p-3 font-semibold text-slate-300">Type</th>
                    </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                    {safeAttrs.map((attr) => (
                        <tr key={attr} className="hover:bg-white/5 transition-colors">
                            <td className="p-3 font-mono text-cyan-400">{attr}</td>
                            <td className="p-3">
                                <span className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-violet-500/10 text-violet-400 border border-violet-500/20 w-fit text-xs font-mono">
                                    <Type size={10} />
                                    dimension
                                </span>
                            </td>
                        </tr>
                    ))}
                    {safeAttrs.length === 0 && (
                        <tr>
                            <td colSpan={2} className="p-8 text-center text-slate-600 italic">No attributes explicitly mapped.</td>
                        </tr>
                    )}
                </tbody>
            </table>
        </div>
    );
};
