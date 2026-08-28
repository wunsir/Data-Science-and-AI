import { createApp, ref, computed, nextTick, onMounted, onUnmounted } from "./vendor/vue.esm-browser.prod.js";
import { sharedNavigation, fallbackMetrics, homeData, pageData } from "./story-data.js";

const currentPage = document.body.dataset.page || "home";

function setupParticleCanvas() {
    const canvas = document.getElementById("particle-canvas");
    const hero = document.querySelector(".hero-bg");
    if (!canvas || !hero) return () => {};

    const context = canvas.getContext("2d", { alpha: true });
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let width = 0;
    let height = 0;
    let particles = [];
    let animationFrame = 0;
    let resizeFrame = 0;
    let pageVisible = !document.hidden;
    let heroVisible = true;
    const mouse = { x: null, y: null };

    class Particle {
        constructor() {
            this.reset();
        }

        reset() {
            this.x = Math.random() * Math.max(width, 1);
            this.y = Math.random() * Math.max(height, 1);
            this.baseVx = (Math.random() - 0.5) * 0.5;
            this.baseVy = (Math.random() - 0.5) * 0.5;
            this.vx = this.baseVx;
            this.vy = this.baseVy;
            this.size = Math.random() * 2.4 + 1.6;
            this.alpha = Math.random() * 0.45 + 0.3;
        }

        update() {
            this.x += this.vx;
            this.y += this.vy;
            if (this.x < 0 || this.x > width) {
                this.vx *= -1;
                this.baseVx *= -1;
            }
            if (this.y < 0 || this.y > height) {
                this.vy *= -1;
                this.baseVy *= -1;
            }
            if (mouse.x !== null && mouse.y !== null) {
                const dx = mouse.x - this.x;
                const dy = mouse.y - this.y;
                const distance = Math.hypot(dx, dy);
                if (distance > 0 && distance < 250) {
                    const force = (250 - distance) / 250 * 0.05;
                    this.vx -= dx / distance * force;
                    this.vy -= dy / distance * force;
                }
            }
            this.vx += (this.baseVx - this.vx) * 0.05;
            this.vy += (this.baseVy - this.vy) * 0.05;
        }

        draw() {
            context.beginPath();
            context.arc(this.x, this.y, this.size, 0, Math.PI * 2);
            context.fillStyle = `rgba(203, 213, 225, ${this.alpha})`;
            context.fill();
        }
    }

    const rebuild = () => {
        width = window.innerWidth;
        height = window.innerHeight;
        const pixelRatio = Math.min(window.devicePixelRatio || 1, 1.5);
        canvas.width = Math.round(width * pixelRatio);
        canvas.height = Math.round(height * pixelRatio);
        canvas.style.width = `${width}px`;
        canvas.style.height = `${height}px`;
        context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
        const count = Math.min(80, Math.max(48, Math.round(width * height / 21000)));
        particles = Array.from({ length: count }, () => new Particle());
        drawFrame(false);
    };

    const drawFrame = (advance = true) => {
        context.clearRect(0, 0, width, height);
        for (let index = 0; index < particles.length; index += 1) {
            if (advance) particles[index].update();
            particles[index].draw();
            for (let other = index + 1; other < particles.length; other += 1) {
                const dx = particles[index].x - particles[other].x;
                const dy = particles[index].y - particles[other].y;
                const distance = Math.hypot(dx, dy);
                if (distance < 180) {
                    context.beginPath();
                    context.strokeStyle = `rgba(203, 213, 225, ${(1 - distance / 180) * 0.72})`;
                    context.lineWidth = 1.2;
                    context.moveTo(particles[index].x, particles[index].y);
                    context.lineTo(particles[other].x, particles[other].y);
                    context.stroke();
                }
            }
        }
    };

    const animate = () => {
        animationFrame = 0;
        if (!pageVisible || !heroVisible || reducedMotion) return;
        drawFrame(true);
        animationFrame = requestAnimationFrame(animate);
    };

    const syncAnimation = () => {
        if (pageVisible && heroVisible && !reducedMotion && !animationFrame) {
            animationFrame = requestAnimationFrame(animate);
        } else if ((!pageVisible || !heroVisible || reducedMotion) && animationFrame) {
            cancelAnimationFrame(animationFrame);
            animationFrame = 0;
        }
    };

    const onResize = () => {
        cancelAnimationFrame(resizeFrame);
        resizeFrame = requestAnimationFrame(rebuild);
    };
    const onPointerMove = (event) => {
        mouse.x = event.clientX;
        mouse.y = event.clientY;
    };
    const clearPointer = () => {
        mouse.x = null;
        mouse.y = null;
    };
    const onVisibility = () => {
        pageVisible = !document.hidden;
        syncAnimation();
    };

    const observer = new IntersectionObserver(([entry]) => {
        heroVisible = entry.isIntersecting;
        syncAnimation();
    }, { threshold: 0.01 });

    window.addEventListener("resize", onResize, { passive: true });
    window.addEventListener("pointermove", onPointerMove, { passive: true });
    document.addEventListener("pointerleave", clearPointer);
    document.addEventListener("visibilitychange", onVisibility);
    observer.observe(hero);
    rebuild();
    syncAnimation();

    return () => {
        if (animationFrame) cancelAnimationFrame(animationFrame);
        if (resizeFrame) cancelAnimationFrame(resizeFrame);
        observer.disconnect();
        window.removeEventListener("resize", onResize);
        window.removeEventListener("pointermove", onPointerMove);
        document.removeEventListener("pointerleave", clearPointer);
        document.removeEventListener("visibilitychange", onVisibility);
    };
}

