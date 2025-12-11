/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            colors: {
                background: '#0d0f15',
                panel: '#151821',
                text: {
                    primary: '#e0e3e7',
                    secondary: '#94a3b8',
                },
                accent: {
                    cyan: '#00e5ff',
                    aqua: '#39ffbc',
                    violet: '#a855f7',
                },
                border: '#1e293b',
            },
            fontFamily: {
                sans: ['Inter', 'sans-serif'],
                mono: ['JetBrains Mono', 'monospace'],
            },
        },
    },
    plugins: [],
}
