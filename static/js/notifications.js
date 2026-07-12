// Notification bell in the navbar: polls the unread count periodically,
// and lazily loads the recent-notifications list the first time the
// dropdown is opened (rather than on every page load, to keep things
// light).

document.addEventListener("DOMContentLoaded", function () {
    const api = window.NOTIFICATIONS_API;
    if (!api) return;

    const badge = document.getElementById("notificationBadge");
    const bell = document.getElementById("notificationBell");
    const dropdown = document.getElementById("notificationDropdown");

    function getCookie(name) {
        const match = document.cookie.match(new RegExp("(^| )" + name + "=([^;]+)"));
        return match ? match[2] : null;
    }

    function updateBadge(count) {
        if (!badge) return;
        if (count > 0) {
            badge.textContent = count > 9 ? "9+" : count;
            badge.classList.remove("d-none");
        } else {
            badge.classList.add("d-none");
        }
    }

    function refreshUnreadCount() {
        fetch(api.unreadCount, { headers: { "X-Requested-With": "XMLHttpRequest" } })
            .then((r) => r.json())
            .then((data) => updateBadge(data.unread_count))
            .catch(() => {});
    }

    function renderDropdown(data) {
        if (!dropdown) return;
        dropdown.innerHTML = "";

        if (!data.notifications || data.notifications.length === 0) {
            dropdown.innerHTML = '<li class="px-3 py-2 text-muted small">No notifications yet.</li>';
        } else {
            data.notifications.forEach(function (n) {
                const li = document.createElement("li");
                const a = document.createElement("a");
                a.href = "#";
                a.className = "dropdown-item small py-2" + (n.is_read ? "" : " fw-bold");
                a.textContent = n.message;
                a.title = n.created_at;
                a.addEventListener("click", function (e) {
                    e.preventDefault();
                    markReadAndGo(n.id, n.link_url);
                });
                li.appendChild(a);
                dropdown.appendChild(li);
            });
        }

        const viewAllLi = document.createElement("li");
        viewAllLi.innerHTML = `<hr class="dropdown-divider"><a class="dropdown-item text-center small" href="${api.viewAll}">View all notifications</a>`;
        dropdown.appendChild(viewAllLi);

        updateBadge(data.unread_count);
    }

    function markReadAndGo(id, linkUrl) {
        const url = api.markReadTemplate.replace("999999", id);
        fetch(url, {
            method: "POST",
            headers: {
                "X-Requested-With": "XMLHttpRequest",
                "X-CSRFToken": getCookie("csrftoken"),
            },
        }).finally(function () {
            if (linkUrl) window.location.href = linkUrl;
            else refreshUnreadCount();
        });
    }

    if (bell) {
        bell.addEventListener("click", function () {
            fetch(api.recent, { headers: { "X-Requested-With": "XMLHttpRequest" } })
                .then((r) => r.json())
                .then(renderDropdown)
                .catch(() => {});
        });
    }

    refreshUnreadCount();
    setInterval(refreshUnreadCount, 30000); // poll every 30s
});
