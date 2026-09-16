/*
 * Dx — keyboard and scanner support.
 *
 * Hand-written, no framework, no build step, no network fetch. The application
 * runs unchanged on an air-gapped laboratory network, and this file does not
 * change that.
 *
 * Everything here is an enhancement: with JavaScript disabled every screen
 * still works, because each behaviour below replaces a mouse action that
 * remains available.
 */
(function () {
    "use strict";

    // ── Result entry: keyboard-driven value entry ────────────────────────────
    //
    // A twenty-analyte panel is twenty values. Reaching for the mouse between
    // each one is the difference between thirty seconds and three minutes, and
    // staff frequently have one hand on a rack.

    function entryFields(form) {
        return Array.prototype.slice
            .call(form.querySelectorAll("input[type='text'], input[type='number']"))
            .filter(function (field) {
                return !field.disabled && field.offsetParent !== null;
            });
    }

    function initResultEntry() {
        var form = document.querySelector("[data-dx-entry-form]");
        if (!form) return;

        var fields = entryFields(form);
        if (fields.length === 0) return;

        // Start where the work starts.
        if (!document.activeElement || document.activeElement === document.body) {
            fields[0].focus();
            fields[0].select();
        }

        form.addEventListener("keydown", function (event) {
            var field = event.target;
            if (fields.indexOf(field) === -1) return;

            // Ctrl/Cmd+Enter submits the form's primary action from any field.
            if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
                event.preventDefault();
                var primary = form.querySelector("button.btn-primary[type='submit']");
                if (primary) primary.click();
                return;
            }

            // Enter and the arrow keys walk the column. Enter would otherwise
            // submit, which is rarely what someone typing a panel intends.
            var step = 0;
            if (event.key === "Enter" || event.key === "ArrowDown") step = 1;
            else if (event.key === "ArrowUp") step = -1;
            if (step === 0) return;

            event.preventDefault();
            var next = fields[fields.indexOf(field) + step];
            if (next) {
                next.focus();
                next.select();
            } else if (step === 1) {
                // Past the last value: move to the action, don't submit blindly.
                var button = form.querySelector("button[type='submit']");
                if (button) button.focus();
            }
        });
    }

    // ── Search box: focus from anywhere ──────────────────────────────────────
    //
    // "/" is the convention for jump-to-search. A barcode scanner types its
    // payload and presses Enter, so a focused box is all a scan needs.

    function initSearchShortcut() {
        var box = document.querySelector("[data-dx-search]");
        if (!box) return;

        document.addEventListener("keydown", function (event) {
            if (event.key !== "/" || event.ctrlKey || event.metaKey || event.altKey) return;

            var active = document.activeElement;
            var tag = active ? active.tagName : "";
            if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
            if (active && active.isContentEditable) return;

            event.preventDefault();
            box.focus();
            box.select();
        });
    }

    // ── Batch selection ──────────────────────────────────────────────────────
    //
    // Verifying twelve orders one page at a time is twelve page loads and
    // twelve password entries. The header checkbox and the running count make
    // a batch selectable; the server still applies every regulatory gate to
    // each order individually.

    function initBatchSelection() {
        var table = document.querySelector("[data-dx-batch]");
        if (!table) return;

        var master = table.querySelector("[data-dx-batch-all]");
        var boxes = Array.prototype.slice.call(
            table.querySelectorAll("input[type='checkbox'][name='orders']")
        );
        var counter = document.querySelector("[data-dx-batch-count]");
        var actions = document.querySelector("[data-dx-batch-actions]");

        function refresh() {
            var chosen = boxes.filter(function (box) { return box.checked; }).length;
            if (counter) {
                counter.textContent = chosen === 0
                    ? "none selected"
                    : chosen + " selected";
            }
            if (actions) actions.hidden = chosen === 0;
            if (master) {
                master.checked = chosen > 0 && chosen === boxes.length;
                master.indeterminate = chosen > 0 && chosen < boxes.length;
            }
        }

        if (master) {
            master.addEventListener("change", function () {
                boxes.forEach(function (box) { box.checked = master.checked; });
                refresh();
            });
        }
        boxes.forEach(function (box) { box.addEventListener("change", refresh); });
        refresh();
    }


    /* ── Record locking ──────────────────────────────────────────────────────
     *
     * A screen that has reserved a record keeps its lock alive while it is
     * open, and gives it up when the user leaves. Without the release, a
     * record stays locked for the full TTL after somebody simply navigates
     * away — and a laboratory that meets that a few times learns to break
     * locks reflexively, which is how a control stops being one.
     *
     * The release uses sendBeacon because it is the only request the browser
     * reliably delivers from a page that is going away.
     */
    function initRecordLock() {
        var node = document.getElementById("dx-lock-config");
        if (!node) { return; }

        var config;
        try { config = JSON.parse(node.textContent); } catch (error) { return; }
        if (!config.held) { return; }

        var indicator = document.querySelector("[data-lock-held]");
        if (indicator) { indicator.hidden = false; }

        var token = getCookie("csrftoken");
        var body = function () {
            var data = new FormData();
            data.append("entity_type", config.entityType);
            data.append("entity_id", config.entityId);
            data.append("csrfmiddlewaretoken", token);
            return data;
        };

        /* Refresh well inside the server's TTL so a slow typist never loses
         * the lock mid-entry. */
        var timer = window.setInterval(function () {
            fetch(config.heartbeatUrl, {
                method: "POST", body: body(), credentials: "same-origin",
                headers: { "X-CSRFToken": token }
            }).then(function (response) {
                if (response.status === 409) {
                    /* Expired and taken, or broken by a manager. Say so rather
                     * than letting the next save fail with no explanation. */
                    window.clearInterval(timer);
                    announceLockLoss(response);
                }
            }).catch(function () { /* transient; the next tick retries */ });
        }, 120000);

        var released = false;
        var release = function () {
            if (released) { return; }
            released = true;
            window.clearInterval(timer);
            if (navigator.sendBeacon) {
                navigator.sendBeacon(config.releaseUrl, body());
            }
        };

        /* pagehide covers navigation, tab close and the bfcache; visibility
         * alone would release the lock when someone glances at another tab. */
        window.addEventListener("pagehide", release);

        /* A successful save releases server-side, so do not fight it. */
        document.querySelectorAll("form").forEach(function (form) {
            form.addEventListener("submit", function () { released = true; });
        });
    }

    function announceLockLoss(response) {
        response.json().then(function (data) {
            var banner = document.createElement("div");
            banner.className = "alert alert-error no-print";
            banner.textContent = data.holder
                ? "This record is now open by " + data.holder +
                  ". Your changes will not be saved — reload before continuing."
                : "Your hold on this record has been released. Reload before continuing.";
            var content = document.querySelector(".content");
            if (content) { content.insertBefore(banner, content.firstChild); }
        }).catch(function () { /* nothing useful to say */ });
    }

    function getCookie(name) {
        var match = document.cookie.match(new RegExp("(^| )" + name + "=([^;]+)"));
        return match ? decodeURIComponent(match[2]) : "";
    }

    function start() {
        initRecordLock();
        initResultEntry();
        initSearchShortcut();
        initBatchSelection();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", start);
    } else {
        start();
    }
})();
