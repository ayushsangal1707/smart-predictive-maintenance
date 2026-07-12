// Renders the per-machine prediction-probability trend chart on the
// Prediction History page, reading the JSON payload the view embedded
// server-side (see predictions/views.py -> machine_prediction_history).

document.addEventListener("DOMContentLoaded", function () {
    const dataEl = document.getElementById("prediction-chart-data");
    const canvas = document.getElementById("predictionTrendChart");
    if (!dataEl || !canvas) return;

    let chartData;
    try {
        chartData = JSON.parse(dataEl.textContent);
    } catch (e) {
        console.error("Could not parse prediction chart data:", e);
        return;
    }

    if (!chartData.labels || chartData.labels.length === 0) {
        canvas.replaceWith(Object.assign(document.createElement("p"), {
            className: "text-muted text-center mb-0",
            textContent: "No prediction history yet to chart.",
        }));
        return;
    }

    new Chart(canvas.getContext("2d"), {
        type: "line",
        data: {
            labels: chartData.labels,
            datasets: [
                {
                    label: "Failure Probability",
                    data: chartData.values,
                    borderColor: "#ee6c4d",
                    backgroundColor: "rgba(238, 108, 77, 0.15)",
                    tension: 0.25,
                    pointRadius: 3,
                    fill: true,
                },
                {
                    label: "Critical Threshold",
                    data: chartData.labels.map(() => 0.75),
                    borderColor: "#e63946",
                    borderDash: [6, 4],
                    pointRadius: 0,
                    fill: false,
                },
            ],
        },
        options: {
            responsive: true,
            scales: {
                y: { min: 0, max: 1, ticks: { callback: (v) => (v * 100).toFixed(0) + "%" } },
                x: { ticks: { maxTicksLimit: 12 } },
            },
            plugins: { legend: { position: "top" } },
        },
    });
});
