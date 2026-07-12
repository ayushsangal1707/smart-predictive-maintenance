// Renders the Sensor Reading History line chart. Reads the JSON payload
// embedded server-side in #sensor-chart-data (see sensors/views.py ->
// reading_history) rather than making a separate AJAX call, since the data
// is already computed for the current page's filters.

document.addEventListener("DOMContentLoaded", function () {
    const dataEl = document.getElementById("sensor-chart-data");
    const canvas = document.getElementById("sensorHistoryChart");
    if (!dataEl || !canvas) return;

    let chartData;
    try {
        chartData = JSON.parse(dataEl.textContent);
    } catch (e) {
        console.error("Could not parse chart data:", e);
        return;
    }

    if (!chartData.labels || chartData.labels.length === 0) {
        canvas.replaceWith(Object.assign(document.createElement("p"), {
            className: "text-muted text-center mb-0",
            textContent: "No data available to chart for the current filters.",
        }));
        return;
    }

    const datasets = [
        {
            label: chartData.sensor_name ? (chartData.sensor_name + " (" + chartData.unit + ")") : "Value",
            data: chartData.values,
            borderColor: "#0d3b66",
            backgroundColor: "rgba(13, 59, 102, 0.1)",
            tension: 0.25,
            pointRadius: 2,
            fill: true,
        },
    ];

    // Draw the sensor's normal-range band as two reference lines, if a
    // single sensor is selected (normal_min/max only makes sense per-sensor,
    // not across a mixed set of sensors with different units).
    if (chartData.normal_min !== null && chartData.normal_min !== undefined) {
        datasets.push({
            label: "Normal Min",
            data: chartData.labels.map(() => chartData.normal_min),
            borderColor: "#2a9d8f",
            borderDash: [6, 4],
            pointRadius: 0,
            fill: false,
        });
    }
    if (chartData.normal_max !== null && chartData.normal_max !== undefined) {
        datasets.push({
            label: "Normal Max",
            data: chartData.labels.map(() => chartData.normal_max),
            borderColor: "#e63946",
            borderDash: [6, 4],
            pointRadius: 0,
            fill: false,
        });
    }

    new Chart(canvas.getContext("2d"), {
        type: "line",
        data: {
            labels: chartData.labels,
            datasets: datasets,
        },
        options: {
            responsive: true,
            interaction: { mode: "index", intersect: false },
            scales: {
                x: { ticks: { maxTicksLimit: 12 } },
                y: { beginAtZero: false },
            },
            plugins: {
                legend: { position: "top" },
            },
        },
    });
});
