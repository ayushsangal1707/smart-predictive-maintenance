// Manual sensor entry page: when the user picks a Machine, fetch that
// machine's active sensors via AJAX and repopulate the Sensor dropdown,
// instead of showing every sensor for every machine in one long list.

document.addEventListener("DOMContentLoaded", function () {
    const machineSelect = document.querySelector("#id_machine");
    const sensorSelect = document.querySelector("#id_sensor");
    if (!machineSelect || !sensorSelect) return;

    function loadSensorsForMachine(machineId, preselectSensorId) {
        if (!machineId) {
            sensorSelect.innerHTML = '<option value="">Select a machine first</option>';
            return;
        }

        const url = window.SENSORS_API_BASE + machineId + "/sensors/";

        fetch(url, { headers: { "X-Requested-With": "XMLHttpRequest" } })
            .then(function (response) {
                if (!response.ok) throw new Error("Failed to load sensors (" + response.status + ")");
                return response.json();
            })
            .then(function (data) {
                sensorSelect.innerHTML = "";
                if (!data.sensors || data.sensors.length === 0) {
                    sensorSelect.innerHTML = '<option value="">No active sensors for this machine</option>';
                    return;
                }
                data.sensors.forEach(function (sensor) {
                    const opt = document.createElement("option");
                    opt.value = sensor.id;
                    opt.textContent = sensor.sensor_name + " (" + sensor.unit + ")";
                    if (preselectSensorId && String(sensor.id) === String(preselectSensorId)) {
                        opt.selected = true;
                    }
                    sensorSelect.appendChild(opt);
                });
            })
            .catch(function (err) {
                console.error(err);
                sensorSelect.innerHTML = '<option value="">Could not load sensors — try again</option>';
            });
    }

    machineSelect.addEventListener("change", function () {
        loadSensorsForMachine(machineSelect.value, null);
    });

    // On initial page load (e.g. after a validation error re-renders the
    // form), pre-load sensors for whichever machine/sensor was already
    // selected so the form doesn't appear to have "lost" the choice.
    if (machineSelect.value) {
        const currentSensorId = sensorSelect.getAttribute("data-selected") || sensorSelect.value;
        loadSensorsForMachine(machineSelect.value, currentSensorId);
    }
});
