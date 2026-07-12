// Dashboard page charts: Risk Distribution (doughnut), Monthly Report
// (bar), and the three Machine Sensor Trend line charts (Temperature /
// Pressure / Vibration), which refresh via AJAX when a different machine
// is picked from the dropdown — no full page reload needed.

document.addEventListener("DOMContentLoaded", function () {
    const sensorCharts = {}; // model_key -> Chart.js instance, so we can .destroy() + rebuild on machine switch

    // ---- Risk Distribution (doughnut) --------------------------------------
    (function renderRiskDistribution() {
        const el = document.getElementById("risk-distribution-data");
        const canvas = document.getElementById("riskDistributionChart");
        if (!el || !canvas) return;

        const data = JSON.parse(el.textContent);
        new Chart(canvas.getContext("2d"), {
            type: "doughnut",
            data: {
                labels: ["Low", "Medium", "High", "Critical"],
                datasets: [{
                    data: [data.LOW || 0, data.MEDIUM || 0, data.HIGH || 0, data.CRITICAL || 0],
                    backgroundColor: ["#2a9d8f", "#3d5a80", "#f4a261", "#e63946"],
                }],
            },
            options: {
                responsive: true,
                plugins: { legend: { position: "bottom" } },
            },
        });
    })();

    // ---- Monthly Report (bar) ----------------------------------------------
    (function renderMonthlyReport() {
        const el = document.getElementById("monthly-report-data");
        const canvas = document.getElementById("monthlyReportChart");
        if (!el || !canvas) return;

        const data = JSON.parse(el.textContent);
        new Chart(canvas.getContext("2d"), {
            type: "bar",
            data: {
                labels: data.labels,
                datasets: [
                    {
                        label: "Predictions Run",
                        data: data.total,
                        backgroundColor: "rgba(13, 59, 102, 0.6)",
                    },
                    {
                        label: "High/Critical Risk",
                        data: data.high_critical,
                        backgroundColor: "rgba(230, 57, 70, 0.7)",
                    },
                ],
            },
            options: {
                responsive: true,
                scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
                plugins: { legend: { position: "bottom" } },
            },
        });
    })();

    // ---- Machine Sensor Trend charts (Temperature/Pressure/Vibration) -----
    const SENSOR_CHART_CONFIG = {
        temperature: { canvasId: "temperatureChart", noDataId: "temperatureNoData", color: "#e63946" },
        pressure: { canvasId: "pressureChart", noDataId: "pressureNoData", color: "#3d5a80" },
        vibration: { canvasId: "vibrationChart", noDataId: "vibrationNoData", color: "#f4a261" },
    };

    function renderSensorChart(key, chartData) {
        const config = SENSOR_CHART_CONFIG[key];
        const canvas = document.getElementById(config.canvasId);
        const noDataEl = document.getElementById(config.noDataId);
        if (!canvas) return;

        if (sensorCharts[key]) {
            sensorCharts[key].destroy();
            sensorCharts[key] = null;
        }

        if (!chartData || !chartData.labels || chartData.labels.length === 0) {
            canvas.classList.add("d-none");
            if (noDataEl) noDataEl.classList.remove("d-none");
            return;
        }

        canvas.classList.remove("d-none");
        if (noDataEl) noDataEl.classList.add("d-none");

        sensorCharts[key] = new Chart(canvas.getContext("2d"), {
            type: "line",
            data: {
                labels: chartData.labels,
                datasets: [{
                    label: chartData.sensor_name + " (" + chartData.unit + ")",
                    data: chartData.values,
                    borderColor: config.color,
                    backgroundColor: config.color + "22",
                    tension: 0.25,
                    pointRadius: 1.5,
                    fill: true,
                }],
            },
            options: {
                responsive: true,
                plugins: { legend: { display: false } },
                scales: { x: { ticks: { maxTicksLimit: 6 } } },
            },
        });
    }

    function renderAllSensorCharts(sensorChartsData) {
        Object.keys(SENSOR_CHART_CONFIG).forEach(function (key) {
            renderSensorChart(key, sensorChartsData ? sensorChartsData[key] : null);
        });
    }

    const initialDataEl = document.getElementById("sensor-charts-data");
    if (initialDataEl) {
        try {
            renderAllSensorCharts(JSON.parse(initialDataEl.textContent));
        } catch (e) {
            console.error("Could not parse initial sensor chart data:", e);
        }
    }

    // ---- AJAX machine switch ------------------------------------------------
    const picker = document.getElementById("machineSensorPicker");
    if (picker && window.DASHBOARD_MACHINE_API_URL_TEMPLATE) {
        picker.addEventListener("change", function () {
            const machineId = picker.value;
            const url = window.DASHBOARD_MACHINE_API_URL_TEMPLATE.replace("999999", machineId);

            fetch(url, { headers: { "X-Requested-With": "XMLHttpRequest" } })
                .then(function (response) {
                    if (!response.ok) throw new Error("Failed to load machine data (" + response.status + ")");
                    return response.json();
                })
                .then(function (data) {
                    renderAllSensorCharts(data.sensor_charts);
                })
                .catch(function (err) {
                    console.error(err);
                });
        });
    }
});
