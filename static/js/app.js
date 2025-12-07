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

    function handleApiError(err) {
        var message = "Что-то пошло не так. Попробуйте позже.";
        function notify(msg) {
            showToast(msg || message, "error");
            try { document.dispatchEvent(new CustomEvent("ps-error", { detail: err })); } catch (_) {}
        }
        if (!err) return notify(message);
        if (typeof Response !== "undefined" && err instanceof Response) {
            err.json().then(function (data) {
                var msg = (data && (data.message || data.detail)) || message;
                notify(msg);
            }).catch(function () { notify(message); });
            return;
        }
        if (typeof err === "string") return notify(err);
        if (err.code && err.message) return notify(err.message);
        if (err.message) return notify(err.message);
        if (err.response && err.response.message) return notify(err.response.message);
        notify(message);
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
        const sheet = qs("[data-spots-sheet]") || qs("[data-spots-panel]");
        if (!sheet) return;
        const handle = qs("[data-sheet-handle]", sheet) || qs(".ps-bottom-sheet__handle", sheet);
        let currentState = sheet.getAttribute("data-sheet-state") || "collapsed";
        let startY = 0;
        let startShift = 0;
        let baseHeight = Math.min(window.innerHeight * 0.82, 760);
        let activePointerId = null;
        const STATE_ORDER = ["collapsed", "half", "full"];
        const COLLAPSED_HEIGHT = 72;

        function clamp(val, min, max) {
            return Math.max(min, Math.min(max, val));
        }

        function isFloating() {
            return isMobileWidth() && sheet.classList.contains("ps-bottom-sheet--floating");
        }

        function computeBaseHeight() {
            const viewportH = (window.visualViewport && window.visualViewport.height) || window.innerHeight;
            return Math.min(Math.max(viewportH * 0.82, 400), 780);
        }

        function apply(state, opts) {
            currentState = state === "peek" ? "collapsed" : state;
            sheet.setAttribute("data-sheet-state", currentState);
            if (!isFloating()) {
                sheet.style.removeProperty("--ps-sheet-shift");
                sheet.style.removeProperty("height");
                return;
            }
            baseHeight = computeBaseHeight();
            const rounded = Math.round(baseHeight);
            sheet.style.height = rounded + "px";
            sheet.style.setProperty("--ps-sheet-height", rounded + "px");
            let collapsed = COLLAPSED_HEIGHT;
            if ((window.visualViewport && window.visualViewport.height <= 440) || window.innerHeight <= 440) {
                collapsed = 60;
            }
            const rawShift = currentState === "full" ? 0 : currentState === "half" ? baseHeight * 0.45 : baseHeight - collapsed;
            const shift = clamp(rawShift, 0, baseHeight - 48);
            sheet.style.setProperty("--ps-sheet-shift", shift + "px");
            if (opts && opts.immediate) {
                sheet.style.transition = "none";
                requestAnimationFrame(function () {
                    sheet.style.transition = "";
                });
            }
        }

        function releasePointer(id) {
            if (id !== null && sheet.hasPointerCapture && sheet.hasPointerCapture(id)) {
                sheet.releasePointerCapture(id);
            }
            sheet.style.transition = "";
            activePointerId = null;
        }

        function gestureStart(evt) {
            if (!isFloating()) return;
            activePointerId = evt.pointerId;
            startY = evt.clientY;
            startShift = parseFloat(getComputedStyle(sheet).getPropertyValue("--ps-sheet-shift")) || baseHeight * 0.6;
            sheet.style.transition = "none";
            if (sheet.setPointerCapture) {
                sheet.setPointerCapture(activePointerId);
            }
            window.addEventListener("pointermove", gestureMove, { passive: true });
            window.addEventListener("pointerup", gestureEnd);
            window.addEventListener("pointercancel", gestureEnd);
        }

        function gestureMove(evt) {
            if (!isFloating() || evt.pointerId !== activePointerId) return;
            const delta = evt.clientY - startY;
            const nextShift = clamp(startShift + delta, 8, baseHeight - 64);
            sheet.style.setProperty("--ps-sheet-shift", nextShift + "px");
        }

        function gestureEnd(evt) {
            if (!isFloating() || (evt && evt.pointerId !== activePointerId)) {
                releasePointer(activePointerId);
                return;
            }
            window.removeEventListener("pointermove", gestureMove);
            window.removeEventListener("pointerup", gestureEnd);
            window.removeEventListener("pointercancel", gestureEnd);
            const shift = parseFloat(getComputedStyle(sheet).getPropertyValue("--ps-sheet-shift")) || baseHeight * 0.6;
            const ratio = shift / baseHeight;
            if (ratio < 0.25) {
                apply("full");
            } else if (ratio < 0.6) {
                apply("half");
            } else {
                apply("collapsed");
            }
            releasePointer(activePointerId);
        }

        if (handle) {
            handle.addEventListener("pointerdown", gestureStart);
            handle.addEventListener("click", function () {
                if (!isFloating()) return;
                const idx = STATE_ORDER.indexOf(currentState);
                const next = STATE_ORDER[(idx + 1) % STATE_ORDER.length] || "half";
                apply(next);
            });
        }

        window.addEventListener("resize", function () {
            apply(currentState, { immediate: true });
        });

        document.addEventListener("ps:spot-selection", function () {
            if (!isFloating()) return;
            if (currentState === "collapsed") {
                apply("half");
            } else if (currentState === "half") {
                apply("half");
            }
        });

        apply(currentState, { immediate: true });
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

    // ---------- Voice search (Web Speech API) ----------

    function initVoiceInput() {
        const trigger = qs("[data-voice-input]");
        const inputs = qsa("[data-geocode-input]");
        if (!trigger || !inputs.length) return;

        const submit = qs("[data-geocode-submit]");
        const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;

        if (!Recognition) {
            trigger.addEventListener("click", function () {
                showToast("Голосовой ввод недоступен на этом устройстве", "info");
            });
            trigger.setAttribute("aria-disabled", "true");
            return;
        }

        const recognition = new Recognition();
        recognition.lang = "ru-RU";
        recognition.continuous = false;
        recognition.interimResults = false;

        let listening = false;
        const defaultPlaceholder = inputs[0].getAttribute("placeholder") || "";

        function setListeningUi() {
            listening = true;
            trigger.classList.add("is-active");
            trigger.setAttribute("aria-pressed", "true");
            inputs.forEach(function (input) {
                input.placeholder = "Слушаю…";
            });
        }

        function clearListeningUi() {
            listening = false;
            trigger.classList.remove("is-active");
            trigger.setAttribute("aria-pressed", "false");
            inputs.forEach(function (input) {
                input.placeholder = defaultPlaceholder;
            });
        }

        function stopListening() {
            if (!listening) return;
            try {
                recognition.stop();
            } catch (_) {
                /* ignore */
            }
        }

        recognition.onstart = setListeningUi;
        recognition.onend = clearListeningUi;
        recognition.onerror = function () {
            clearListeningUi();
            showToast("Не удалось распознать речь. Попробуйте ещё раз.", "error");
        };
        recognition.onresult = function (event) {
            const transcript = event.results && event.results[0] && event.results[0][0] ? event.results[0][0].transcript : "";
            if (transcript) {
                inputs.forEach(function (input) {
                    input.value = transcript;
                    input.dispatchEvent(new Event("input", { bubbles: true }));
                });
                if (submit) {
                    submit.click();
                }
            }
            stopListening();
        };

        trigger.addEventListener("click", function () {
            if (listening) {
                stopListening();
                return;
            }
            try {
                recognition.start();
            } catch (err) {
                clearListeningUi();
                showToast("Голосовой ввод недоступен сейчас", "info");
            }
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
                .catch(function (err) {
                    if (window.ParkShare && window.ParkShare.handleApiError) window.ParkShare.handleApiError(err);
                });
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
                    .catch(function (err) { (window.ParkShare && window.ParkShare.handleApiError) ? window.ParkShare.handleApiError(err) : showToast("Не удалось сохранить карту", "error"); });
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
                        .catch(function (err) { (window.ParkShare && window.ParkShare.handleApiError) ? window.ParkShare.handleApiError(err) : showToast("Не удалось обновить карту", "error"); });
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
                        .catch(function (err) { (window.ParkShare && window.ParkShare.handleApiError) ? window.ParkShare.handleApiError(err) : showToast("Не удалось удалить карту", "error"); });
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

    // ---------- Onboarding ----------

    function initOnboarding() {
        const root = qs("[data-onboarding]");
        if (!root) return;
        const slides = qsa("[data-onboarding-slides] .ps-onboarding__slide", root);
        const btnNext = qs("[data-onboarding-next]", root);
        const btnSkip = qs("[data-onboarding-skip]", root);
        const storageKey = "ps_onboarded";
        let index = 0;

        function isDone() {
            try {
                return localStorage.getItem(storageKey) === "1";
            } catch (_) {
                return false;
            }
        }
        function markDone() {
            try {
                localStorage.setItem(storageKey, "1");
            } catch (_) {}
        }
        function show() {
            root.hidden = false;
            root.classList.add("is-visible");
            render();
        }
        function hide() {
            root.classList.remove("is-visible");
            setTimeout(function () {
                root.hidden = true;
            }, 200);
        }
        function render() {
            slides.forEach(function (slide, i) {
                slide.classList.toggle("is-active", i === index);
            });
            if (btnNext) {
                btnNext.textContent = index >= slides.length - 1 ? "Готово" : "Далее";
            }
        }
        function finish() {
            markDone();
            hide();
        }
        if (isDone()) return;
        if (btnNext) {
            btnNext.addEventListener("click", function () {
                if (index < slides.length - 1) {
                    index += 1;
                    render();
                } else {
                    finish();
                }
            });
        }
        if (btnSkip) {
            btnSkip.addEventListener("click", finish);
        }
        show();
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
        initOnboarding();
        initVoiceInput();
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
    window.ParkShare.handleApiError = handleApiError;
})();
