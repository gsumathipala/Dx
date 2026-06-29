import React from 'react';
import { cn } from './button';

const Card = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
    ({ className, ...props }, ref) => (
        <div
            ref={ref}
            className={cn("rounded-xl border border-slate-200 bg-white text-slate-950 shadow-sm", className)}
            {...props}
        />
    )
)
Card.displayName = "Card"

const CardHeader = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
    ({ className, ...props }, ref) => (
        <div
            ref={ref}
            className={cn("flex flex-col space-y-1.5 p-6", className)}
            {...props}
        />
    )
)
CardHeader.displayName = "CardHeader"

const CardTitle = React.forwardRef<HTMLParagraphElement, React.HTMLAttributes<HTMLHeadingElement>>(
    ({ className, ...props }, ref) => (
        <h3
            ref={ref}
            className={cn("font-semibold leading-none tracking-tight", className)}
            {...props}
        />
    )
)
CardTitle.displayName = "CardTitle"

const CardDescription = React.forwardRef<HTMLParagraphElement, React.HTMLAttributes<HTMLParagraphElement>>(
    ({ className, ...props }, ref) => (
        <p
            ref={ref}
            className={cn("text-sm text-slate-500 dark:text-slate-400", className)}
            {...props}
        />
    )
)
CardDescription.displayName = "CardDescription"

const CardContent = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
    ({ className, ...props }, ref) => (
        <div ref={ref} className={cn("p-6 pt-0", className)} {...props} />
    )
)
CardContent.displayName = "CardContent"

const CardFooter = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
    ({ className, ...props }, ref) => (
        <div
            ref={ref}
            className={cn("flex items-center p-6 pt-0", className)}
            {...props}
        />
    )
)
CardFooter.displayName = "CardFooter"

// LEGACY ADAPTER for existing pages
interface LegacyCardProps {
    children: React.ReactNode;
    className?: string;
    title?: string;
    description?: string;
    footer?: React.ReactNode;
    style?: React.CSSProperties;
}

export function LegacyCard({ children, className = '', title, description, footer, style }: LegacyCardProps) {
    return (
        <Card className={className} style={style}>
            {(title || description) && (
                <CardHeader className="border-b border-slate-100 bg-gradient-to-r from-slate-50 to-white">
                    {title && <h3 className="text-lg font-semibold text-slate-900">{title}</h3>}
                    {description && <p className="text-sm text-slate-600 mt-1">{description}</p>}
                </CardHeader>
            )}
            <CardContent className="p-6">
                {children}
            </CardContent>
            {footer && (
                <div className="bg-slate-50 px-6 py-3 border-t border-slate-100 flex items-center">
                    {footer}
                </div>
            )}
        </Card>
    );
}

// Export named components for new UI
export { Card as CardRoot, CardHeader, CardFooter, CardTitle, CardDescription, CardContent }

// Export LegacyCard as 'Card' for backward compatibility with existing pages
export { LegacyCard as Card }

// Default export handles the Legacy case transparently?
// No, existing code does `import { Card } from ...` and checks named export? NO, likely `import { Card }` or `import Card`.
// Previous file had `export function Card`. So named export `Card`.
// So I MUST export the LegacyCard AS `Card` to not break existing pages!
// BUT new pages want `Card` as the root element.
// Conflict: Old pages use `<Card title="...">` (Legacy). New pages use `<Card><CardHeader>...` (Composable).
// Solution: Make `Card` smart? Or rename old usages.
// "Refactoring all usages is risky".
// Let's make `Card` the Composable one, and export `LegacyCard`.
// AND for the sake of not breaking everything immediately, I will check if any pages import `Card` as default.
// The file viewed had `export function Card`. So it was a NAMED export.
// So `import { Card }` is used.
// Failure mode: All existing pages will break if I invoke `Card` without title/desc props? No, they pass extra props.
// If I change `Card` to the simple div wrapper, existing pages passing `title=".."` will just render a div with a title attribute (valid HTML but invisible).
// BAD.
// I will export `SimpleCard` as `Card` and `LegacyCard` as `LegacyCard`.
// Wait, I want `backup/page.tsx` to use the nice composable ones.
// I'll update `backup/page.tsx` to import `SimpleCard` alias or similar.
// BETTER: I will rename the new components in this file to `UiCard`, `UiCardHeader` etc. and export them.
// And keep `Card` as the Legacy one.
// Then update `backup/page.tsx` to use `UiCard`.
