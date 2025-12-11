import React from 'react';
import { NavLink, Link } from 'react-router-dom';
import { BookOpen, Box, ArrowLeft } from 'lucide-react';

interface Props {
    children: React.ReactNode;
}

const docsNav = [
    { title: "Introduction", path: "/docs" },
    { title: "Semantic Models", path: "/docs/models" },
    { title: "Metrics Framework", path: "/docs/metrics" },
    { title: "Business Glossary", path: "/docs/glossary" },
    { title: "Snowflake Integration", path: "/docs/snowflake" },
];

export const DocsLayout: React.FC<Props> = ({ children }) => {
    return (
        <div className="flex h-screen bg-[#0d0f15]">
            {/* Sidebar */}
            <div className="w-64 border-r border-white/10 flex flex-col bg-[#111319]">
                <div className="p-4 border-b border-white/10">
                    <Link to="/" className="flex items-center gap-2 text-slate-400 hover:text-white transition-colors mb-4">
                        <ArrowLeft size={16} /> Back to App
                    </Link>
                    <div className="flex items-center gap-2 font-bold text-lg text-white">
                        <BookOpen className="text-cyan-400" />
                        <span>Documentation</span>
                    </div>
                </div>

                <nav className="flex-1 overflow-y-auto p-4 space-y-1">
                    {docsNav.map(item => (
                        <NavLink
                            key={item.path}
                            to={item.path}
                            end={item.path === "/docs"}
                            className={({ isActive }) => `
                                block px-3 py-2 rounded-md text-sm font-medium transition-colors
                                ${isActive
                                    ? "bg-cyan-500/10 text-cyan-400 border border-cyan-500/20"
                                    : "text-slate-400 hover:bg-white/5 hover:text-slate-200"}
                            `}
                        >
                            {item.title}
                        </NavLink>
                    ))}

                    <div className="pt-4 mt-4 border-t border-white/10">
                        <h4 className="px-3 text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Reference</h4>
                        <a href="https://github.com/axi-data/axi" target="_blank" rel="noreferrer" className="block px-3 py-2 rounded-md text-sm font-medium text-slate-400 hover:text-white hover:bg-white/5 flex items-center gap-2">
                            <Box size={14} /> CLI Commands
                        </a>
                    </div>
                </nav>
            </div>

            {/* Main Content */}
            <div className="flex-1 overflow-y-auto">
                <div className="max-w-4xl mx-auto p-8 lg:p-12">
                    {children}
                </div>
            </div>
        </div>
    );
};
