import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { LayoutDashboard, Network, Database, Activity } from 'lucide-react';

export const Layout = ({ children }: { children: React.ReactNode }) => {
    const location = useLocation();

    const navItems = [
        { name: 'Explorer', path: '/', icon: <LayoutDashboard size={18} /> },
        { name: 'Graph', path: '/graph', icon: <Network size={18} /> },
        { name: 'Models', path: '/models', icon: <Database size={18} /> },
    ];

    return (
        <div style={{ display: 'flex', minHeight: '100vh' }}>
            {/* Sidebar */}
            <aside style={{ width: '250px', borderRight: '1px solid var(--border-color)', padding: '1.5rem', display: 'flex', flexDirection: 'column' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '2rem', color: 'var(--accent-primary)', fontWeight: 'bold', fontSize: '1.25rem' }}>
                    <Activity />
                    <span>AXI</span>
                </div>

                <nav style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    {navItems.map(item => {
                        const isActive = location.pathname === item.path;
                        return (
                            <Link
                                key={item.path}
                                to={item.path}
                                style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '0.75rem',
                                    padding: '0.75rem',
                                    borderRadius: '0.375rem',
                                    color: isActive ? 'white' : 'var(--text-secondary)',
                                    backgroundColor: isActive ? 'var(--bg-tertiary)' : 'transparent',
                                    fontWeight: isActive ? 500 : 400
                                }}
                            >
                                {item.icon}
                                {item.name}
                            </Link>
                        )
                    })}
                </nav>
            </aside>

            {/* Main Content */}
            <main style={{ flex: 1, padding: '2rem', overflowY: 'auto' }}>
                <div className="container">
                    {children}
                </div>
            </main>
        </div>
    );
};
