(function () {
    "use strict";

    window.ParkShare = window.ParkShare || {};

    // ---------- Helpers ----------

    function qs(selector, scope) {
        return (scope || document).querySelector(selector);
    }

    function qsa(selector, scope) {
        return Array.prototype.slice.call((scope || document).querySelectorAll(selector));
    }

    function isMobileWidth() {
        return window.matchMedia("(max-width: 767px)").matches;
    }

    // ---------- Service worker (registration is idempotent, PWA layer can override) ----------

    if ("serviceWorker" in navigator && !window.__PS_PWA_REGISTERED__) {
        window.__PS_PWA_REGISTERED__ = true;
        window.addEventListener("load", function () {
            navigator.serviceWorker
                .register("/service-worker.js", {updateViaCache: "none"})
                .then(function (reg) {
                    console.log("[SW] registered (legacy entry)", reg.scope);
                })
                .catch(function (err) {
                    console.warn("[SW] registration failed", err);
                });
        });
    }

    // ---------- Mobile menu ----------

    function initMenu() {
        const toggle = qs("[data-menu-toggle]");
        const menu = qs("[data-menu]");

        if (!toggle || !menu) return;

        function syncAria(isOpen) {
            toggle.setAttribute("aria-expanded", String(isOpen));
            toggle.setAttribute("aria-label", isOpen ? "Закрыть меню" : "Открыть меню");
        }

        toggle.addEventListener("click", function () {
            const isOpen = toggle.classList.toggle("is-open");
            menu.classList.toggle("is-open", isOpen);
            document.body.classList.toggle("ps-menu-open", isOpen);
            syncAria(isOpen);
        });

        syncAria(toggle.classList.contains("is-open"));

        // закрывать по клику на ссылку (на мобиле)
        qsa(".ps-nav-link", menu).forEach(function (link) {
            link.addEventListener("click", function () {
                toggle.classList.remove("is-open");
                menu.classList.remove("is-open");
                document.body.classList.remove("ps-menu-open");
                syncAria(false);
            });
        });
    }

    // ---------- Smooth scroll ----------

    function initSmoothScroll() {
        qsa("[data-scroll-to]").forEach(function (el) {
            el.addEventListener("click", function (e) {
                const href = el.getAttribute("href");
                if (!href || !href.startsWith("#")) return;
                const target = qs(href);
                if (!target) return;
                e.preventDefault();
                window.scrollTo({
                    top: target.getBoundingClientRect().top + window.scrollY - 72,
                    behavior: "smooth"
                });
            });
        });
    }

    // ---------- Back to top ----------

    function initBackToTop() {
        const btn = qs("[data-back-to-top]");
        if (!btn) return;

        function onScroll() {
            if (window.scrollY > 300) {
                btn.classList.add("is-visible");
            } else {
                btn.classList.remove("is-visible");
            }
        }

        window.addEventListener("scroll", onScroll, {passive: true});
        onScroll();

        btn.addEventListener("click", function () {
            window.scrollTo({top: 0, behavior: "smooth"});
        });
    }

    // ---------- Toasts ----------

    function showToast(message, type) {
        type = type || "info";
        const container = qs(".ps-toast-container");
        if (!container) return;

        const toast = document.createElement("div");
        toast.className = "ps-toast ps-toast--" + type;

        const msg = document.createElement("div");
        msg.className = "ps-toast-message";
        msg.textContent = message;

        const close = document.createElement("button");
        close.className = "ps-toast-close";
        close.type = "button";
        close.innerHTML = "×";

        close.addEventListener("click", function () {
            toast.remove();
        });

        toast.appendChild(msg);
        toast.appendChild(close);
        container.appendChild(toast);

        setTimeout(function () {
            toast.remove();
        }, 4000);
    }

    // ---------- PWA install banner ----------

    let deferredPrompt = null;
    const INSTALL_DISMISS_KEY = "pwaPromptDismissedUntil";
    const INSTALL_DISMISS_DAYS = 30;

    function isStandalone() {
        return window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone;
    }

    function isMobileDevice() {
        const ua = navigator.userAgent || "";
        const isIOS = /iPhone|iPad|iPod/i.test(ua);
        const isAndroid = /Android/i.test(ua);
        const isCoarse = window.matchMedia && window.matchMedia("(pointer:coarse)").matches;
        return isIOS || isAndroid || isCoarse;
    }

    function dismissedUntil() {
        try {
            const value = localStorage.getItem(INSTALL_DISMISS_KEY);
            return value ? parseInt(value, 10) : 0;
        } catch (_) {
            return 0;
        }
    }

    function markDismiss(days) {
        try {
            const until = Date.now() + days * 24 * 60 * 60 * 1000;
            localStorage.setItem(INSTALL_DISMISS_KEY, String(until));
        } catch (_) {}
    }

    function canShowBanner() {
        if (!isMobileDevice() || isStandalone()) return false;
        const until = dismissedUntil();
        if (until && until > Date.now()) return false;
        return true;
    }

    function initInstallBanner() {
        const banner = qs("[data-install-banner]");
        const btnAccept = qs("[data-install-accept]", banner);
        const btnDismiss = qs("[data-install-dismiss]", banner);
        const menuButton = qs("[data-nav-install-app]");
        const fallbackUrl = (menuButton && menuButton.getAttribute("data-install-href")) || "/pwa-install/";

        if (!banner || !btnAccept || !btnDismiss) return;

        function hideBanner() {
            banner.classList.remove("is-visible");
            setTimeout(function () { banner.hidden = true; }, 200);
        }

        function showBanner() {
            if (!canShowBanner()) return;
            banner.hidden = false;
            requestAnimationFrame(function () { banner.classList.add("is-visible"); });
        }

        function triggerInstall(source) {
            if (deferredPrompt) {
                deferredPrompt.prompt();
                deferredPrompt.userChoice
                    .then(function (choiceResult) {
                        if (choiceResult.outcome === "accepted") {
                            showToast("Установка ParkShare RU запущена", "success");
                            markDismiss(365);
                        }
                    })
                    .finally(function () {
                        deferredPrompt = null;
                        hideBanner();
                    });
            } else {
                if (fallbackUrl) {
                    window.location.href = fallbackUrl;
                } else {
                    showToast("Откройте меню браузера и выберите «Добавить на экран»", "info");
                }
                hideBanner();
            }
        }

        if (menuButton) {
            if (!isMobileDevice() || isStandalone()) {
                menuButton.style.display = "none";
            }
            menuButton.addEventListener("click", function () { triggerInstall("menu"); });
        }

        window.addEventListener("beforeinstallprompt", function (e) {
            e.preventDefault();
            deferredPrompt = e;
            if (canShowBanner()) {
                showBanner();
            }
        });

        btnDismiss.addEventListener("click", function () {
            markDismiss(INSTALL_DISMISS_DAYS);
            hideBanner();
            deferredPrompt = null;
        });

        btnAccept.addEventListener("click", function () { triggerInstall("banner"); });

        window.addEventListener("appinstalled", function () {
            markDismiss(365);
            hideBanner();
        });

        if (canShowBanner()) {
            showBanner();
        }
    }

    // ---------- Skeleton removal ----------

    function initSkeletons() {
        const cards = qsa(".ps-card--skeleton");
        if (!cards.length) return;

        // Имитация загрузки данных — через небольшой таймаут
        window.setTimeout(function () {
            cards.forEach(function (card) {
                card.parentNode && card.parentNode.removeChild(card);
            });
        }, 350);
    }

    // ---------- Spots bottom sheet (mobile) ----------

    function initSpotsSheet() {
        const panel = qs("[data-spots-panel]");
        if (!panel) return;
        const triggers = qsa("[data-open-spots]");

        function setState(open) {
            panel.classList.toggle("is-sheet-open", open);
            if (open) {
                panel.scrollIntoView({ behavior: "smooth" });
            }
        }

        triggers.forEach(function (btn) {
            btn.addEventListener("click", function () {
                const next = !panel.classList.contains("is-sheet-open");
                setState(next);
            });
        });

        window.addEventListener("resize", function () {
            if (!isMobileWidth()) {
                panel.classList.remove("is-sheet-open");
            }
        });
    }

// ---------- Adaptive AI probe ----------
function initAdaptiveProbe() {
    const payload = {
        width: window.innerWidth,
        height: window.innerHeight,
        pixelRatio: window.devicePixelRatio || 1,
        platform: document.documentElement.getAttribute("data-platform") || "RU",
    };

    fetch("/api/ai/parkmate/config/", {
        method: "POST",
        credentials: "include",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            client: payload,
            action: "adaptive-profile",
        }),
        keepalive: true, // чтобы не блокировать навигацию, аналогично sendBeacon
    }).catch(function () {
        // молча игнорируем
    });
}





    // ---------- Geolocation helper ----------

    function initGeolocation() {
        const buttons = qsa("[data-fill-location]");
        if (!buttons.length) return;

        function fill(lat, lng) {
            const latInput = qs("#lat");
            const lngInput = qs("#lng");
            if (!latInput || !lngInput) return;
            latInput.value = lat.toFixed(5);
            lngInput.value = lng.toFixed(5);
            showToast("Координаты определены, нажмите «Найти места»", "success");
        }

        buttons.forEach(function (btn) {
            btn.addEventListener("click", function () {
                if (!("geolocation" in navigator)) {
                    showToast("Геолокация недоступна в этом браузере", "error");
                    return;
                }

                navigator.geolocation.getCurrentPosition(
                    function (pos) {
                        fill(pos.coords.latitude, pos.coords.longitude);
                    },
                    function () {
                        showToast("Не удалось получить местоположение", "error");
                    },
                    {
                        enableHighAccuracy: false,
                        timeout: 8000,
                        maximumAge: 60000
                    }
                );
            });
        });
    }

    // ---------- Payment methods (ЛК) ----------

    const PAYMENT_METHODS_ENDPOINT = "/api/payments/methods/";

    function getCSRFToken() {
        const match = document.cookie.match(/csrftoken=([^;]+)/);
        return match ? match[1] : "";
    }

    function detectBrand(num) {
        if (!num) return "other";
        if (/^4/.test(num)) return "visa";
        if (/^5[1-5]/.test(num)) return "mc";
        if (/^220[0-4]/.test(num)) return "mir";
        if (/^62/.test(num)) return "up";
        return "other";
    }

    function renderPaymentMethods(methods, container) {
        if (!container) return;
        if (!methods || !methods.length) {
            container.innerHTML = "<div class='ps-empty'>Карты пока не добавлены.</div>";
            return;
        }
        container.innerHTML = methods
            .map(function (method) {
                const brand = method.brand ? method.brand.toUpperCase() : "CARD";
                const defaultBadge = method.is_default ? "<span class='ps-badge ps-badge--success'>По умолчанию</span>" : "";
                return (
                    "<div class='ps-payment-card'>" +
                    "<div>" +
                    "<div class='ps-payment-brand'>" + brand + " · " + (method.mask || ("**** " + method.last4)) + " " + defaultBadge + "</div>" +
                    "<div class='ps-payment-meta'>Срок: " + method.exp_month + "/" + method.exp_year + (method.label ? " · " + method.label : "") + "</div>" +
                    "</div>" +
                    "<div class='ps-payment-actions'>" +
                    "<button class='ps-btn ps-btn-ghost ps-btn-sm' data-payment-default='" + method.id + "'>Сделать осн.</button>" +
                    "<button class='ps-btn ps-btn-ghost ps-btn-sm' data-payment-delete='" + method.id + "'>Удалить</button>" +
                    "</div>" +
                    "</div>"
                );
            })
            .join("");
    }

    function initPaymentMethods() {
        const container = qs("[data-payment-methods]");
        const form = qs("[data-payment-method-form]");
        if (!container && !form) return;

        function loadMethods() {
            fetch(PAYMENT_METHODS_ENDPOINT, { credentials: "include" })
                .then(function (resp) { return resp.json(); })
                .then(function (data) { renderPaymentMethods(data.results || data, container); })
                .catch(function () { showToast("Не удалось загрузить способы оплаты", "error"); });
        }

        if (form) {
            form.addEventListener("submit", function (evt) {
                evt.preventDefault();
                const fd = new FormData(form);
                const cardNumber = (fd.get("card_number") || "").replace(/\D/g, "");
                const exp = (fd.get("exp") || "").split("/");
                const expMonth = parseInt(exp[0], 10) || 1;
                const expYear = parseInt((exp[1] || "").replace(/[^0-9]/g, ""), 10) || 30;
                const payload = {
                    label: fd.get("label") || fd.get("provider") || "Моя карта",
                    brand: detectBrand(cardNumber),
                    last4: cardNumber.slice(-4) || "0000",
                    exp_month: expMonth,
                    exp_year: expYear,
                    is_default: fd.get("is_default") === "on",
                    token_masked: "tok_" + (cardNumber.slice(-6) || "card") + Date.now(),
                };

                fetch(PAYMENT_METHODS_ENDPOINT, {
                    method: "POST",
                    credentials: "include",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": getCSRFToken(),
                    },
                    body: JSON.stringify(payload),
                })
                    .then(function (resp) { return resp.json(); })
                    .then(function () {
                        showToast("Карта сохранена", "success");
                        form.reset();
                        loadMethods();
                    })
                    .catch(function () { showToast("Не удалось сохранить карту", "error"); });
            });
        }

        if (container) {
            container.addEventListener("click", function (evt) {
                const defBtn = evt.target.closest("[data-payment-default]");
                const delBtn = evt.target.closest("[data-payment-delete]");
                if (defBtn) {
                    const id = defBtn.getAttribute("data-payment-default");
                    fetch(PAYMENT_METHODS_ENDPOINT + id + "/", {
                        method: "PATCH",
                        credentials: "include",
                        headers: {
                            "Content-Type": "application/json",
                            "X-CSRFToken": getCSRFToken(),
                        },
                        body: JSON.stringify({ is_default: true }),
                    })
                        .then(function (resp) { return resp.json(); })
                        .then(function () { showToast("Карта выбрана по умолчанию", "success"); loadMethods(); })
                        .catch(function () { showToast("Не удалось обновить карту", "error"); });
                }
                if (delBtn) {
                    const id = delBtn.getAttribute("data-payment-delete");
                    fetch(PAYMENT_METHODS_ENDPOINT + id + "/", {
                        method: "DELETE",
                        credentials: "include",
                        headers: { "X-CSRFToken": getCSRFToken() },
                    })
                        .then(function (resp) { if (!resp.ok) throw new Error(); })
                        .then(function () { showToast("Карта удалена", "info"); loadMethods(); })
                        .catch(function () { showToast("Не удалось удалить карту", "error"); });
                }
            });
        }

        loadMethods();
    }

    // ---------- Bottom navigation ----------



    function initBottomNav() {
        const nav = qs("[data-bottom-nav]");
        if (!nav) return;
        const items = qsa("[data-nav]", nav);

        const defaultKey = (function () {
            const path = window.location.pathname;
            if (window.location.hash === "#assistant") return "assistant";
            if (path.indexOf("/assistant") === 0 || path.indexOf("/ai") === 0) return "assistant";
            if (path.indexOf("/личный-кабинет") === 0) return "bookings";
            if (path.indexOf("/кабинет-владельца") === 0) return "parking";
            if (path.indexOf("/map") === 0) return "map";
            return "map";
        })();

        function setActive(key) {
            const target = key || defaultKey;
            items.forEach(function (item) {
                const current = item.getAttribute("data-nav");
                item.classList.toggle("is-active", current === target);
            });
        }

        items.forEach(function (item) {
            item.addEventListener("click", function () {
                const key = item.getAttribute("data-nav");
                if (key) setActive(key);
            });
        });

        setActive(defaultKey);
    }

    // ---------- Init ----------

    document.addEventListener("DOMContentLoaded", function () {
        initMenu();
        initSmoothScroll();
        initBackToTop();
        initInstallBanner();
        initSkeletons();
        initSpotsSheet();
        initAdaptiveProbe();
        initGeolocation();
        initPaymentMethods();
        initBottomNav();

        const aiLauncher = document.querySelector(".ai-assistant-launcher");
        const aiPanel = document.querySelector(".ai-assistant-panel");
        const aiClose = document.querySelector(".ai-assistant-panel__close");

        if (aiLauncher && aiPanel) {
            aiLauncher.addEventListener("click", function () {
                aiPanel.classList.toggle("is-open");
            });
        }

        if (aiClose && aiPanel) {
            aiClose.addEventListener("click", function () {
                aiPanel.classList.remove("is-open");
            });
        }
    });

    // Экспортируем showToast в глобальную область на всякий
    window.ParkShare = window.ParkShare || {};
    window.ParkShare.showToast = showToast;
})();
