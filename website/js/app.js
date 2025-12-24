import { createApp, ref, computed, onMounted, onUnmounted } from 'https://unpkg.com/vue@3/dist/vue.esm-browser.js';
import { analysisData } from './data.js';

const app = createApp({
    setup() {
        const data = ref(analysisData);
        const isPresentationMode = ref(false);
        const currentSlideIndex = ref(0);
        const showModal = ref(false);
        const modalImage = ref(null);

        // 构建演示幻灯片序列
        const slides = computed(() => {
            const list = [];
            
            // 1. 标题页
            list.push({ type: 'intro', content: data.value.intro });
            
            // 2. 分析逻辑架构
            if (data.value.logic) {
                list.push({ type: 'logic', content: data.value.logic });
            }
            
            // 3. 数据清洗与标准化
            if (data.value.dataTransform) {
                list.push({ type: 'transform', content: data.value.dataTransform });
            }
            
            // 4. 回归模型核心发现
            if (data.value.regression) {
                list.push({ type: 'regression', content: data.value.regression });
            }
            
            // 5. 方法论
            list.push({ type: 'methodology', content: data.value.methodology });

            // 6. 故事章节
            data.value.story.forEach(chapter => {
                // 章节介绍页
                list.push({ type: 'chapter', content: chapter });
                
                // 该章节的图片页
                chapter.images.forEach(img => {
                    list.push({ type: 'image', content: img, chapterTitle: chapter.title });
                });
                
                // 该章节的交互式图表页
                if (chapter.interactiveCharts && chapter.interactiveCharts.length > 0) {
                    chapter.interactiveCharts.forEach(chart => {
                        list.push({ type: 'interactive', content: chart, chapterTitle: chapter.title });
                    });
                }
                
                // 章节洞察页
                list.push({ type: 'insight', content: chapter.insight, chapterTitle: chapter.title });
            });

            // 7. 结论页
            if (data.value.conclusion) {
                list.push({ type: 'conclusion', content: data.value.conclusion });
            }

            return list;
        });

        const currentSlide = computed(() => {
            return slides.value[currentSlideIndex.value];
        });

        // 收集所有图片用于背景
        const allImages = computed(() => {
            let imgs = [];
            if (data.value.story) {
                data.value.story.forEach(chapter => {
                    imgs = [...imgs, ...chapter.images];
                });
            }
            return imgs;
        });

        const togglePresentation = () => {
            isPresentationMode.value = !isPresentationMode.value;
            if (isPresentationMode.value) {
                document.body.classList.add('in-presentation');
                currentSlideIndex.value = 0;
            } else {
                document.body.classList.remove('in-presentation');
            }
        };

        const nextSlide = () => {
            if (currentSlideIndex.value < slides.value.length - 1) {
                currentSlideIndex.value++;
            }
        };

        const prevSlide = () => {
            if (currentSlideIndex.value > 0) {
                currentSlideIndex.value--;
            }
        };

        const handleKeydown = (e) => {
            // 在模态框打开时不处理键盘事件
            if (showModal.value) {
                if (e.key === 'Escape') {
                    closeModal();
                }
                return;
            }
            
            if (!isPresentationMode.value) return;
            
            if (e.key === 'ArrowRight' || e.key === '+' || e.key === '=' || e.key === ' ') {
                e.preventDefault();
                nextSlide();
            } else if (e.key === 'ArrowLeft' || e.key === '-') {
                e.preventDefault();
                prevSlide();
            } else if (e.key === 'Escape') {
                togglePresentation();
            }
        };

        const openModal = (img) => {
            if (isPresentationMode.value) return;
            modalImage.value = img;
            showModal.value = true;
            document.body.style.overflow = 'hidden';
        };

        const closeModal = () => {
            showModal.value = false;
            modalImage.value = null;
            document.body.style.overflow = '';
        };

        // 平滑滚动到指定区域
        const scrollTo = (id) => {
            const el = document.getElementById(id);
            if (el) {
                el.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        };

        // 根据数据来源返回对应的 CSS 类
        const getSourceClass = (source) => {
            if (!source) return '';
            if (source.includes('BOSS') || source.includes('boss')) return 'source-boss';
            if (source.includes('前程无忧') || source.includes('51job')) return 'source-51job';
            if (source.includes('智联') || source.includes('Zhaopin')) return 'source-zhaopin';
            return '';
        };

        onMounted(() => {
            window.addEventListener('keydown', handleKeydown);
        });

        onUnmounted(() => {
            window.removeEventListener('keydown', handleKeydown);
        });

        return {
            data,
            isPresentationMode,
            currentSlideIndex,
            slides,
            currentSlide,
            allImages,
            togglePresentation,
            nextSlide,
            prevSlide,
            showModal,
            modalImage,
            openModal,
            closeModal,
            scrollTo,
            getSourceClass
        };
    }
});

app.mount('#app');
