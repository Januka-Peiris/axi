
import React from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { LayoutDashboard, Database, BarChart3, Layers, Terminal, Settings, BookOpen, Bookmark, GitFork, Command, Search } from 'lucide-react';
import clsx from 'clsx';
import { CommandPalette } from '../components/CommandPalette';

const NavItem = ({ to, icon: Icon, label }: { to: string; icon: any; label: string }) => (
    <NavLink
        to={to}
        className={({ isActive }) => clsx(
            "flex items-center gap-3 px-4 py-2 rounded-lg transition-colors font-medium text-sm",
            isActive ? 'bg-cyan-500/10 text-cyan-400' : 'text-slate-400 hover:text-white hover:bg-white/5'
        )}
    >
        <Icon className="w-5 h-5" />
        <span>{label}</span>
    </NavLink>
);

export const Shell: React.FC<{ children?: React.ReactNode }> = ({ children }) => {
    return (
        <div className="flex h-screen bg-[#0d0f15] text-slate-200 selection:bg-cyan-500/30">
            {/* Command Palette */}
            <CommandPalette />

            {/* Sidebar */}
            <div className="w-64 border-r border-white/5 flex flex-col bg-[#151821]">
                <div className="p-6">
                    <div className="text-2xl font-black bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 to-blue-500 tracking-tight">
                        axi<span className="text-white">.OSS</span>
                    </div>
                    <div className="text-xs text-slate-500 mt-1 font-mono">v0.1.0-alpha</div>
                </div>

                {/* Quick Search Button */}
                <div className="px-3 mb-2">
                    <button
                        onClick={() => {
                            const event = new KeyboardEvent('keydown', {
                                key: 'k',
                                metaKey: true,
                                bubbles: true
                            });
                            window.dispatchEvent(event);
                        }}
                        className="w-full flex items-center gap-2 px-3 py-2 text-sm text-slate-500 bg-black/20 border border-white/5 rounded-lg hover:border-cyan-500/30 hover:text-slate-400 transition-colors"
                    >
                        <Search className="w-4 h-4" />
                        <span className="flex-1 text-left">Quick search...</span>
                        <span className="flex items-center gap-1 text-xs bg-white/5 px-1.5 py-0.5 rounded">
                            <Command className="w-3 h-3" />K
                        </span>
                    </button>
                </div>

                <nav className="flex-1 px-3 space-y-1">
                    <div className="px-4 py-2 text-xs font-bold text-slate-600 uppercase tracking-widest mt-4 mb-2">Navigation</div>
                    <NavItem to="/glossary" icon={BookOpen} label="Glossary" />
                    <NavItem to="/" icon={LayoutDashboard} label="Dashboard" />
                    <NavItem to="/models" icon={Database} label="Models" />
                    <NavItem to="/metrics" icon={BarChart3} label="Metrics" />
                    <NavItem to="/dimensions" icon={Layers} label="Dimensions" />
                    <NavItem to="/graph" icon={GitFork} label="Graph" />

                    <div className="px-4 py-2 text-xs font-bold text-slate-600 uppercase tracking-widest mt-6 mb-2">Tools</div>
                    <NavItem to="/saved-queries" icon={Bookmark} label="Saved Queries" />
                    <NavItem to="/query" icon={Terminal} label="SQL Runner" />

                    <div className="pt-4 mt-2 border-t border-white/10">
                        <div className="px-3 mb-2 text-xs font-bold text-slate-500 uppercase tracking-wider">Resources</div>
                        <NavItem to="/docs" icon={BookOpen} label="Documentation" />
                    </div>
                </nav>

                <div className="p-4 bg-black/20">
                    <NavItem to="/settings" icon={Settings} label="Settings" />
                </div>
            </div>

            {/* Main Content */}
            <div className="flex-1 overflow-auto relative">
                <main className="min-h-full p-6">
                    {children || <Outlet />}
                </main>
            </div>
        </div>
    );
};
