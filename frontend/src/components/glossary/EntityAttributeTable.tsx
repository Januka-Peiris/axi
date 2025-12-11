import type { GlossaryAttribute } from '../../api/glossary';
import { Key, Link as LinkIcon } from 'lucide-react';

interface Props {
    attributes: GlossaryAttribute[];
}

export const EntityAttributeTable: React.FC<Props> = ({ attributes = [] }) => {
    const safeAttrs = Array.isArray(attributes) ? attributes : [];

    return (
        <div className="w-full overflow-hidden rounded-lg border border-white/10 bg-[#151821]">
            <table className="w-full text-left text-sm">
                <thead>
                    <tr className="border-b border-white/10 bg-white/5">
                        <th className="p-3 font-semibold text-slate-300">Attribute</th>
                        <th className="p-3 font-semibold text-slate-300">Type</th>
                        <th className="p-3 font-semibold text-slate-300">Description</th>
                        <th className="p-3 font-semibold text-slate-300">Keys</th>
                        <th className="p-3 font-semibold text-slate-300">Source</th>
                    </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                    {safeAttrs.map((attr) => (
                        <tr key={attr.name} className="hover:bg-white/5 transition-colors">
                            <td className="p-3 font-mono text-cyan-400">{attr.name}</td>
                            <td className="p-3 text-slate-400 font-mono text-xs">{attr.data_type}</td>
                            <td className="p-3 text-slate-400 max-w-xs truncate" title={attr.description}>{attr.description || '-'}</td>
                            <td className="p-3">
                                <div className="flex gap-2">
                                    {attr.is_pk && <span title="Primary Key" className="p-1 rounded bg-amber-500/10 text-amber-500"><Key className="w-3 h-3" /></span>}
                                    {attr.is_fk && <span title="Foreign Key" className="p-1 rounded bg-blue-500/10 text-blue-500"><LinkIcon className="w-3 h-3" /></span>}
                                </div>
                            </td>
                            <td className="p-3 text-slate-500 text-xs font-mono">{attr.source_column}</td>
                        </tr>
                    ))}
                    {safeAttrs.length === 0 && (
                        <tr>
                            <td colSpan={5} className="p-8 text-center text-slate-600 italic">No attributes found.</td>
                        </tr>
                    )}
                </tbody>
            </table>
        </div>
    );
};
