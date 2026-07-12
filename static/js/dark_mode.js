// Dark mode toggle. The initial theme is already applied by the inline
// script in base.html's <head> (to avoid a flash of the wrong theme on
// load) — this file only handles the toggle button click and persists
// the choice.

document.addEventListener("DOMContentLoaded", function () {
    const toggleBtn = document.getElementById("darkModeToggle");
    if (!toggleBtn) return;

    function updateButtonIcon() {
        const isDark = document.documentElement.classList.contains("dark-mode");
        toggleBtn.textContent = isDark ? "☀️" : "🌙";
    }

    updateButtonIcon();

    toggleBtn.addEventListener("click", function () {
        document.documentElement.classList.toggle("dark-mode");
        const isDark = document.documentElement.classList.contains("dark-mode");
        localStorage.setItem("theme", isDark ? "dark" : "light");
        updateButtonIcon();
    });
});
