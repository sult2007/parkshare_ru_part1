(function () {
  'use strict';

  function qs(selector, scope) {
    return (scope || document).querySelector(selector);
  }
  function qsa(selector, scope) {
    return Array.prototype.slice.call((scope || document).querySelectorAll(selector));
  }

  const encoder = new TextEncoder();
  const STORAGE_PREFIX = 'ps_ai_chat_v2:';

  function storageKey(userId, fallbackKey) {
    return STORAGE_PREFIX + (userId || 'guest') + ':' + (fallbackKey || 'default');
  }

  function loadState(key) {
    try {
      const raw = localStorage.getItem(key);
      if (!raw) return null;
      return JSON.parse(raw);
    } catch (_) {
      return null;
    }
  }

  function saveState(key, state) {
    try {
      localStorage.setItem(key, JSON.stringify(state));
    } catch (_) {
      // ignore quota errors
    }
  }

  function now() {
    return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }

  function createWelcomeMessage() {
    return {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: 'Привет! Я ParkShare AI Concierge. Спроси про загрузку, цены, сценарии для гостей или подготовку персонала.',
      createdAt: Date.now()
    };
  }

  function renderMessage(message) {
    const bubble = document.createElement('div');
    bubble.className = 'ps-ai-bubble ' + (message.role === 'user' ? 'ps-ai-bubble--user' : 'ps-ai-bubble--assistant');
    bubble.dataset.messageId = message.id;

    const meta = document.createElement('div');
    meta.className = 'ps-ai-meta';
    meta.innerHTML = `<span class="ps-chip ${message.role === 'user' ? 'ps-chip--primary' : 'ps-chip--ghost'}">${message.role === 'user' ? 'Вы' : 'AI'}</span><span>${new Date(message.createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>`;
    bubble.appendChild(meta);

    const text = document.createElement('div');
    text.className = 'ps-ai-text';
    text.textContent = message.content || '...';
    bubble.appendChild(text);

    if (message.role === 'assistant') {
      const actions = document.createElement('div');
      actions.className = 'ps-ai-actions-row';
      const copyBtn = document.createElement('button');
      copyBtn.type = 'button';
      copyBtn.className = 'ps-btn ps-btn-ghost ps-btn-xs';
      copyBtn.textContent = 'Копировать';
      copyBtn.dataset.aiCopy = 'true';
      actions.appendChild(copyBtn);

      const regenBtn = document.createElement('button');
      regenBtn.type = 'button';
      regenBtn.className = 'ps-btn ps-btn-ghost ps-btn-xs';
      regenBtn.textContent = 'Перегенерировать';
      regenBtn.dataset.aiRegenerate = 'true';
      actions.appendChild(regenBtn);

      actions.hidden = !message.content;
      bubble.appendChild(actions);
    }

    return bubble;
  }

  function setupChat() {
    const chatRoot = qs('[data-ai-chat]');
    if (!chatRoot) return;

    const messagesEl = qs('[data-ai-messages]', chatRoot);
    const suggestionsEl = qs('[data-ai-suggestions]', chatRoot);
    const actionsEl = qs('[data-ai-actions]', chatRoot);
    const sessionsEl = qs('[data-ai-sessions]', chatRoot);
    const alertsEl = qs('[data-ai-alerts]', chatRoot);
    const textarea = qs('#ai-input', chatRoot);
    const sendBtn = qs('[data-ai-send]', chatRoot);
    const clearBtn = qs('[data-ai-clear]', chatRoot);
    const statusEl = qs('[data-ai-status]', chatRoot);
    const regenerateBtn = qs('[data-ai-regenerate]', chatRoot);
    const promptButtons = qsa('[data-ai-prompt]');
    const userId = document.body.getAttribute('data-user-id') || 'guest';
    const historyKey = chatRoot.getAttribute('data-ai-history-key') || 'default';
    const storage = storageKey(userId, historyKey);

    let state = loadState(storage) || { messages: [createWelcomeMessage()] };
    let isLoading = false;

    function persist() {
      saveState(storage, state);
    }

  function render() {
    messagesEl.innerHTML = '';
    state.messages.forEach(function (msg) {
      messagesEl.appendChild(renderMessage(msg));
    });
    messagesEl.scrollTop = messagesEl.scrollHeight;
    if (regenerateBtn) {
      const hasUserMessages = state.messages.some(function (m) { return m.role === 'user'; });
      regenerateBtn.hidden = !hasUserMessages || isLoading;
    }
    persist();
  }

    function setStatus(text, tone) {
      if (!statusEl) return;
      statusEl.textContent = text;
      statusEl.classList.toggle('is-error', tone === 'error');
    }

  function lastUserMessage() {
      for (let i = state.messages.length - 1; i >= 0; i--) {
        if (state.messages[i].role === 'user') return state.messages[i];
      }
      return null;
  }

    function addMessage(role, content) {
      const msg = { id: crypto.randomUUID(), role, content, createdAt: Date.now() };
      state.messages.push(msg);
      return msg;
    }

    function updateMessage(id, updater) {
      state.messages = state.messages.map(function (msg) {
        return msg.id === id ? updater(msg) : msg;
      });
    }

    function renderSuggestions(payload) {
      if (!suggestionsEl) return;
      const suggestions = (payload && payload.suggestions) || [];
      if (!suggestions.length) {
        suggestionsEl.hidden = true;
        suggestionsEl.innerHTML = "";
        return;
      }
      suggestionsEl.hidden = false;
      suggestionsEl.innerHTML = suggestions
        .map(function (item) {
          const tags = (item.tags || []).map(function (t) {
            return '<span class="ps-pill ps-pill--ghost">' + t + "</span>";
          }).join("");
          const price = item.price ? "от " + item.price + " ₽/час" : "Цена уточняется";
          return (
            '<article class="ps-card ps-card--spot ps-animate-fade-up" data-ai-suggestion="' + item.spot_id + '">' +
            '<div class="ps-card-header"><div class="ps-card-title">' + (item.title || "Парковка") + '</div></div>' +
            '<div class="ps-card-body">' +
            '<div class="ps-spot-meta">' + tags + '</div>' +
            '<div class="ps-spot-price">' + price + '</div>' +
            '<div class="ps-card-actions">' +
            '<button class="ps-btn ps-btn-secondary ps-btn-sm" data-ai-map="' + item.spot_id + '">Показать на карте</button>' +
            '<button class="ps-btn ps-btn-primary ps-btn-sm" data-ai-book="' + item.spot_id + '">Забронировать</button>' +
            '</div>' +
            '</div>' +
            '</article>'
          );
        })
        .join("");
    }

    function renderAlerts(list) {
      if (!alertsEl) return;
      if (!list || !list.length) {
        alertsEl.hidden = true;
        alertsEl.innerHTML = '';
        return;
      }
      alertsEl.hidden = false;
      alertsEl.innerHTML = list
        .map(function (alert) {
          var minutes = alert.minutes_left || 0;
          return (
            '<div class="ps-card ps-card--spot ps-animate-fade-up ps-card-line--muted">' +
            '<div class="ps-card-body">' +
            '<div class="ps-spot-price">Сессия заканчивается через ~' + minutes + ' мин.</div>' +
            '<div class="ps-card-line ps-card-line--muted">' + (alert.spot || '') + '</div>' +
            '</div>' +
            '</div>'
          );
        })
        .join('');
    }

    function renderActions(list) {
      if (!actionsEl) return;
      if (!list || !list.length) {
        actionsEl.hidden = true;
        actionsEl.innerHTML = '';
        return;
      }
      actionsEl.hidden = false;
      actionsEl.innerHTML = list
        .map(function (action, idx) {
          var key = action.booking_id || action.spot_id || idx;
          var label = action.type === 'booking_start' ? 'Начать парковку' : action.type === 'booking_extend' ? 'Продлить' : action.type === 'booking_stop' ? 'Завершить' : 'Действие';
          return (
            '<button class="ps-chip" data-ai-action="' + action.type + '" data-action-key="' + key + '" data-spot-id="' + (action.spot_id || '') + '" data-booking-id="' + (action.booking_id || '') + '" data-extend-min="' + (action.extend_minutes || '') + '" data-duration="' + (action.duration_minutes || '') + '">' +
            label +
            '</button>'
          );
        })
        .join('');
    }

    function renderSessions(list) {
      if (!sessionsEl) return;
      if (!list || !list.length) {
        sessionsEl.hidden = true;
        sessionsEl.innerHTML = '';
        return;
      }
      sessionsEl.hidden = false;
      sessionsEl.innerHTML = list
        .map(function (session) {
          var minutes = Math.max(0, Math.floor((session.remaining_seconds || 0) / 60));
          return (
            '<div class="ps-card ps-card--spot ps-animate-fade-up">' +
            '<div class="ps-card-header"><div class="ps-card-title">' + session.spot_name + ' · ' + session.lot_name + '</div></div>' +
            '<div class="ps-card-body">' +
            '<div class="ps-spot-meta">Осталось ~' + minutes + ' мин</div>' +
            '<div class="ps-card-actions">' +
            '<button class="ps-btn ps-btn-secondary ps-btn-sm" data-ai-action="booking_extend" data-booking-id="' + session.id + '">+30 мин</button>' +
            '<button class="ps-btn ps-btn-primary ps-btn-sm" data-ai-action="booking_stop" data-booking-id="' + session.id + '">Завершить</button>' +
            '</div>' +
            '</div>' +
            '</div>'
          );
        })
        .join('');
    }

    function csrfToken() {
      const match = document.cookie.match(/csrftoken=([^;]+)/);
      return match ? match[1] : '';
    }

    async function performActionFromButton(btn) {
      const type = btn.getAttribute('data-ai-action');
      const spotId = btn.getAttribute('data-spot-id');
      const bookingId = btn.getAttribute('data-booking-id');
      const extendMin = parseInt(btn.getAttribute('data-extend-min') || '30', 10);
      const duration = parseInt(btn.getAttribute('data-duration') || '60', 10);
      try {
        if (type === 'booking_start' && spotId) {
          await fetch('/api/v1/booking/start/', {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
            body: JSON.stringify({ spot_id: spotId, duration_minutes: duration })
          });
        } else if (type === 'booking_extend' && bookingId) {
          await fetch('/api/v1/booking/extend/', {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
            body: JSON.stringify({ booking_id: bookingId, extend_minutes: extendMin || 30 })
          });
        } else if (type === 'booking_stop' && bookingId) {
          await fetch('/api/v1/booking/stop/', {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
            body: JSON.stringify({ booking_id: bookingId })
          });
        } else if (type === 'focus_map' && spotId) {
          try { sessionStorage.setItem('ps_focus_spot', spotId); } catch (_) {}
          window.location.href = '/';
        } else if (type === 'book' && spotId) {
          window.location.href = '/booking/confirm/?spot_id=' + encodeURIComponent(spotId);
        }
        setStatus('Готово. Действие выполнено.', 'info');
      } catch (err) {
        setStatus('Не удалось выполнить действие', 'error');
      }
    }

  function handleSend() {
      if (!textarea || !textarea.value.trim() || isLoading) return;
      const text = textarea.value.trim();
      textarea.value = '';
      const userMsg = addMessage('user', text);
      const assistant = addMessage('assistant', '');
      render();
      const history = state.messages.filter(function (msg) { return msg.id !== assistant.id; });
      streamToApi(userMsg, assistant, history);
    }

    function handleRegenerate() {
      if (isLoading) return;
      let lastUserIndex = -1;
      for (let i = state.messages.length - 1; i >= 0; i--) {
        if (state.messages[i].role === 'user') {
          lastUserIndex = i;
          break;
        }
      }
      if (lastUserIndex === -1) return;
      // Оставляем историю до последнего пользовательского сообщения
      state.messages = state.messages.slice(0, lastUserIndex + 1);
      const userMsg = state.messages[lastUserIndex];
      const assistant = addMessage('assistant', '');
      const history = state.messages.filter(function (msg) { return msg.id !== assistant.id; });
      setStatus('Генерируем новый ответ…', 'info');
      render();
      streamToApi(userMsg, assistant, history);
    }

    function handleCopy(targetId) {
      const msg = state.messages.find(function (m) { return m.id === targetId; });
      if (!msg || !msg.content || !navigator.clipboard) return;
      navigator.clipboard.writeText(msg.content).catch(function () {});
    }

  async function streamToApi(userMsg, assistantMsg, historyOverride) {
      const baseHistory = (historyOverride && historyOverride.length ? historyOverride : state.messages).filter(function (msg) {
        return !(assistantMsg && msg.id === assistantMsg.id);
      });
      const payload = baseHistory.map(function (m) {
        return { role: m.role, content: m.content };
      });
      if (typeof navigator !== "undefined" && navigator.onLine === false) {
        if (window.ParkShare && window.ParkShare.handleApiError) {
          window.ParkShare.handleApiError({ message: 'Нет подключения. Попробуйте позже.' });
        }
        return;
      }
      isLoading = true;
      setStatus('Генерируем ответ…', 'info');
      try {
        const resp = await fetch('/api/v1/assistant/chat/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken(),
          },
          credentials: 'include',
          body: JSON.stringify({ messages: payload, structured: true })
        });

        if (!resp.ok) {
          let detail = '';
          try {
            const errJson = await resp.json();
            detail = errJson.detail || errJson.message || '';
          } catch (_) {
            try { detail = await resp.text(); } catch (__) { /* ignore */ }
          }
          if (window.ParkShare && window.ParkShare.handleApiError) {
            window.ParkShare.handleApiError({ message: detail || 'Ассистент недоступен.' });
          }
          throw new Error(detail || 'Ассистент недоступен.');
        }

        const data = await resp.json();
        updateMessage(assistantMsg.id, function (msg) {
          return { ...msg, content: data.reply || '' };
        });
        render();
        renderSuggestions(data);
        renderActions(data.actions || []);
        renderSessions(data.sessions || []);
        renderAlerts(data.alerts || []);
        setStatus('Готово. Можно задавать следующий вопрос.', 'info');
      } catch (error) {
        console.warn('Chat error', error);
        if (window.ParkShare && window.ParkShare.handleApiError) {
          window.ParkShare.handleApiError(error);
        }
        updateMessage(assistantMsg.id, function (msg) {
          return { ...msg, content: 'Сервис временно недоступен. Попробуйте позже.' };
        });
        setStatus('Ошибка сети или LLM. Попробуйте ещё раз.', 'error');
      } finally {
        isLoading = false;
        render();
      }
    }

    function handleClear() {
      state = { messages: [createWelcomeMessage()] };
      setStatus('История очищена. Новый диалог.', 'info');
      renderSuggestions({ suggestions: [] });
      renderActions([]);
      renderSessions([]);
      renderAlerts([]);
      render();
    }

    chatRoot.addEventListener('click', function (e) {
      const bubble = e.target.closest('[data-message-id]');
      if (!bubble) return;
      const id = bubble.getAttribute('data-message-id');
      if (e.target.matches('[data-ai-copy]')) {
        handleCopy(id);
      }
      if (e.target.matches('[data-ai-regenerate]')) {
        handleRegenerate();
      }
    });

    if (suggestionsEl) {
      suggestionsEl.addEventListener('click', function (e) {
        const mapBtn = e.target.closest('[data-ai-map]');
        const bookBtn = e.target.closest('[data-ai-book]');
        if (mapBtn) {
          const spotId = mapBtn.getAttribute('data-ai-map');
          try {
            sessionStorage.setItem('ps_focus_spot', spotId);
          } catch (_) {}
          window.location.href = '/';
        }
        if (bookBtn) {
          const spotId = bookBtn.getAttribute('data-ai-book');
          try {
            sessionStorage.setItem('ps_focus_spot', spotId);
          } catch (_) {}
          window.location.href = '/booking/confirm/?spot_id=' + encodeURIComponent(spotId);
        }
      });
    }

    if (actionsEl) {
      actionsEl.addEventListener('click', function (e) {
        const btn = e.target.closest('[data-ai-action]');
        if (!btn) return;
        performActionFromButton(btn);
      });
    }

    sendBtn && sendBtn.addEventListener('click', handleSend);
    clearBtn && clearBtn.addEventListener('click', handleClear);
    regenerateBtn && regenerateBtn.addEventListener('click', handleRegenerate);

    promptButtons.forEach(function (btn) {
      btn.addEventListener('click', function () {
        const prompt = btn.textContent || '';
        if (!textarea) return;
        textarea.value = prompt;
        textarea.focus();
      });
    });

    if (textarea) {
      textarea.addEventListener('keydown', function (evt) {
        if (evt.key === 'Enter' && !evt.shiftKey) {
          evt.preventDefault();
          handleSend();
        }
      });
    }

    render();
  }

  document.addEventListener('DOMContentLoaded', setupChat);
})();
