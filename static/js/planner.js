(() => {
    const configEl = document.getElementById("planner-config");
    let endpoints = {
        profiles_endpoint: "/api/planner/profiles/",
        plan_endpoint: "/api/planner/plan/",
    };
    if (configEl && configEl.textContent) {
        try {
            endpoints = JSON.parse(configEl.textContent);
        } catch (e) {
            console.warn("Planner config parse failed", e);
        }
    }

    const form = document.querySelector("[data-planner-form]");
    const resultsEl = document.querySelector("[data-planner-results]");
    const statusEl = document.querySelector("[data-planner-status]");

    const renderRecommendations = (items) => {
        if (!resultsEl) return;
        if (!items || !items.length) {
            resultsEl.innerHTML = '<div class="ps-empty">Пока нет рекомендаций. Запросите план.</div>';
            return;
        }
        resultsEl.innerHTML = items
            .map(
                (item) => `
                <article class="planner-reco ps-animate-fade-up">
                    <div class="ps-card-title">${item.lot_name || "Парковка"}</div>
                    <p class="planner-reco__meta">
                        <span>${item.address || "Адрес уточняется"}</span>
                        <span>~${item.distance_km} км пешком</span>
                        <span>Загруженность: ${(item.predicted_occupancy * 100).toFixed(0)}%</span>
                    </p>
                    <p class="ps-hint">EV: ${item.has_ev_charging ? "да" : "нет"} · Крытое: ${item.is_covered ? "да" : "нет"} · От ${item.hourly_price} ₽/ч</p>
                </article>
            `
            )
            .join("");
    };

    const setStatus = (msg) => {
        if (statusEl) {
            statusEl.textContent = msg || "";
        }
    };

    if (form) {
        form.addEventListener("submit", async (e) => {
            e.preventDefault();
            const data = new FormData(form);
            const payload = {
                destination_lat: parseFloat(data.get("destination_lat")),
                destination_lon: parseFloat(data.get("destination_lon")),
                arrival_at: data.get("arrival_at") || null,
                requires_ev_charging: data.get("requires_ev_charging") === "on",
                requires_covered: data.get("requires_covered") === "on",
                max_price_level: parseInt(data.get("max_price_level") || "0", 10),
            };
            setStatus("Загружаем рекомендации…");
            try {
                const resp = await fetch(endpoints.plan_endpoint, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    credentials: "include",
                    body: JSON.stringify(payload),
                });
                const json = await resp.json();
                renderRecommendations(json.recommendations || []);
                setStatus("");
            } catch (err) {
                console.error(err);
                setStatus("Не удалось получить рекомендации. Попробуйте позже.");
            }
        });
    }

    renderRecommendations([]);
})();
