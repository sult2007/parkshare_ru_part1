// static/js/map.js
// Обновлённый модуль карты ParkShare: кастомные тёмные слои Яндекс.Карт,
// анимированные контролы, адаптивные балуны и мобильные шторки.

(function () {
    "use strict";

    function qs(sel, ctx) { return (ctx || document).querySelector(sel); }
    function qsa(sel, ctx) { return Array.prototype.slice.call((ctx || document).querySelectorAll(sel)); }

    var MAP_CONFIG = window.PARKSHARE_MAP_PROVIDER || {};
    var priceRange = [0, 1500];
    var prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
    var dataTheme = document.documentElement.getAttribute("data-theme");
    var storedTheme = null;
    try { storedTheme = localStorage.getItem("ps-theme"); } catch (_) {}
    var isNight = (dataTheme || storedTheme || (prefersDark ? "dark" : "light")) === "dark";
    var lastFeatures = [];
    var featureIndex = {};
    var selectionSubscribers = [];
    var activeSpotId = null;
    var userLocation = null;

    function distanceKm(a, b) {
        if (!a || !b) return 0;
        var rad = Math.PI / 180;
        var lat1 = a[0] * rad, lat2 = b[0] * rad, lon1 = a[1] * rad, lon2 = b[1] * rad;
        var dlat = lat2 - lat1, dlon = lon2 - lon1;
        var h = Math.sin(dlat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dlon / 2) ** 2;
        return 6371 * 2 * Math.atan2(Math.sqrt(h), Math.sqrt(1 - h));
    }

    function applyMapTheme(theme, provider, container, silent) {
        var mode = theme === "dark" ? "dark" : "light";
        var mapEl = container || qs("#map");
        if (mapEl) {
            mapEl.classList.toggle("ps-map--dark", mode === "dark");
            mapEl.classList.toggle("ps-map--light", mode === "light");
        }

        if (!silent) {
            if (window.ThemeController && typeof window.ThemeController.setTheme === "function") {
                window.ThemeController.setTheme(mode);
            } else {
                document.documentElement.setAttribute("data-theme", mode);
                try { localStorage.setItem("ps-theme", mode); } catch (_) {}
            }
        }

        var btn = qs("[data-map-theme]");
        if (btn) {
            var isDark = mode === "dark";
            btn.setAttribute("aria-pressed", String(isDark));
            btn.classList.toggle("is-active", isDark);
        }

        isNight = mode === "dark";
        if (provider && provider.toggleTheme) provider.toggleTheme(isNight ? "night" : "day");
    }

    // ---------- Базовый интерфейс ----------
    function BaseMapProvider(options) { this.options = options || {}; }
    BaseMapProvider.prototype.init = function () {};
    BaseMapProvider.prototype.setFeatures = function () {};
    BaseMapProvider.prototype.setLoading = function () {};
    BaseMapProvider.prototype.drawRouteTo = function () {};
    BaseMapProvider.prototype.focusOn = function () {};
    BaseMapProvider.prototype.onInteraction = function () {};
    BaseMapProvider.prototype.toggleTheme = function () {};
    BaseMapProvider.prototype.showUserLocation = function () {};
    BaseMapProvider.prototype.setView = function () {};

    // ---------- Leaflet fallback ----------
    function LeafletMapProvider(options) {
        BaseMapProvider.call(this, options);
        this._map = null;
        this._markersLayer = null;
        this._tileLayers = {};
        this._currentTile = "day";
        this._activeRoute = null;
        this._highlight = null;
        this._markers = {};
        this._activeMarker = null;
    }
    LeafletMapProvider.prototype = Object.create(BaseMapProvider.prototype);

    LeafletMapProvider.prototype.init = function (container, center, zoom) {
        if (typeof L === "undefined") return;
        this._map = L.map(container, { center: center, zoom: zoom, scrollWheelZoom: false });
        this._tileLayers.day = this._createBaseLayer("light");
        this._tileLayers.night = this._createBaseLayer("dark");
        this._tileLayers.day.addTo(this._map);
        this._markersLayer = L.markerClusterGroup({ chunkedLoading: true, spiderfyOnMaxZoom: true }).addTo(this._map);
    };

    LeafletMapProvider.prototype._createBaseLayer = function (mode) {
        var url = mode === "dark"
            ? "https://tiles.stadiamaps.com/tiles/alidade_smooth_dark/{z}/{x}/{y}{r}.png"
            : "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png";
        return L.tileLayer(url, { maxZoom: 20 });
    };

    LeafletMapProvider.prototype.setFeatures = function (fc) {
        if (!this._map || !this._markersLayer) return;
        var layer = this._markersLayer;
        layer.clearLayers();
        this._markers = {};
        var bounds = [];
        (fc.features || []).forEach(function (feature) {
            var coords = feature.geometry && feature.geometry.coordinates;
            if (!coords) return;
            var lng = coords[0], lat = coords[1];
            var p = feature.properties || {};
            var spotId = String(p.spot_id || feature.id || p.id || "");
            var stress = p.stress_index || 0;
            var color = stress >= 0.8 ? "#ef4444" : stress >= 0.6 ? "#f59e0b" : "#0ea5e9";
            var isHot = p.hourly_price && stress < 0.6;
            var freeLabel = (p.free_places === 0 || p.free_places) ? p.free_places : null;
            var label = freeLabel != null ? String(freeLabel) : "P";
            var textColor = (color === "#ef4444" || color === "#f59e0b") ? "#ffffff" : "#04121f";
            var markerHtml = [
                "<div class='ps-map-marker" + (isHot ? " ps-map-marker--hot" : "") + "'>",
                "  <div class='ps-map-marker__halo'></div>",
                "  <div class='ps-map-marker__body' style='background:" + color + "; color:" + textColor + "'>",
                "    <span class='ps-map-marker__value'>" + label + "</span>",
                "  </div>",
                "</div>"
            ].join("");
            var marker = L.marker([lat, lng], {
                icon: L.divIcon({
                    className: "ps-map-marker-wrap",
                    html: markerHtml,
                    iconSize: [46, 46],
                    iconAnchor: [23, 23],
                })
            });
            marker.bindPopup(buildPopupHtml(p, color), { className: "ps-map-popup-card" });
            marker.addTo(layer);
            this._markers[spotId] = marker;
            marker.on("click", function () {
                notifySelection(spotId, { lat: lat, lng: lng });
            });
            bounds.push([lat, lng]);
        }, this);
        lastFeatures = fc.features || [];
        if (bounds.length) this._map.fitBounds(bounds, { padding: [72, 72] });
    };

    LeafletMapProvider.prototype.toggleTheme = function (mode) {
        if (!this._map) return;
        var next = mode === "night" ? "night" : mode === "day" ? "day" : (this._currentTile === "day" ? "night" : "day");
        this._map.removeLayer(this._tileLayers[this._currentTile]);
        this._tileLayers[next].addTo(this._map);
        this._currentTile = next;
    };

    LeafletMapProvider.prototype.setLoading = function (isLoading) {
        var el = qs("[data-map-loading]");
        if (el) el.style.display = isLoading ? "flex" : "none";
    };

    LeafletMapProvider.prototype.drawRouteTo = function (target, fromCoords, onHint) {
        if (!this._map || !target) return;
        if (this._activeRoute) this._activeRoute.remove();
        var origin = fromCoords ? L.latLng(fromCoords.lat, fromCoords.lng) : this._map.getCenter();
        var dest = target.lat != null ? L.latLng(target.lat, target.lng) : L.latLng(target[0], target[1]);
        this._activeRoute = L.polyline([origin, dest], { color: "#22c55e", weight: 4, opacity: 0.85 }).addTo(this._map);
        var km = distanceKm([origin.lat, origin.lng], [dest.lat, dest.lng]);
        if (onHint) onHint(km);
        this._map.fitBounds(this._activeRoute.getBounds(), { padding: [56, 56] });
    };

    LeafletMapProvider.prototype.focusOn = function (lat, lng) {
        if (!this._map) return;
        if (this._highlight) this._highlight.remove();
        this._highlight = L.circleMarker([lat, lng], { color: "#fbbf24", radius: 14, weight: 3 }).addTo(this._map);
        this._map.panTo([lat, lng], { animate: true, duration: 0.35, easeLinearity: 0.2 });
    };

    LeafletMapProvider.prototype.onInteraction = function (start, end) {
        if (!this._map) return;
        if (start) this._map.on("movestart zoomstart dragstart", start);
        if (end) this._map.on("moveend zoomend dragend", end);
    };

    LeafletMapProvider.prototype.showUserLocation = function (lat, lng) {
        if (!this._map) return;
        var radius = L.circle([lat, lng], { radius: 450, color: "#22c55e", weight: 2, fillOpacity: 0.12 }).addTo(this._map);
        radius.bringToBack();
    };

    LeafletMapProvider.prototype.setView = function (lat, lng, zoom) {
        if (!this._map) return;
        this._map.setView([lat, lng], zoom || this._map.getZoom());
    };

    LeafletMapProvider.prototype.setActiveMarkerById = function (spotId) {
        if (!this._markers) return;
        if (this._activeMarker && this._activeMarker._icon) {
            this._activeMarker._icon.classList.remove("is-active");
        }
        var marker = this._markers[spotId];
        if (marker && marker._icon) {
            marker._icon.classList.add("is-active");
            this._activeMarker = marker;
        }
    };

    // ---------- Yandex Maps ----------
    function YandexMapProvider(options) {
        BaseMapProvider.call(this, options);
        this._map = null;
        this._clusterer = null;
        this._activeRoute = null;
        this._highlight = null;
        this._ready = false;
        this._theme = options.theme || "day";
        this._mapTypesReady = false;
        this._heatLayer = null;
        this._markers = {};
        this._activePlacemark = null;
    }
    YandexMapProvider.prototype = Object.create(BaseMapProvider.prototype);

    YandexMapProvider.prototype._ensureMapTypes = function () {
        if (this._mapTypesReady || typeof ymaps === "undefined") return;
        var lightLayer = function () {
            return new ymaps.Layer("https://core-renderer-tiles.maps.yandex.net/tiles?l=map&theme=light&x=%x&y=%y&z=%z&scale=1&lang=ru_RU", { projection: ymaps.projection.sphericalMercator });
        };
        var darkLayer = function () {
            return new ymaps.Layer("https://core-renderer-tiles.maps.yandex.net/tiles?l=map&theme=dark&x=%x&y=%y&z=%z&scale=1&lang=ru_RU", { projection: ymaps.projection.sphericalMercator });
        };
        ymaps.mapType.storage.add("ps#light", new ymaps.MapType("ps#light", [lightLayer]));
        ymaps.mapType.storage.add("ps#dark", new ymaps.MapType("ps#dark", [darkLayer]));
        this._mapTypesReady = true;
    };

    YandexMapProvider.prototype._ensureLayouts = function () {
        if (this._markerLayout && this._clusterIconLayout && this._clusterBalloonLayout) return;

        var markerTpl = [
            "<div class='ps-map-marker {{properties.markerActive}} {{properties.markerHot ? \"ps-map-marker--hot\" : ''}}'>",
            "  <div class='ps-map-marker__halo'></div>",
            "  <div class='ps-map-marker__body' style='background: {{properties.markerColor}}; color: {{properties.markerTextColor}}'>",
            "    <span class='ps-map-marker__value'>{{properties.markerLabel}}</span>",
            "  </div>",
            "</div>"
        ].join("");
        this._markerLayout = ymaps.templateLayoutFactory.createClass(markerTpl, {
            getShape: function () { return new ymaps.shape.Circle(new ymaps.geometry.pixel.Point([28, 28]), 26); },
        });

        var clusterTpl = "<div class='ps-map-cluster'><div class='ps-map-cluster__count'>{{properties.geoObjects.length}}</div></div>";
        this._clusterIconLayout = ymaps.templateLayoutFactory.createClass(clusterTpl, {
            build: function () {
                this.constructor.superclass.build.call(this);
                var node = this.getParentElement() && this.getParentElement().firstChild;
                if (!node) return;
                var geoObjects = (this.getData().properties.get("geoObjects") || []).map(function (g) { return g.properties.getAll(); });
                var avg = geoObjects.reduce(function (acc, p) { return acc + (p.stress_index || 0); }, 0) / (geoObjects.length || 1);
                node.classList.add(avg >= 0.75 ? "ps-map-cluster--danger" : avg >= 0.45 ? "ps-map-cluster--warn" : "ps-map-cluster--ok");
            }
        });

        this._clusterBalloonLayout = ymaps.templateLayoutFactory.createClass("<div class='ps-map-popup ps-map-popup--list'></div>", {
            build: function () {
                this.constructor.superclass.build.call(this);
                var container = this.getParentElement() && this.getParentElement().querySelector(".ps-map-popup--list");
                if (!container) return;
                var items = this.getData().properties.get("geoObjects") || [];
                container.innerHTML = items.map(function (g) { return g.properties.get("balloonContent") || ""; }).join("");
            }
        });
    };

    YandexMapProvider.prototype.init = function (container, center, zoom) {
        var self = this;
        if (typeof ymaps === "undefined") return;
        this._container = container;
        ymaps.ready(function () {
            self._ensureMapTypes();
            self._map = new ymaps.Map(container, { center: center, zoom: zoom, type: isNight ? "ps#dark" : "ps#light", controls: ["zoomControl"] });
            self._map.behaviors.disable("scrollZoom");
            self._ensureLayouts();
            self._clusterer = new ymaps.Clusterer({
                clusterIconLayout: self._clusterIconLayout,
                clusterIconOffset: [-28, -28],
                clusterIconShape: { type: "Circle", coordinates: [28, 28], radius: 28 },
                clusterNumbers: [50],
                groupByCoordinates: false,
                clusterDisableClickZoom: true,
                clusterBalloonContentLayout: self._clusterBalloonLayout,
                clusterBalloonPanelMaxMapArea: 0,
            });
            self._map.geoObjects.add(self._clusterer);
            self._ready = true;
            if (self._pending) { self.setFeatures(self._pending); self._pending = null; }
        });
    };

    YandexMapProvider.prototype._renderHeat = function (features) {
        if (!this._map) return;
        if (this._heatLayer) { this._map.geoObjects.remove(this._heatLayer); }
        var collection = new ymaps.GeoObjectCollection({}, { opacity: 0.35, fillOpacity: 0.18, strokeWidth: 0 });
        features.slice(0, 40).forEach(function (f) {
            var coords = f.geometry && f.geometry.coordinates; if (!coords) return;
            var stress = f.properties && (f.properties.stress_index || 0);
            if (!stress) return;
            var radius = 250 + stress * 1200;
            var color = stress > 0.75 ? "rgba(239,68,68,0.4)" : stress > 0.5 ? "rgba(245,158,11,0.4)" : "rgba(14,165,233,0.35)";
            collection.add(new ymaps.Circle([[coords[1], coords[0]], radius], {}, { fillColor: color }));
        });
        this._heatLayer = collection;
        this._map.geoObjects.add(collection);
    };

    YandexMapProvider.prototype.setFeatures = function (fc) {
        if (typeof ymaps === "undefined") return;
        if (!this._map || !this._ready) { this._pending = fc; return; }
        this._ensureLayouts();
        this._clusterer.removeAll();
        this._markers = {};
        var bounds = [];
        var features = fc.features || [];
        var prices = features.map(function (f) { return f.properties && f.properties.hourly_price; }).filter(function (v) { return typeof v === "number"; });
        var avgPrice = prices.length ? prices.reduce(function (a, b) { return a + b; }, 0) / prices.length : null;
        var self = this;

        features.forEach(function (feature) {
            var coords = feature.geometry && feature.geometry.coordinates; if (!coords) return;
            var lng = coords[0], lat = coords[1];
            var p = feature.properties || {};
            var spotId = String(p.spot_id || feature.id || p.id || "");
            var stress = p.stress_index || 0;
            var allowAi = !!p.allow_dynamic_pricing;
            var color = allowAi ? "#22c55e" : "#0ea5e9";
            if (stress > 0.7) color = "#ef4444"; else if (stress > 0.45) color = "#f59e0b";
            var isHot = avgPrice && p.hourly_price && p.hourly_price < avgPrice * 0.75;
            var freeLabel = (p.free_places === 0 || p.free_places) ? p.free_places : null;
            var label = freeLabel != null ? String(freeLabel) : "P";
            var textColor = (color === "#ef4444" || color === "#f59e0b") ? "#ffffff" : "#04121f";
            var popupHtml = buildPopupHtml(p, color);
            var placemark = new ymaps.Placemark([lat, lng], {
                hintContent: (p.lot_name || "") + (p.name ? " — " + p.name : ""),
                balloonContent: popupHtml,
                markerColor: color,
                markerLabel: label,
                markerHot: isHot,
                markerTextColor: textColor,
                stress_index: stress,
            }, {
                iconLayout: self._markerLayout,
                iconOffset: [-26, -26],
                hideIconOnBalloonOpen: false,
                balloonPanelMaxMapArea: 0,
            });
            placemark.events.add("balloonopen", function () {
                self._setActive(placemark);
                notifySelection(spotId, { lat: lat, lng: lng });
                self._map.panTo([lat, lng], { flying: true, duration: 400 });
            });
            placemark.events.add("click", function () {
                self._setActive(placemark);
                notifySelection(spotId, { lat: lat, lng: lng });
            });
            placemark.events.add("balloonclose", function () { self._setActive(null); });
            self._clusterer.add(placemark);
            self._markers[spotId] = placemark;
            bounds.push([lat, lng]);
        });

        if (bounds.length) this._map.setBounds(bounds, { checkZoomRange: true, zoomMargin: 48 });
        this._renderHeat(features);
    };

    YandexMapProvider.prototype._setActive = function (placemark) {
        if (this._activePlacemark && this._activePlacemark !== placemark) {
            this._activePlacemark.properties.set("markerActive", "");
            this._activePlacemark.options.unset("zIndex");
        }
        this._activePlacemark = placemark;
        if (placemark) { placemark.properties.set("markerActive", "ps-map-marker--active"); placemark.options.set("zIndex", 2200); }
    };

    YandexMapProvider.prototype.setActiveMarkerById = function (spotId) {
        if (!this._markers) return;
        var target = this._markers[spotId];
        if (target) {
            this._setActive(target);
        }
    };

    YandexMapProvider.prototype.toggleTheme = function (mode) {
        this._theme = mode || this._theme;
        if (!this._map || !this._ready) return;
        this._ensureMapTypes();
        this._map.setType(this._theme === "night" ? "ps#dark" : "ps#light");
    };

    YandexMapProvider.prototype.setLoading = LeafletMapProvider.prototype.setLoading;

    YandexMapProvider.prototype.drawRouteTo = function (target, fromCoords, onHint) {
        if (!this._map || !target) return;
        if (this._activeRoute) this._map.geoObjects.remove(this._activeRoute);
        var origin = fromCoords ? [fromCoords.lat, fromCoords.lng] : this._map.getCenter();
        var dest = target.lat != null ? [target.lat, target.lng] : target;
        this._activeRoute = new ymaps.Polyline([origin, dest], {}, { strokeColor: "#22c55e", strokeWidth: 4, opacity: 0.82 });
        this._map.geoObjects.add(this._activeRoute);
        var km = distanceKm(origin, dest);
        if (onHint) onHint(km);
        this._map.setBounds(this._activeRoute.geometry.getBounds(), { checkZoomRange: true, zoomMargin: 48 });
    };

    YandexMapProvider.prototype.focusOn = function (lat, lng) {
        if (!this._map || !this._ready) return;
        if (this._highlight) this._map.geoObjects.remove(this._highlight);
        this._highlight = new ymaps.Circle([[lat, lng], 120], {}, { strokeColor: "#fbbf24", strokeOpacity: 0.9, strokeWidth: 3, fillColor: "rgba(251,191,36,0.18)" });
        this._map.geoObjects.add(this._highlight);
        this._map.setCenter([lat, lng], 15, { duration: 300 });
    };

    YandexMapProvider.prototype.onInteraction = function (start, end) {
        var self = this;
        if (!this._map || !this._ready) {
            if (typeof ymaps !== "undefined") ymaps.ready(function () { self.onInteraction(start, end); });
            return;
        }
        ["actionbegin", "wheel", "mousedown", "touchstart"].forEach(function (ev) { if (start) self._map.events.add(ev, start); });
        if (end) self._map.events.add("actionend", end);
    };

    YandexMapProvider.prototype.showUserLocation = function (lat, lng) {
        if (!this._map || !this._ready) return;
        if (this._userMarker) this._map.geoObjects.remove(this._userMarker);
        if (this._userRadius) this._map.geoObjects.remove(this._userRadius);
        this._userRadius = new ymaps.Circle([[lat, lng], 500], {}, { fillColor: "rgba(34,197,94,0.15)", strokeColor: "#22c55e", strokeOpacity: 0.65, strokeWidth: 2, zIndex: 1500 });
        this._userMarker = new ymaps.Placemark([lat, lng], {}, { preset: "islands#circleDotIcon", iconColor: "#16a34a", zIndex: 2000 });
        this._map.geoObjects.add(this._userRadius); this._map.geoObjects.add(this._userMarker);
    };

    YandexMapProvider.prototype.setView = function (lat, lng, zoom) {
        if (!this._map || !this._ready) return;
        this._map.setCenter([lat, lng], zoom || this._map.getZoom(), { duration: 300 });
    };

    // ---------- Helpers ----------
    function buildPopupHtml(props, color) {
        var badges = [];
        if (props.allow_dynamic_pricing) badges.push("<span class='ps-badge ps-badge--success'>AI‑тариф</span>");
        if (props.has_ev_charging) badges.push("<span class='ps-badge'>EV</span>");
        if (props.is_covered) badges.push("<span class='ps-badge'>Крытая</span>");
        if (props.is_24_7) badges.push("<span class='ps-badge'>24/7</span>");
        var occupancy = Math.min(100, Math.round((props.occupancy_7d || 0) * 100));
        var stressTone = occupancy > 80 ? "danger" : occupancy > 60 ? "warn" : "ok";
        var estimate = estimatePricing(props);
        return [
            "<div class='ps-map-popup ps-map-popup--" + stressTone + "'>",
            "  <header class='ps-map-popup-head'>",
            "    <div class='ps-map-popup-title'>" + (props.city || "") + (props.lot_name ? ", " + props.lot_name : "") + (props.name ? " — " + props.name : "") + "</div>",
            "    <div class='ps-map-popup-meta'>" + (props.address || "Адрес уточняется") + "</div>",
            "  </header>",
            "  <div class='ps-map-popup-price'>от <strong>" + (props.hourly_price || "?") + " ₽/час</strong><div class='ps-map-popup-meta'>~" + estimate.h3 + " ₽ за 3 часа · ~" + estimate.h24 + " ₽/сутки</div></div>",
            "  <div class='ps-map-popup-badges'>" + badges.join(" ") + "</div>",
            "  <div class='ps-map-popup-meter'><span style='width:" + occupancy + "%; background:" + color + "'></span><div class='ps-map-popup-meter-label'>загруженность " + occupancy + "%</div></div>",
            "  <div class='ps-map-popup-actions'>",
            "    <button class='ps-btn ps-btn-primary ps-btn-sm' data-spot-id='" + (props.spot_id || props.id || "") + "'>Забронировать</button>",
            "    <button class='ps-btn ps-btn-ghost ps-btn-sm' data-focus-spot='" + (props.spot_id || props.id || "") + "'>Маршрут</button>",
            "  </div>",
            "</div>"
        ].join("");
    }

    function registerSelectionHandler(fn) {
        selectionSubscribers.push(fn);
    }

    function notifySelection(spotId, coords) {
        activeSpotId = spotId;
        try {
            document.dispatchEvent(new CustomEvent("ps:spot-selection", { detail: { spotId: spotId, coords: coords } }));
        } catch (_) {}
        selectionSubscribers.forEach(function (fn) { fn(spotId, coords); });
    }

    function indexFeatures(fc) {
        featureIndex = {};
        (fc.features || []).forEach(function (f) {
            var p = f.properties || {};
            var id = String(p.spot_id || f.id || p.id || "");
            if (id) featureIndex[id] = f;
        });
    }

    function findFeature(id) {
        if (!id) return null;
        return featureIndex[id] || (lastFeatures || []).find(function (f) {
            var pid = f.properties && (f.properties.spot_id || f.properties.id);
            return String(pid || f.id || "") === String(id);
        }) || null;
    }

    function estimatePricing(props) {
        var hourly = Number(props.hourly_price) || 0;
        var nightly = Number(props.nightly_price) || 0;
        var daily = Number(props.daily_price) || 0;
        var oneHour = hourly || Math.max(nightly / 10, daily / 24, 0);
        var threeHours = hourly ? hourly * 3 : oneHour * 3;
        var day = daily || (hourly ? hourly * 12 : threeHours * 2.5);
        return {
            h1: Math.round(oneHour),
            h3: Math.round(threeHours),
            h24: Math.round(day)
        };
    }

    function buildStressHint(props) {
        var stress = props.stress_index || 0;
        var occupancy = props.occupancy_7d || 0;
        if (stress > 0.7 || occupancy > 0.75) {
            return "Сейчас высокая загруженность, лучше рассмотреть альтернативы.";
        }
        if (stress > 0.45 || occupancy > 0.55) {
            var uplift = Math.round(Math.max(stress, occupancy) * 30);
            return "В этом районе обычно дороже на ~" + (uplift || 10) + "%.";
        }
        return "Обычно свободно, бронируйте без ожидания.";
    }

    function createProvider() {
        var id = (MAP_CONFIG.key || MAP_CONFIG.id || "yandex").toLowerCase();
        var fallback = (MAP_CONFIG.fallback || "leaflet").toLowerCase();
        var center = MAP_CONFIG.default_center || [55.75, 37.61];
        var zoom = MAP_CONFIG.default_zoom || 12;
        var container = qs("#map");
        if (!container) return { provider: null, center: center, zoom: zoom };
        var hasYandex = typeof ymaps !== "undefined";
        var hasLeaflet = typeof L !== "undefined";
        var provider = null;
        var opts = Object.assign({}, MAP_CONFIG, { theme: isNight ? "night" : "day" });
        if (id === "yandex" && hasYandex) provider = new YandexMapProvider(opts);
        else if (id === "leaflet" && hasLeaflet) provider = new LeafletMapProvider(opts);
        else if (fallback === "yandex" && hasYandex) provider = new YandexMapProvider(opts);
        else if (hasLeaflet) provider = new LeafletMapProvider(opts);
        if (!provider) return { provider: null, center: center, zoom: zoom };
        provider.init(container, center, zoom);
        return { provider: provider, center: center, zoom: zoom };
    }

    function readFilters() {
        var form = qs("[data-map-filters]");
        if (!form) return {};
        var fd = new FormData(form);
        return {
            only_free: fd.get("only_free") === "on",
            ev: fd.get("ev") === "on",
            covered: fd.get("covered") === "on",
            is_24_7: fd.get("is_24_7") === "on",
            ai_recommended: fd.get("ai_recommended") === "on",
            min_price: priceRange[0],
            max_price: priceRange[1]
        };
    }

    function buildQuery(params) {
        var q = [];
        Object.keys(params).forEach(function (k) {
            var v = params[k];
            if (v === "" || v === null || typeof v === "undefined") return;
            if (typeof v === "boolean") v = v ? "true" : "false";
            q.push(encodeURIComponent(k) + "=" + encodeURIComponent(v));
        });
        return q.length ? "?" + q.join("&") : "";
    }

    function fetchFeatures(provider) {
        if (!provider) return;
        provider.setLoading(true);
        var url = "/api/parking/map/" + buildQuery(readFilters());
        return fetch(url, { headers: { "Accept": "application/json" } })
            .then(function (resp) { if (!resp.ok) throw new Error("Map API error"); return resp.json(); })
            .then(function (data) {
                provider.setFeatures(data);
                indexFeatures(data);
                lastFeatures = data.features || [];
                updateSpotsList(data); updateStats(data);
                try {
                    var minimal = (data.features || []).slice(0, 20).map(function (f) {
                        var p = f.properties || {};
                        return { title: (p.city || "") + (p.lot_name ? ", " + p.lot_name : ""), address: p.address || "", spot_id: p.spot_id || f.id };
                    });
                    localStorage.setItem("ps_offline_spots", JSON.stringify(minimal));
                } catch (_) {}
                try {
                    var pendingFocus = sessionStorage.getItem("ps_focus_spot");
                    if (pendingFocus) {
                        sessionStorage.removeItem("ps_focus_spot");
                        var coords = featureCoordsById(pendingFocus);
                        if (coords) { notifySelection(pendingFocus, coords); }
                    }
                } catch (_) {}
            })
            .catch(function (err) {
                if (window.ParkShare && window.ParkShare.handleApiError) {
                    window.ParkShare.handleApiError(err);
                }
            })
            .finally(function () { provider.setLoading(false); });
    }

    function updateStats(fc) {
        var features = fc.features || [];
        var prices = features.map(function (f) { return f.properties && f.properties.hourly_price; }).filter(function (p) { return typeof p === "number"; });
        var avgEls = qsa("[data-avg-price]"); var countEls = qsa("[data-spots-count]");
        countEls.forEach(function (el) { el.textContent = String(features.length); });
        if (!avgEls.length) return; if (!prices.length) { avgEls.forEach(function (el) { el.textContent = "—"; }); return; }
        var sum = prices.reduce(function (acc, p) { return acc + p; }, 0);
        var value = (Math.round((sum / prices.length) / 10) * 10) + " ₽/час";
        avgEls.forEach(function (el) { el.textContent = value; });
    }

    function updateSpotsList(fc) {
        var container = qs("[data-spots-list]"); if (!container) return;
        var features = fc.features || [];
        if (!features.length) { container.innerHTML = "<div class='ps-empty'><p>Подходящих мест пока нет. Попробуйте изменить фильтры.</p></div>"; return; }
        container.innerHTML = features.map(function (f) {
            var p = f.properties || {};
            var spotId = p.spot_id || f.id || "";
            var badge = p.allow_dynamic_pricing ? "<span class='ps-badge ps-badge--success'>AI‑тариф</span>" : "";
            var estimate = estimatePricing(p);
            var statusIcon = (p.status && p.status !== "active") ? "#ps-ic-forbidden" : (p.hourly_price ? "#ps-ic-paid" : "#ps-ic-allowed");
            var statusLabel = (p.status && p.status !== "active") ? "Ограничена" : (p.hourly_price ? "Платная" : "Разрешена");
            var pills = [
                "<span class='ps-pill ps-pill--accent'><svg class='ps-icon' viewBox='0 0 24 24'><use href='" + statusIcon + "'></use></svg>" + statusLabel + "</span>"
            ];
            if (p.has_ev_charging) pills.push("<span class='ps-pill ps-pill--success'><svg class='ps-icon' viewBox='0 0 24 24'><use href='#ps-ic-ev'></use></svg>EV</span>");
            if (p.is_covered) pills.push("<span class='ps-pill'><svg class='ps-icon' viewBox='0 0 24 24'><use href='#ps-ic-covered'></use></svg>Крытая</span>");
            if (p.is_24_7) pills.push("<span class='ps-pill'>24/7</span>");
            return [
                "<article class='ps-card ps-card--spot ps-animate-fade-up ps-animate-stagger' data-spot-card='" + spotId + "'>",
                "  <div class='ps-card-header'><div class='ps-card-title'>" + (p.city || "") + (p.lot_name ? ", " + p.lot_name : "") + (p.name ? " — " + p.name : "") + "</div>" + badge + "</div>",
                "  <div class='ps-card-body'>",
                "    <div class='ps-spot-meta'>" + pills.join("") + "</div>",
                "    <div class='ps-spot-price'>от " + (p.hourly_price || "?") + " ₽/час</div>",
                "    <div class='ps-spot-estimate'>Оценка: ~" + estimate.h3 + " ₽ за 3 часа · ~" + estimate.h24 + " ₽/сутки</div>",
                "    <div class='ps-card-line ps-card-line--muted'>" + (p.address || "Адрес будет уточнён") + "</div>",
                "    <div class='ps-card-line ps-card-line--muted'>" + buildStressHint(p) + "</div>",
                "  </div>",
                "</article>"
            ].join("");
        }).join("");
        if (activeSpotId) {
            setActiveCard(activeSpotId);
        }
    }

    function featureCoordsById(spotId) {
        var match = findFeature(spotId);
        if (match && match.geometry && match.geometry.coordinates) {
            return { lat: match.geometry.coordinates[1], lng: match.geometry.coordinates[0] };
        }
        return null;
    }

    function setActiveCard(spotId) {
        var idStr = String(spotId || "");
        qsa("[data-spot-card]").forEach(function (card) {
            card.classList.toggle("is-active", card.getAttribute("data-spot-card") === idStr);
        });
        var activeCard = qs("[data-spot-card='" + idStr + "']");
        if (activeCard && typeof activeCard.scrollIntoView === "function") {
            activeCard.scrollIntoView({ behavior: "smooth", block: "center" });
        }
    }

    function initPriceSlider(onChange) {
        var slider = qs("[data-price-slider]"); var priceLabel = qs("[data-price-display]");
        if (!slider || typeof noUiSlider === "undefined") return;
        function render(values) { if (priceLabel) priceLabel.textContent = "Цена: от " + values[0] + " ₽ до " + values[1] + " ₽"; }
        noUiSlider.create(slider, { start: priceRange, connect: true, step: 50, range: { min: 0, max: 2000 } });
        slider.noUiSlider.on("update", function (values) { priceRange = values.map(function (v) { return Math.round(parseFloat(v)); }); render(priceRange); if (onChange) onChange(); });
        render(priceRange);
    }

    function updateRouteHint(km) {
        var hint = qs("[data-route-hint]"); if (!hint) return;
        if (!km) { hint.textContent = "Постройте мини-маршрут до выбранной точки."; return; }
        var timeMin = Math.max(2, Math.round(km / 0.4));
        hint.textContent = "~" + km.toFixed(1) + " км, " + timeMin + " мин пешком/авто.";
    }

    function drawRoute(provider, targetLatLng) {
        if (!provider || !targetLatLng || !provider.drawRouteTo) return;
        var from = userLocation ? { lat: userLocation.lat, lng: userLocation.lng } : null;
        provider.drawRouteTo({ lat: targetLatLng.lat || targetLatLng[0], lng: targetLatLng.lng || targetLatLng[1] }, from, function (km) { updateRouteHint(km); });
    }

    function initFloatingActions(provider) {
        var actions = qs(".ps-map-floating-actions"); if (!actions) return;
        var timer = null;
        function dim() { actions.classList.add("is-dimmed"); }
        function undim() { actions.classList.remove("is-dimmed"); startTimer(); }
        function startTimer() { clearTimeout(timer); timer = setTimeout(dim, 3000); }
        startTimer();
        qsa(".ps-map-action", actions).forEach(function (btn) {
            ["mouseenter", "touchstart", "click"].forEach(function (evt) { btn.addEventListener(evt, undim, { passive: true }); });
        });
        if (provider && provider.onInteraction) provider.onInteraction(undim, startTimer);
    }

    function initGeocode(provider) {
        var inputs = qsa("[data-geocode-input]");
        var primary = inputs.length ? inputs[0] : null;
        var submit = qs("[data-geocode-submit]"); var suggestions = qs("[data-geocode-suggestions]"); var timer = null;

        function syncInputs(value) {
            inputs.forEach(function (el) { el.value = value; });
        }

        function search(query) {
            if (typeof navigator !== "undefined" && navigator.onLine === false) {
                if (window.ParkShare && window.ParkShare.handleApiError) window.ParkShare.handleApiError({ message: "Нет подключения. Поиск недоступен оффлайн." });
                return;
            }
            if (!query) return;
            fetch("/api/geocode/?q=" + encodeURIComponent(query))
                .then(function (resp) { return resp.json(); })
                .then(function (data) {
                    var list = data.results || [];
                    if (suggestions) suggestions.innerHTML = list.map(function (item) { return "<button type='button' data-geocode-choice data-lat='" + item.lat + "' data-lng='" + item.lng + "'>" + item.title + "</button>"; }).join("");
                })
                .catch(function (err) {
                    if (window.ParkShare && window.ParkShare.handleApiError) window.ParkShare.handleApiError(err);
                });
        }

        inputs.forEach(function (input) {
            input.addEventListener("input", function () {
                clearTimeout(timer);
                var value = input.value.trim();
                timer = setTimeout(function () { search(value); }, 350);
            });
            input.addEventListener("keydown", function (evt) {
                if (evt.key === "Enter") { evt.preventDefault(); search(input.value.trim()); }
            });
        });

        if (submit) submit.addEventListener("click", function () { var value = primary ? primary.value : ""; search(value); });
        if (suggestions) {
            suggestions.addEventListener("click", function (e) {
                var btn = e.target.closest("[data-geocode-choice]"); if (!btn) return;
                var lat = parseFloat(btn.getAttribute("data-lat")); var lng = parseFloat(btn.getAttribute("data-lng"));
                suggestions.innerHTML = "";
                syncInputs(btn.textContent || "");
                if (provider && provider.setView) { provider.setView(lat, lng, 15); drawRoute(provider, { lat: lat, lng: lng }); }
            });
        }
    }

    document.addEventListener("DOMContentLoaded", function () {
        var mapContainer = qs("#map"); if (!mapContainer) return;
        var result = createProvider(); var provider = result.provider; if (!provider) return;
        initPriceSlider(function () { fetchFeatures(provider); });
        initGeocode(provider);
        fetchFeatures(provider);
        initFloatingActions(provider);
        applyMapTheme(isNight ? "dark" : "light", provider, mapContainer, true);

        var themeBtn = qs("[data-map-theme]");
        if (themeBtn) themeBtn.addEventListener("click", function () { var next = isNight ? "light" : "dark"; applyMapTheme(next, provider, mapContainer, false); });
        document.addEventListener("ps-theme-changed", function (e) {
            var next = e.detail && e.detail.theme;
            if (next) applyMapTheme(next, provider, mapContainer, true);
        });
        registerSelectionHandler(function (spotId, coords) {
            var point = coords || featureCoordsById(spotId);
            if (provider.setActiveMarkerById) provider.setActiveMarkerById(spotId);
            setActiveCard(spotId);
            if (point) {
                if (provider.focusOn) provider.focusOn(point.lat, point.lng);
                drawRoute(provider, point);
            }
        });

        var filtersForm = qs("[data-map-filters]");
        if (filtersForm) filtersForm.addEventListener("change", function () { fetchFeatures(provider); });

        qsa("[data-chip-toggle]").forEach(function (chip) {
            var input = qs("input", chip); if (!input) return; chip.classList.toggle("is-active", input.checked);
            chip.addEventListener("click", function (e) { if (e.target.tagName === "INPUT") return; input.checked = !input.checked; chip.classList.toggle("is-active", input.checked); input.dispatchEvent(new Event("change", { bubbles: true })); fetchFeatures(provider); });
        });

        var resetBtn = qs("[data-reset-filters]");
        if (resetBtn) {
            resetBtn.addEventListener("click", function () {
                resetBtn.classList.remove("ps-map-action--spinning");
                void resetBtn.offsetWidth;
                resetBtn.classList.add("ps-map-action--spinning");
                if (filtersForm) filtersForm.reset();
                priceRange = [0, 1500];
                var slider = qs("[data-price-slider]");
                if (slider && slider.noUiSlider) slider.noUiSlider.set(priceRange);
                qsa("[data-chip-toggle]").forEach(function (chip) { chip.classList.remove("is-active"); });
                fetchFeatures(provider);
            });
        }

function getCSRFToken() {
    var match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? match[1] : "";
}

function showToast(message, type) {
    var container = document.querySelector(".ps-toast-container");
    if (!container) return alert(message);
    var toast = document.createElement("div");
    toast.className = "ps-toast ps-toast--" + (type || "info");
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(function () { toast.remove(); }, 4200);
}

function createBooking(spotId) {
    var now = new Date();
    var end = new Date(now.getTime() + 60 * 60 * 1000);
    return fetch("/api/parking/bookings/", {
        method: "POST",
        credentials: "include",
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCSRFToken(),
        },
        body: JSON.stringify({
            spot: spotId,
            start_at: now.toISOString(),
            end_at: end.toISOString(),
            booking_type: "hourly",
        }),
    }).then(function (resp) {
        if (resp.status === 401 || resp.status === 403) {
            showToast("Войдите, чтобы бронировать места", "error");
            throw new Error("auth_required");
        }
        if (!resp.ok) {
            return resp.json().then(function (data) {
                var detail = typeof data === "object" ? JSON.stringify(data) : data;
                throw new Error(detail || "Ошибка бронирования");
            }).catch(function (err) { throw err; });
        }
        return resp.json();
    });
}

        qsa("[data-fill-location]").forEach(function (btn) {
            btn.addEventListener("click", function () {
                if (!navigator.geolocation) return; btn.classList.add("ps-map-action--pulse");
                navigator.geolocation.getCurrentPosition(function (pos) {
                    userLocation = { lat: pos.coords.latitude, lng: pos.coords.longitude };
                    if (provider.showUserLocation) provider.showUserLocation(userLocation.lat, userLocation.lng);
                    if (provider.setView) provider.setView(userLocation.lat, userLocation.lng, 14);
                    btn.classList.remove("ps-map-action--pulse");
                }, function () { btn.classList.remove("ps-map-action--pulse"); }, { timeout: 8000 });
            });
        });

        var mapPanel = qs("[data-map-panel]");
        if (mapPanel) {
            mapPanel.addEventListener("click", function (e) {
                var focusBtn = e.target.closest("[data-focus-spot]");
                var bookBtn = e.target.closest("[data-spot-id]");
                if (focusBtn) {
                    var id = focusBtn.getAttribute("data-focus-spot");
                    var coords = featureCoordsById(id);
                    notifySelection(id, coords);
                }
                if (bookBtn) {
                    var targetId = bookBtn.getAttribute("data-spot-id");
                    window.location.href = "/booking/confirm/?spot_id=" + encodeURIComponent(targetId);
                }
            });
        }

        qsa("[data-spots-list]").forEach(function (list) {
            list.addEventListener("click", function (e) {
                var card = e.target.closest("[data-spot-card]"); if (!card) return;
                var id = card.getAttribute("data-spot-card");
                var coords = featureCoordsById(id);
                notifySelection(id, coords);
            });
        });
    });
})();