createApp({
    setup() {
        const data = ref(currentPage === "home" ? homeData : pageData[currentPage]);
        const metrics = ref({ ...fallbackMetrics });
        const navigation = ref(sharedNavigation);
        const menuOpen = ref(false);
        const lightboxOpen = ref(false);
        const activeFigure = ref(null);
        let revealObserver = null;
        let cleanupParticles = () => {};
        let lastTrigger = null;

        const pageStats = computed(() => [
            { label: "原始记录", value: metrics.value.rawRows },
            { label: "去重职位", value: metrics.value.uniqueJobs },
            { label: "薪资样本", value: metrics.value.salaryJobs },
            { label: "数据来源", value: `${metrics.value.sources} 个平台` }
        ]);

        const heroTags = computed(() => homeData.tags.map((tag) => ({
            label: `${metrics.value[tag.key]}${tag.suffix}`
        })));

        const isActive = (page) => page === currentPage;

        const loadSummary = async () => {
            try {
                const response = await fetch("./data/analysis_summary.json", { cache: "no-store" });
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                const summary = await response.json();
                const coverage = summary.coverage || {};
                metrics.value = {
                    rawRows: Number(coverage.raw_rows || 0).toLocaleString("zh-CN"),
                    uniqueJobs: Number(coverage.unique_jobs || 0).toLocaleString("zh-CN"),
                    salaryJobs: Number(coverage.salary_analyzable_jobs || 0).toLocaleString("zh-CN"),
                    sources: String((coverage.sources || []).length || 3)
                };
            } catch {
                metrics.value = { ...fallbackMetrics };
            }
        };

        const scrollToContent = () => {
            document.getElementById("overview")?.scrollIntoView({
                behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth"
            });
        };

        const openLightbox = (figure, event) => {
            if (figure.kind !== "image") return;
            activeFigure.value = figure;
            lightboxOpen.value = true;
            lastTrigger = event?.currentTarget || null;
            document.body.classList.add("lightbox-open");
            nextTick(() => document.querySelector(".lightbox-close")?.focus());
        };

        const closeLightbox = () => {
            lightboxOpen.value = false;
            activeFigure.value = null;
            document.body.classList.remove("lightbox-open");
            nextTick(() => lastTrigger?.focus());
        };

        const handleKeydown = (event) => {
            if (event.key === "Escape" && lightboxOpen.value) closeLightbox();
        };

        onMounted(() => {
            loadSummary();
            window.addEventListener("keydown", handleKeydown);
            cleanupParticles = setupParticleCanvas();

            const items = document.querySelectorAll(".reveal");
            if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
                items.forEach((item) => item.classList.add("is-visible"));
            } else {
                revealObserver = new IntersectionObserver((entries) => {
                    entries.forEach((entry) => {
                        if (entry.isIntersecting) {
                            entry.target.classList.add("is-visible");
                            revealObserver.unobserve(entry.target);
                        }
                    });
                }, { threshold: 0.08 });
                items.forEach((item) => revealObserver.observe(item));
            }
        });

        onUnmounted(() => {
            cleanupParticles();
            revealObserver?.disconnect();
            window.removeEventListener("keydown", handleKeydown);
            document.body.classList.remove("lightbox-open");
        });

        return {
            data,
            metrics,
            navigation,
            menuOpen,
            lightboxOpen,
            activeFigure,
            pageStats,
            heroTags,
            isActive,
            scrollToContent,
            openLightbox,
            closeLightbox
        };
    }
}).mount("#app");

