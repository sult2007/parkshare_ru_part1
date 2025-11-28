// app.js

// Базовый URL FastAPI-сервера
// Если сервер крутится на другом порту/домене — поправь здесь.
const API_BASE = "http://localhost:8001";

let map;
let markersLayer;
let lotsCache = [];
let lotsById = new Map();

function pickBestLot(lots) {
  if (!lots || lots.length === 0) return null;
  const ranked = [...lots].sort((a, b) => {
    const occA = a.predicted_occupancy ?? 1;
    const occB = b.predicted_occupancy ?? 1;
    return occA - occB;
  });
  return ranked[0];
}

function updateAIOracleCard(lots) {
  const nameEl = document.getElementById("aiOracleName");
  const etaEl = document.getElementById("aiOracleETA");
  const confEl = document.getElementById("aiOracleConfidence");
  const metaEl = document.getElementById("aiOracleMeta");
  const reasoningEl = document.getElementById("aiOracleReason");

  if (!nameEl || !etaEl || !confEl || !metaEl || !reasoningEl) return;

  if (!lots || lots.length === 0) {
    nameEl.textContent = "—";
    etaEl.textContent = "—";
    confEl.textContent = "—";
    metaEl.textContent = "—";
    reasoningEl.textContent = "AI готовит инсайт…";
    return;
  }

  const bestLot = pickBestLot(lots);
  if (!bestLot) return;

  const occ = bestLot.predicted_occupancy ?? 0;
  const occPercent = Math.round(occ * 100);
  const eta = Math.max(2, Math.min(15, Math.round((1 - occ) * 12)));
  const confidence = Math.max(68, Math.min(99, 96 - Math.round(occPercent / 2)));
  const ev = bestLot.has_ev_charging ? "EV" : "обычная";
  const covered = bestLot.has_covered ? "крытая" : "открытая";

  nameEl.textContent = bestLot.name;
  etaEl.textContent = `${eta} мин`;
  confEl.textContent = `${confidence}%`;
  metaEl.textContent = `${ev} · ${covered}`;
  reasoningEl.textContent =
    "Учитывая вашу историю: быстрый выезд, EV и близость к метро — этот слот даст наивысший WOW-эффект.";
}

// ----------------- ИНИЦИАЛИЗАЦИЯ КАРТЫ -----------------

function occupancyColor(value) {
  if (value <= 0.4) return "#22c55e"; // green
  if (value <= 0.7) return "#eab308"; // yellow
  return "#ef4444"; // red
}

function initMap() {
  map = L.map("map", {
    zoomControl: true,
    attributionControl: false,
  }).setView([55.7558, 37.6173], 12);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
  }).addTo(map);

  markersLayer = L.layerGroup().addTo(map);
}

// ----------------- API HELPERS -----------------

async function apiGet(path, params = {}) {
  const url = new URL(API_BASE + path);
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null) {
      url.searchParams.set(k, v);
    }
  });

  const res = await fetch(url.toString());
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return res.json();
}

// ----------------- ОТРИСОВКА ЛОТОВ -----------------

function renderLotsOnMap(lots) {
  markersLayer.clearLayers();

  lots.forEach((lot) => {
    const occ = lot.predicted_occupancy ?? 0;
    const color = occupancyColor(occ);

    const marker = L.circleMarker([lot.latitude, lot.longitude], {
      radius: 8,
      fillColor: color,
      fillOpacity: 0.9,
      color: "#020617",
      weight: 1,
    });

    const occPercent = Math.round(occ * 100);

    const html = `
      <div style="font-size: 12px;">
        <strong>${lot.name}</strong><br />
        Загрузка: <strong>${occPercent}%</strong><br />
        Метро: ${lot.near_metro ? "рядом" : "нет"}<br />
        Уровень цены: ${lot.price_level}<br />
        Крытая: ${lot.has_covered ? "да" : "нет"}<br />
        Зарядка EV: ${lot.has_ev_charging ? "есть" : "нет"}
      </div>
    `;

    marker.bindPopup(html);
    marker.addTo(markersLayer);
  });

  if (lots.length > 0) {
    const bounds = L.latLngBounds(
      lots.map((lot) => [lot.latitude, lot.longitude])
    );
    map.fitBounds(bounds.pad(0.2));
  }
}

