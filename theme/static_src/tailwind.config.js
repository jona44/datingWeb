module.exports = {
    content: [
        '../templates/**/*.html',
        '../../templates/**/*.html',
        '../../**/templates/**/*.html',
    ],
    safelist: [
        'text-pink-600', 'hover:text-pink-600',
        'text-indigo-600', 'hover:text-indigo-600',
        'from-pink-600', 'to-purple-800',
        'from-indigo-600', 'to-teal-800',
        'bg-pink-600', 'hover:bg-pink-600',
        'bg-indigo-600', 'hover:bg-indigo-600'
    ],
    theme: {
        extend: {},
    },
    plugins: [
        require('@tailwindcss/typography'),
        require('@tailwindcss/forms'),
        require('@tailwindcss/aspect-ratio'),
        require('@tailwindcss/container-queries'),
    ],
}
