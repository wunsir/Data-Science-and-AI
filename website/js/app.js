import { createApp, ref, nextTick, onMounted, onUnmounted } from './vendor/vue.esm-browser.prod.js';
import { analysisData } from './data.js';

createApp({
    setup() {
        const data = ref(analysisData);
        const menuOpen = ref(false);
        const lightboxOpen = ref(false);
        const activeFigure = ref(null);
        let revealObserver = null;
        let lastTrigger = null;

        const scrollTo = (id) => {
            const target = document.getElementById(id);
            if (!target) return;

            menuOpen.value = false;
            const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
            target.scrollIntoView({
                behavior: reducedMotion ? 'auto' : 'smooth',
                block: 'start'
            });
        };

        const openLightbox = (figure, event) => {
            activeFigure.value = figure;
            lightboxOpen.value = true;
            lastTrigger = event?.currentTarget || null;
            document.body.classList.add('lightbox-open');
            nextTick(() => document.querySelector('.lightbox-close')?.focus());
        };

        const closeLightbox = () => {
            lightboxOpen.value = false;
            activeFigure.value = null;
            document.body.classList.remove('lightbox-open');
            nextTick(() => lastTrigger?.focus());
        };

        const handleKeydown = (event) => {
            if (event.key === 'Escape' && lightboxOpen.value) {
                closeLightbox();
            }
        };

        onMounted(() => {
            window.addEventListener('keydown', handleKeydown);
            const revealItems = document.querySelectorAll('.reveal');

            if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
                revealItems.forEach((item) => item.classList.add('is-visible'));
                return;
            }

            revealObserver = new IntersectionObserver((entries) => {
                entries.forEach((entry) => {
                    if (entry.isIntersecting) {
                        entry.target.classList.add('is-visible');
                        revealObserver.unobserve(entry.target);
                    }
                });
            }, { threshold: 0.08 });

            revealItems.forEach((item) => revealObserver.observe(item));
        });

        onUnmounted(() => {
            window.removeEventListener('keydown', handleKeydown);
            revealObserver?.disconnect();
            document.body.classList.remove('lightbox-open');
        });

        return {
            data,
            menuOpen,
            lightboxOpen,
            activeFigure,
            scrollTo,
            openLightbox,
            closeLightbox
        };
    }
}).mount('#app');
