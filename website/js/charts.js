const chartElement = document.getElementById("chart");
const statusElement = document.getElementById("chart-status");
const chartId = new URLSearchParams(window.location.search).get("id");
const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const palette = ["#1e40af", "#0f766e", "#7c3aed", "#b45309", "#be123c", "#475569"];
let instance = null;
let resizeObserver = null;

const stableColor = (name) => {
    let hash = 0;
    for (const character of String(name || "")) {
        hash = ((hash * 31) + character.codePointAt(0)) >>> 0;
    }
    return palette[hash % palette.length];
};

const money = (value) => `¥${Number(value).toLocaleString("zh-CN", { maximumFractionDigits: 0 })}/月`;
const showStatus = (message) => {
    statusElement.textContent = message;
    statusElement.hidden = false;
};
const hideStatus = () => {
    statusElement.hidden = true;
};

const loadScript = (src) => new Promise((resolve, reject) => {
    if (document.querySelector(`script[data-plugin="${src}"]`)) {
        resolve();
        return;
    }
    const script = document.createElement("script");
    script.src = src;
    script.dataset.plugin = src;
    script.onload = resolve;
    script.onerror = () => reject(new Error(`无法加载 ${src}`));
    document.head.appendChild(script);
});

const commonTitle = (chart) => ({
    text: chart.title,
    subtext: chart.subtitle,
    left: "center",
    top: 18,
    textStyle: { color: "#0f172a", fontSize: 20, fontWeight: 700, fontFamily: "Microsoft YaHei" },
    subtextStyle: { color: "#64748b", fontSize: 12, lineHeight: 18 }
});

function bar3dOption(chart) {
    const values = chart.data.values || [];
    const salaries = values.map((item) => Number(item[2]));
    return {
        title: commonTitle(chart),
        tooltip: {
            formatter: (params) => {
                const value = params.value;
                return `${chart.data.cities[value[0]]}<br>${chart.data.categories[value[1]]}<br>${money(value[2])}<br>n=${Number(value[3]).toLocaleString("zh-CN")}`;
            }
        },
        visualMap: {
            min: salaries.length ? Math.min(...salaries) : 0,
            max: salaries.length ? Math.max(...salaries) : 1,
            dimension: 2,
            orient: "horizontal",
            left: "center",
            bottom: 18,
            inRange: { color: ["#dbeafe", "#60a5fa", "#1e40af"] },
            text: ["较高", "较低"],
            textStyle: { color: "#64748b" }
        },
        xAxis3D: { type: "category", data: chart.data.cities, axisLabel: { interval: 0 } },
        yAxis3D: { type: "category", data: chart.data.categories, axisLabel: { interval: 0 } },
        zAxis3D: { type: "value", name: "元/月" },
        grid3D: {
            top: 92,
            bottom: 55,
            boxWidth: 140,
            boxDepth: 82,
            light: { main: { intensity: 1.1 }, ambient: { intensity: 0.45 } },
            viewControl: { autoRotate: false, distance: 190, alpha: 24, beta: 36 }
        },
        series: [{ type: "bar3D", data: values, shading: "lambert", itemStyle: { opacity: 0.92 } }]
    };
}

function treemapOption(chart) {
    return {
        title: commonTitle(chart),
        color: palette,
        tooltip: { formatter: (params) => `${params.name}<br>职位数：${Number(params.value).toLocaleString("zh-CN")}` },
        series: [{
            type: "treemap",
            top: 92,
            left: 20,
            right: 20,
            bottom: 20,
            roam: false,
            nodeClick: "zoomToNode",
            breadcrumb: { show: true, bottom: 5 },
            label: { show: true, formatter: "{b}" },
            upperLabel: { show: true, height: 26, color: "#fff" },
            itemStyle: { borderColor: "#fff", borderWidth: 2, gapWidth: 2 },
            data: chart.data.tree || []
        }]
    };
}

function sankeyOption(chart) {
    return {
        title: commonTitle(chart),
        color: palette,
        tooltip: {
            trigger: "item",
            formatter: (params) => params.dataType === "edge"
                ? `${params.data.source.split(":").slice(1).join(":")} → ${params.data.target.split(":").slice(1).join(":")}<br>职位数：${Number(params.data.value).toLocaleString("zh-CN")}`
                : params.data.label
        },
        series: [{
            type: "sankey",
            top: 100,
            left: 40,
            right: 120,
            bottom: 35,
            nodeWidth: 16,
            nodeGap: 12,
            emphasis: { focus: "adjacency" },
            lineStyle: { color: "gradient", curveness: 0.48, opacity: 0.34 },
            label: { color: "#334155", formatter: (params) => params.data.label },
            data: chart.data.nodes || [],
            links: chart.data.links || []
        }]
    };
}

function wordcloudOption(chart) {
    return {
        title: commonTitle(chart),
        tooltip: { formatter: (params) => `${params.name}<br>职位数：${Number(params.value).toLocaleString("zh-CN")}` },
        series: [{
            type: "wordCloud",
            shape: "diamond",
            left: "center",
            top: 92,
            width: "92%",
            height: "72%",
            sizeRange: [18, 72],
            rotationRange: [-28, 28],
            rotationStep: 14,
            gridSize: 10,
            drawOutOfBound: false,
            textStyle: { color: (params) => stableColor(params.name) },
            emphasis: { textStyle: { textShadowBlur: 8, textShadowColor: "rgba(15,23,42,.25)" } },
            data: chart.data.words || []
        }]
    };
}

