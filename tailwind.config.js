/** @type {import('tailwindcss').Config} */
module.exports = {
    content: [
        "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
        "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
        "./src/lib/**/*.{js,ts,jsx,tsx,mdx}",
    ],
    safelist: [
        'theme-blue',
        'theme-emerald',
        'theme-rose',
        'theme-indigo',
        'theme-contrast',
        'mode-dark',
    ],
    theme: {
        extend: {
            colors: {
                primary: {
                    50: 'var(--primary-50)',
                    100: 'var(--primary-100)',
                    200: '#bfdbfe', // Static (Unused in themes)
                    300: '#93c5fd',
                    400: '#60a5fa',
                    500: 'var(--primary-500)',
                    600: 'var(--primary-600)', // Modern Blue Main
                    700: 'var(--primary-700)',
                    800: '#1e40af',
                    900: '#1e3a8a',
                },
                success: {
                    50: 'var(--success-50)',
                    100: '#dcfce7',
                    500: 'var(--success-500)',
                    600: 'var(--success-600)',
                    700: '#15803d',
                },
                warning: {
                    50: 'var(--warning-50)',
                    100: '#fef3c7',
                    500: 'var(--warning-500)',
                    600: 'var(--warning-600)',
                    700: '#b45309',
                },
                danger: {
                    50: 'var(--danger-50)',
                    100: '#ffe4e6',
                    500: 'var(--danger-500)',
                    600: 'var(--danger-600)',
                    700: '#b91c1c',
                },
                slate: {
                    50: 'var(--slate-50)',
                    100: 'var(--slate-100)',
                    200: 'var(--slate-200)',
                    300: '#cbd5e1',
                    400: '#94a3b8',
                    500: '#64748b',
                    600: 'var(--slate-600)',
                    700: '#334155',
                    800: 'var(--slate-800)',
                    900: 'var(--slate-900)',
                    950: '#020617',
                }
            },
            fontFamily: {
                sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'sans-serif'],
            },
            boxShadow: {
                'card': '0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)',
                'card-hover': '0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)',
                'elevated': '0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)',
            },
            borderRadius: {
                'lg': '0.75rem',
                'xl': '1rem',
            },
            transitionDuration: {
                '150': '150ms',
                '200': '200ms',
            },
        },
    },
    plugins: [],
}
