// Machine list page behavior: changing a filter dropdown re-submits the
// search form automatically, so the user doesn't have to click "Search"
// again after picking a status/department/type filter.

document.addEventListener("DOMContentLoaded", function () {
    const form = document.getElementById("filter-form");
    if (!form) return;

    form.querySelectorAll(".filter-auto-submit").forEach(function (select) {
        select.addEventListener("change", function () {
            form.submit();
        });
    });
});
