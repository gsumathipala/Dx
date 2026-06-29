import React from 'react';

type BadgeVariant = 'default' | 'primary' | 'success' | 'warning' | 'error' | 'outline';

interface BadgeProps {
    children: React.ReactNode;
    variant?: BadgeVariant;
    className?: string;
    icon?: string;
}

const variants = {
    default: 'bg-slate-100 text-slate-700 ring-1 ring-inset ring-slate-600/20',
    primary: 'bg-primary-50 text-primary-700 ring-1 ring-inset ring-primary-200',
    success: 'bg-success-50 text-success-700 ring-1 ring-inset ring-success-600/20',
    warning: 'bg-warning-50 text-warning-700 ring-1 ring-inset ring-warning-600/20',
    error: 'bg-danger-50 text-danger-700 ring-1 ring-inset ring-danger-600/20',
    outline: 'border border-slate-300 text-slate-700 bg-white',
};

export function Badge({ children, variant = 'default', className = '', icon }: BadgeProps) {
    return (
        <span className={`inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-medium transition-all duration-150 ${variants[variant]} ${className}`}>
            {icon && <span className="text-sm">{icon}</span>}
            {children}
        </span>
    );
}

export function StatusBadge({ status }: { status: string }) {
    let variant: BadgeVariant = 'default';
    let icon = '';
    const s = status.toLowerCase();

    if (s === 'completed' || s === 'ok' || s === 'final') {
        variant = 'success';
        icon = '✓';
    }
    else if (s === 'pending' || s === 'in progress' || s === 'preliminary') {
        variant = 'primary';
        icon = '⏳';
    }
    else if (s === 'overdue' || s === 'expired' || s === 'error') {
        variant = 'error';
        icon = '⚠';
    }
    else if (s.includes('low') || s.includes('due')) {
        variant = 'warning';
        icon = '△';
    }

    return <Badge variant={variant} icon={icon}>{status}</Badge>;
}
