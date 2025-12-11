import React from 'react';
import { clsx } from 'clsx';
import { ArrowRight } from 'lucide-react';
import { Link } from 'react-router-dom';

interface GlossaryCardProps {
    title: string;
    subtitle?: string; // e.g., "Attributes: 5"
    tags?: string[];
    linkTo: string;
    children?: React.ReactNode;
    accentColor?: "cyan" | "violet" | "aqua";
}

export const GlossaryCard: React.FC<GlossaryCardProps> = ({
    title, subtitle, tags = [], linkTo, children, accentColor = "cyan"
}) => {
    const safeTags = Array.isArray(tags) ? tags : [];
    const borderColors = {
        cyan: "hover:border-cyan-400/50",
        violet: "hover:border-violet-400/50",
        aqua: "hover:border-emerald-400/50",
    };

    const textColors = {
        cyan: "text-cyan-400",
        violet: "text-violet-400",
        aqua: "text-emerald-400"
    };

    return (
        <Link to={linkTo} className={clsx(
            "block p-5 rounded-xl border border-white/5 bg-[#151821] transition-all duration-300 group",
            "hover:-translate-y-1 hover:shadow-lg hover:shadow-cyan-900/10",
            borderColors[accentColor]
        )}>
            <div className="flex justify-between items-start mb-3">
                <div>
                    <h3 className={clsx("text-lg font-bold font-mono group-hover:text-white transition-colors", textColors[accentColor])}>
                        {title}
                    </h3>
                    {subtitle && <p className="text-xs text-slate-400 mt-1">{subtitle}</p>}
                </div>
                <ArrowRight className="w-4 h-4 text-slate-600 group-hover:text-white transition-colors" />
            </div>

            {children && <div className="mb-4 text-sm text-slate-300 line-clamp-2">{children}</div>}

            <div className="flex flex-wrap gap-2 mt-auto">
                {safeTags.map(t => (
                    <span key={t} className="px-2 py-0.5 text-[10px] uppercase font-bold tracking-wider rounded bg-white/5 text-slate-400 border border-white/5">
                        {t}
                    </span>
                ))}
            </div>
        </Link>
    );
};
