// Behavior for login / register / change-password / reset-password forms.

document.addEventListener("DOMContentLoaded", function () {

    // ---- Show / hide password toggles ----------------------------------
    document.querySelectorAll(".toggle-password").forEach(function (toggle) {
        toggle.addEventListener("click", function () {
            const targetId = toggle.getAttribute("data-target");
            const input = document.getElementById(targetId);
            if (!input) return;
            const isHidden = input.type === "password";
            input.type = isHidden ? "text" : "password";
            toggle.textContent = isHidden ? "Hide" : "Show";
        });
    });

    // ---- Live password strength meter -----------------------------------
    const strengthInput = document.querySelector("[data-password-strength]");
    if (strengthInput) {
        const bar = document.querySelector(".password-strength-bar-fill");
        const label = document.querySelector(".password-strength-label");

        strengthInput.addEventListener("input", function () {
            const score = scorePassword(strengthInput.value);
            renderStrength(score, bar, label);
        });
    }

    function scorePassword(password) {
        let score = 0;
        if (!password) return score;

        if (password.length >= 8) score += 1;
        if (password.length >= 12) score += 1;
        if (/[A-Z]/.test(password)) score += 1;
        if (/[0-9]/.test(password)) score += 1;
        if (/[^A-Za-z0-9]/.test(password)) score += 1;

        return score; // 0 - 5
    }

    function renderStrength(score, bar, label) {
        if (!bar) return;

        const levels = [
            { pct: 0, color: "#e63946", text: "Very weak" },
            { pct: 20, color: "#e63946", text: "Weak" },
            { pct: 40, color: "#f4a261", text: "Fair" },
            { pct: 60, color: "#f4a261", text: "Good" },
            { pct: 80, color: "#2a9d8f", text: "Strong" },
            { pct: 100, color: "#2a9d8f", text: "Very strong" },
        ];

        const level = levels[score];
        bar.style.width = level.pct + "%";
        bar.style.backgroundColor = level.color;
        if (label) label.textContent = level.text;
    }
});
