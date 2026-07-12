// Global JS shared across every page. Page-specific behavior (e.g. auth
// forms, dashboard charts) lives in its own file and is loaded only on the
// pages that need it via {% block extra_js %}.

document.addEventListener("DOMContentLoaded", function () {
    // Auto-dismiss alert messages after 5 seconds.
    document.querySelectorAll(".alert").forEach(function (alertEl) {
        setTimeout(function () {
            const alert = bootstrap.Alert.getOrCreateInstance(alertEl);
            alert.close();
        }, 5000);
    });
});