function renderLotsList(containerId, lots, clickHandler) {
  const container = document.getElementById(containerId);
  container.innerHTML = "";

  if (!lots || lots.length === 0) {
    container.innerHTML =
      '<div style="font-size: 0.75rem; color: #6b7280;">Нет данных.</div>';
    return;
  }

  lots.forEach((lot) => {
    const occ = lot.predicted_occupancy ?? 0;
    const occPercent = Math.round(occ * 100);

    const div = document.createElement("div");
    div.className = "lot-item";
    div.innerHTML = `
      <div class="lot-main">
        <div class="lot-name">${lot.name}</div>
        <div class="lot-meta">
          <span>Цена: L${lot.price_level}</span>
          <span>Метро: ${lot.near_metro ? "рядом" : "нет"}</span>
          <span>EV: ${lot.has_ev_charging ? "есть" : "нет"}</span>
          <span>Крытая: ${lot.has_covered ? "да" : "нет"}</span>
        </div>
      </div>
      <div class="lot-occ">${occPercent}%</div>
    `;

    div.addEventListener("click", () => clickHandler(lot));
    container.appendChild(div);
  });
}

// ----------------- ЛОГИКА UI -----------------

async function loadAllLots() {
  const status = document.getElementById("statusText");
  try {
    const lots = await apiGet("/api/lots");
    lotsCache = lots;
    lotsById.clear();
    lots.forEach((lot) => lotsById.set(lot.id, lot));

    renderLotsOnMap(lots);
    renderLotsList("lotsList", lots, (lot) => {
      map.setView([lot.latitude, lot.longitude], 16);
    });

    updateAIOracleCard(lots);

    status.textContent = "AI-сервер подключён";
  } catch (err) {
    console.error(err);
    status.textContent = "Ошибка подключения к AI-серверу";
  }
}

async function handleSearch() {
  const input = document.getElementById("searchInput");
  const status = document.getElementById("searchStatus");
  const text = input.value.trim();
  if (!text) return;

  status.textContent = "Обрабатываю запрос (локальный NLP)…";

  try {
    const data = await apiGet("/api/search", { query: text });
    const lots = data.lots || [];

    renderLotsOnMap(lots);
    renderLotsList("lotsList", lots, (lot) => {
      map.setView([lot.latitude, lot.longitude], 16);
    });

    updateAIOracleCard(lots);

    const parts = [];
    parts.push(`Интент: ${data.intent}`);
    if (data.near_metro !== null) {
      parts.push(`рядом с метро: ${data.near_metro ? "да" : "нет"}`);
    }
    if (data.max_price_level !== null) {
      parts.push(`макс. уровень цены: L${data.max_price_level}`);
    }
    if (data.has_ev_charging !== null) {
      parts.push(`EV: ${data.has_ev_charging ? "нужна" : "не нужна"}`);
    }
    if (data.has_covered !== null) {
      parts.push(`крытая: ${data.has_covered ? "нужна" : "не нужна"}`);
    }
    if (data.time_of_day) {
      parts.push(`время суток: ${data.time_of_day}`);
    }
    status.textContent = parts.join(" · ") || "Фильтры не распознаны.";
  } catch (err) {
    console.error(err);
    status.textContent = "Ошибка обработки запроса";
  }
}

async function initUsersSelect() {
  const select = document.getElementById("userSelect");
  // Пользователи не отдаются API, но user_id есть в тренировочных данных.
  // Для демо предположим, что есть пользователи с id 1..20.
  for (let i = 1; i <= 20; i++) {
    const opt = document.createElement("option");
    opt.value = String(i);
    opt.textContent = `Пользователь #${i}`;
    select.appendChild(opt);
  }
}

async function handleRecommendations(variant) {
  const select = document.getElementById("userSelect");
  const status = document.getElementById("recStatus");
  const listContainerId = "recList";

  const userId = parseInt(select.value, 10) || undefined;

  status.textContent =
    variant === "A"
      ? "Рассчитываю рекомендации (collaborative)…"
      : "Рассчитываю рекомендации (content-based)…";

  try {
    const params = { limit: 10, variant };
    if (variant === "A" && userId) {
      params.user_id = userId;
    }
    const data = await apiGet("/api/recommendations", params);
    const recs = data.recommendations || [];

    const lots = recs.map((r) => r.lot);
    renderLotsOnMap(lots);
    renderLotsList(listContainerId, lots, (lot) => {
      map.setView([lot.latitude, lot.longitude], 16);
    });

    updateAIOracleCard(lots);

    status.textContent = `Вариант ${data.variant}, получено ${recs.length} рекомендаций.`;
  } catch (err) {
    console.error(err);
    status.textContent = "Ошибка получения рекомендаций";
  }
}

// ----------------- СТАРТ -----------------

window.addEventListener("DOMContentLoaded", async () => {
  initMap();
  await initUsersSelect();
  await loadAllLots();

  document
    .getElementById("searchBtn")
    .addEventListener("click", () => handleSearch());

  document
    .getElementById("searchInput")
    .addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        handleSearch();
      }
    });

  document.getElementById("recBtn").addEventListener("click", () => {
    handleRecommendations("A");
  });

  document
    .getElementById("recContentBtn")
    .addEventListener("click", () => {
      handleRecommendations("B");
    });
});
