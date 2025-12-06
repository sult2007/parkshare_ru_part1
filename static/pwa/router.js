import { subscribe } from './state-store.js';

const routes = {
  map: '[data-route="map"]',
  list: '[data-route="list"]',
  dashboard: '[data-route="dashboard"]',
};

export function initRouter() {
  document.addEventListener('click', (event) => {
    const link = event.target.closest('[data-route-link]');
    if (!link) return;
    const target = link.getAttribute('data-route-link');
    if (!target || !routes[target]) return;
    event.preventDefault();
    showRoute(target);
    history.pushState({ route: target }, '', `#${target}`);
  });

  window.addEventListener('popstate', (event) => {
    const route = event.state?.route || window.location.hash.replace('#', '') || 'map';
    showRoute(route);
  });

  const initial = window.location.hash.replace('#', '') || 'map';
  showRoute(initial);
}

function showRoute(name) {
  Object.entries(routes).forEach(([key, selector]) => {
    document.querySelectorAll(selector).forEach((node) => {
      node.hidden = key !== name;
      node.classList.toggle('is-active', key === name);
    });
  });
}

export function bindConnectionBanner() {
  const badge = document.querySelector('[data-connection-badge]');
  if (!badge) return;
  subscribe((state) => {
    badge.textContent = state.isOnline ? 'Онлайн' : 'Оффлайн режим';
    badge.classList.toggle('is-offline', !state.isOnline);
    badge.hidden = false;
  });
}