function scatterOption(chart) {
    return {
        title: commonTitle(chart),
        color: ["#1e40af"],
        grid: { top: 105, left: 80, right: 35, bottom: 68 },
        tooltip: {
            formatter: (params) => `技能数：${params.value[0]}<br>${money(params.value[1])}<br>${params.value[2]} · ${params.value[3]}`
        },
        xAxis: { type: "value", name: "识别技能数", minInterval: 1, nameLocation: "middle", nameGap: 35 },
        yAxis: {
            type: "log",
            name: "月薪中点（元）",
            axisLabel: { formatter: (value) => `${Math.round(value / 1000)}k` },
            splitLine: { lineStyle: { color: "#e2e8f0" } }
        },
        dataZoom: [{ type: "inside" }, { type: "slider", height: 20, bottom: 15 }],
        series: [{
            type: "scatter",
            symbolSize: 7,
            data: chart.data.points || [],
            itemStyle: { opacity: 0.38 },
            emphasis: { itemStyle: { opacity: 1, borderColor: "#fff", borderWidth: 1 } }
        }]
    };
}

function radarOption(chart) {
    return {
        title: commonTitle(chart),
        color: ["#94a3b8", "#1e40af"],
        legend: { top: 86, data: (chart.data.groups || []).map((group) => group.name) },
        tooltip: {},
        radar: {
            center: ["50%", "59%"],
            radius: "60%",
            splitNumber: 5,
            indicator: chart.data.indicators || [],
            axisName: { color: "#334155" },
            splitLine: { lineStyle: { color: "#e2e8f0" } },
            splitArea: { areaStyle: { color: ["#fff", "#f8fafc"] } }
        },
        series: [{
            type: "radar",
            areaStyle: { opacity: 0.12 },
            data: (chart.data.groups || []).map((group) => ({
                name: group.name,
                value: group.values,
                symbolSize: 6
            }))
        }]
    };
}

function bubbleOption(chart) {
    const values = (chart.data.points || []).map((item) => Number(item[2]));
    return {
        title: commonTitle(chart),
        grid: { top: 105, left: 68, right: 45, bottom: 55 },
        tooltip: {
            formatter: (params) => `${params.value[4]}<br>${money(params.value[2])}<br>职位数：${Number(params.value[3]).toLocaleString("zh-CN")}`
        },
        visualMap: {
            min: values.length ? Math.min(...values) : 0,
            max: values.length ? Math.max(...values) : 1,
            dimension: 2,
            orient: "horizontal",
            left: "center",
            bottom: 8,
            inRange: { color: ["#bfdbfe", "#3b82f6", "#1e3a8a"] },
            text: ["薪资较高", "薪资较低"]
        },
        xAxis: {
            type: "value",
            name: "经度",
            min: 102,
            max: 123,
            splitLine: { lineStyle: { color: "#e2e8f0" } }
        },
        yAxis: {
            type: "value",
            name: "纬度",
            min: 20,
            max: 41,
            splitLine: { lineStyle: { color: "#e2e8f0" } }
        },
        series: [{
            type: "scatter",
            data: chart.data.points || [],
            symbolSize: (value) => Math.max(10, Math.min(58, Math.sqrt(value[3]) * 0.65)),
            label: { show: true, formatter: (params) => params.value[4], color: "#0f172a", position: "top" },
            itemStyle: { opacity: 0.76, borderColor: "#fff", borderWidth: 1 }
        }]
    };
}

function buildOption(chart) {
    const builders = {
        bar3d: bar3dOption,
        treemap: treemapOption,
        sankey: sankeyOption,
        wordcloud: wordcloudOption,
        scatter: scatterOption,
        radar: radarOption,
        bubble: bubbleOption
    };
    const builder = builders[chart.chart_type];
    if (!builder) throw new Error(`不支持的图表类型：${chart.chart_type}`);
    const option = builder(chart);
    option.animation = !reducedMotion;
    option.aria = { enabled: true, decal: { show: true } };
    return option;
}

async function boot() {
    if (!chartId) throw new Error("缺少图表 ID");
    if (!window.echarts) throw new Error("ECharts 未加载");

    const response = await fetch("./data/analysis_summary.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`分析数据加载失败（HTTP ${response.status}）`);
    const summary = await response.json();
    const chart = (summary.charts || []).find((item) => item.id === chartId);
    if (!chart || chart.kind !== "interactive") throw new Error("没有找到对应的交互图数据");

    if (chart.plugin === "echarts-gl") {
        await loadScript("./js/vendor/echarts-gl.min.js");
    } else if (chart.plugin === "echarts-wordcloud") {
        await loadScript("./js/vendor/echarts-wordcloud.min.js");
    }

    const renderer = chart.chart_type === "bar3d" || chart.chart_type === "wordcloud" ? "canvas" : "svg";
    instance = window.echarts.init(chartElement, null, { renderer });
    instance.setOption(buildOption(chart), { notMerge: true, lazyUpdate: false });
    chartElement.setAttribute("aria-label", `${chart.title}。样本量 ${Number(chart.sample_n || 0).toLocaleString("zh-CN")}。`);
    hideStatus();

    resizeObserver = new ResizeObserver(() => instance?.resize());
    resizeObserver.observe(chartElement);
}

const dispose = () => {
    resizeObserver?.disconnect();
    resizeObserver = null;
    if (instance) {
        instance.dispose();
        instance = null;
    }
};

document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
        instance?.getZr()?.animation?.stop();
    } else {
        instance?.resize();
    }
});
window.addEventListener("pagehide", dispose, { once: true });
window.addEventListener("beforeunload", dispose, { once: true });

boot().catch((error) => {
    dispose();
    showStatus(error instanceof Error ? error.message : "图表加载失败");
});

