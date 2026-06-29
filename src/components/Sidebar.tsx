"use client";

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuth } from '@/context/AuthContext';
import {
    LayoutDashboard, ClipboardList, FileText, MessageSquare, HelpCircle, File,
    TestTube, MapPin, Archive, Box, Microscope, Activity, Banknote, ShieldCheck,
    Users, Database, AlertCircle, Settings, Ban, Layers, Mail, Code, Send, Thermometer,
    FlaskConical, Bell, GitBranch, BarChart2, Syringe, BookOpen, Calendar, UserCheck,
    Trash2, Globe, Repeat, TrendingUp, Building2
} from 'lucide-react';

export default function Sidebar() {
    const pathname = usePathname();
    const { user, logout } = useAuth();

    if (!user) return null;

    const isActive = (path: string) => pathname === path;

    // RBAC
    const role = user.role;
    const isLabStaff = ['admin', 'manager', 'scientist', 'medic'].includes(role);
    const isAdmin = role === 'admin';
    const isManager = ['admin', 'manager'].includes(role);

    const sections = [
        {
            title: 'Workspace',
            items: [
                { name: 'Dashboard', path: '/dashboard', icon: LayoutDashboard, show: true },
                { name: 'Messages', path: '/messages', icon: Mail, show: true },
                { name: 'Critical Values', path: '/critical-values', icon: Bell, show: isLabStaff },
                { name: 'Reports', path: '/reports', icon: FileText, show: true },
                { name: 'Cumulative Report', path: '/reports/cumulative', icon: TrendingUp, show: isLabStaff },
                { name: 'Email Delivery', path: '/reporting/email', icon: Send, show: isManager },
            ]
        },
        {
            title: 'Samples & Tracking',
            items: [
                { name: 'Accessioning', path: '/accessioning', icon: TestTube, show: isLabStaff || role === 'clerk' },
                { name: 'Specimen Receiving', path: '/receiving', icon: FlaskConical, show: isLabStaff || role === 'clerk' },
                { name: 'Phlebotomy', path: '/phlebotomy', icon: Syringe, show: isLabStaff || role === 'clerk' },
                { name: 'Tracking (CoC)', path: '/tracking', icon: MapPin, show: true },
                { name: 'Storage', path: '/storage', icon: Archive, show: isLabStaff },
                { name: 'Inventory', path: '/inventory', icon: Box, show: isLabStaff },
            ]
        },
        {
            title: 'Clinical Analysis',
            items: [
                { name: 'Results Entry', path: '/results', icon: Microscope, show: isLabStaff },
                { name: 'Workflow Queues', path: '/queues', icon: Layers, show: isLabStaff },
                { name: 'Worksheets', path: '/worksheets', icon: ClipboardList, show: isLabStaff },
                { name: 'QC & Calibration', path: '/qc', icon: Activity, show: isLabStaff },
                { name: 'Epidemiology', path: '/epidemiology', icon: Globe, show: isManager },
                { name: 'Histopathology', path: '/histology', icon: Microscope, show: isAdmin || user.department === 'Histopathology' },
                { name: 'Microbiology', path: '/microbiology', icon: Microscope, show: isAdmin || user.department === 'Microbiology' },
            ]
        },
        {
            title: 'Management',
            items: [
                { name: 'Billing', path: '/billing', icon: Banknote, show: isLabStaff },
                { name: 'Equipment', path: '/equipment', icon: Thermometer, show: true },
                { name: 'Documents', path: '/documents', icon: File, show: true },
                { name: 'Reference', path: '/help', icon: HelpCircle, show: true },
                { name: 'Feedback', path: '/feedback', icon: MessageSquare, show: true },
            ]
        }
    ];

    const adminItems = [
        { name: 'User Management', path: '/admin/users', icon: Users, show: isAdmin },
        { name: 'Patient Data', path: '/admin/patients', icon: Users, show: isManager },
        { name: 'Test Definitions', path: '/admin/tests', icon: TestTube, show: isManager },
        { name: 'Delta Check Rules', path: '/admin/delta-checks', icon: GitBranch, show: isManager },
        { name: 'Reflex Testing Rules', path: '/admin/reflex-rules', icon: Repeat, show: isManager },
        { name: 'Demographic Ref Ranges', path: '/admin/demographic-ranges', icon: Users, show: isManager },
        { name: 'TAT Thresholds', path: '/admin/tat-thresholds', icon: Calendar, show: isManager },
        { name: 'User Competency', path: '/admin/competency', icon: UserCheck, show: isManager },
        { name: 'Distribution Rules', path: '/admin/distribution-rules', icon: Send, show: isManager },
        { name: 'Requester Registry', path: '/admin/requesters', icon: Building2, show: isManager },
        { name: 'Sample Retention', path: '/admin/retention', icon: Trash2, show: isManager },
        { name: 'LOINC Catalogue', path: '/admin/loinc', icon: BookOpen, show: isManager },
        { name: 'KPI Dashboard', path: '/admin/kpi', icon: BarChart2, show: isManager },
        { name: 'Specimen Types', path: '/admin/specimen-types', icon: TestTube, show: isManager },
        { name: 'Rejection Criteria', path: '/admin/criteria', icon: Ban, show: isManager },
        { name: 'Auth Queues', path: '/admin/queues', icon: ShieldCheck, show: isManager },
        { name: 'Departments', path: '/admin/departments', icon: Layers, show: isAdmin },
        { name: 'Notifiable Conditions', path: '/admin/notifiable-conditions', icon: AlertCircle, show: isAdmin },
        { name: 'Audit Logs', path: '/admin/audit', icon: Database, show: isAdmin },
        { name: 'Alert Log', path: '/admin/alerts', icon: AlertCircle, show: isManager },
        { name: 'Backup & Maint.', path: '/admin/backup', icon: Database, show: isAdmin },
        { name: 'Configuration', path: '/admin/settings', icon: Settings, show: isManager },
        { name: 'Developer Docs', path: '/admin/developer-docs', icon: Code, show: isAdmin },
    ];

    return (
        <div className="w-64 bg-[#0f172a] border-r border-[#1e293b] text-slate-300 flex flex-col h-screen font-sans">
            {/* Header */}
            <div className="p-6 border-b border-slate-800">
                <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
                    <Activity className="text-primary-500 w-6 h-6" />
                    <span>Dx</span>
                </h1>
                <p className="text-xs text-primary-400 mt-1 uppercase tracking-widest font-semibold ml-8">
                    {user.role} Module
                </p>
            </div>

            {/* Navigation */}
            <nav className="flex-1 overflow-y-auto px-4 py-4 space-y-8 custom-scrollbar">
                {sections.map((section, idx) => {
                    const visibleItems = section.items.filter(i => i.show);
                    if (visibleItems.length === 0) return null;
                    return (
                        <div key={idx}>
                            <h3 className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-3 px-3">
                                {section.title}
                            </h3>
                            <div className="space-y-1">
                                {visibleItems.map(item => (
                                    <Link
                                        key={item.path}
                                        href={item.path}
                                        className={`
                                            flex items-center gap-3 px-3 py-2 text-sm font-medium rounded-md transition-all
                                            ${isActive(item.path)
                                                ? 'bg-slate-800 text-primary-400'
                                                : 'text-slate-400 hover:text-white hover:bg-slate-800'}
                                        `}
                                    >
                                        <item.icon className={`w-4 h-4 ${isActive(item.path) ? 'text-primary-400' : 'text-slate-500 group-hover:text-white'}`} />
                                        {item.name}
                                    </Link>
                                ))}
                            </div>
                        </div>
                    );
                })}

                {/* Admin Section */}
                {isManager && (
                    <div>
                        <h3 className="text-[10px] font-bold text-red-500/80 uppercase tracking-widest mb-3 px-3 mt-8 pt-4 border-t border-slate-800">
                            Administration
                        </h3>
                        <div className="space-y-1">
                            {adminItems.filter(i => i.show).map(item => (
                                <Link
                                    key={item.path}
                                    href={item.path}
                                    className={`
                                        flex items-center gap-3 px-3 py-2 text-sm font-medium rounded-md transition-all
                                        ${isActive(item.path)
                                            ? 'bg-red-500/10 text-red-400'
                                            : 'text-slate-400 hover:text-white hover:bg-slate-800'}
                                    `}
                                >
                                    <item.icon className="w-4 h-4" />
                                    {item.name}
                                </Link>
                            ))}
                        </div>
                    </div>
                )}
            </nav>

            {/* User Footer */}
            <div className="p-4 bg-slate-950 border-t border-slate-800">
                <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-slate-800 flex items-center justify-center text-xs font-bold text-slate-400">
                        {user.username.substring(0, 2).toUpperCase()}
                    </div>
                    <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-white truncate">{user.name || user.username}</div>
                        <button onClick={logout} className="text-xs text-slate-500 hover:text-white transition-colors">Sign Out</button>
                    </div>
                </div>
            </div>
        </div>
    );
}
