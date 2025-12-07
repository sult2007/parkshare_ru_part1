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
    const textarea = qs('#ai-input', chatRoot);
    const sendBtn = qs('[data-ai-send]', chatRoot);
    const clearBtn = qs('[data-ai-clear]', chatRoot);
    const stopBtn = qs('[data-ai-stop]', chatRoot);
    const statusEl = qs('[data-ai-status]', chatRoot);
    const regenerateBtn = qs('[data-ai-regenerate]', chatRoot);
    const promptButtons = qsa('[data-ai-prompt]');
    const userId = document.body.getAttribute('data-user-id') || 'guest';
    const historyKey = chatRoot.getAttribute('data-ai-history-key') || 'default';
    const storage = storageKey(userId, historyKey);

    let state = loadState(storage) || { messages: [createWelcomeMessage()] };
    let isStreaming = false;
    let abortController = null;

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
      regenerateBtn.hidden = !hasUserMessages || isStreaming;
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

  function handleSend() {
      if (!textarea || !textarea.value.trim() || isStreaming) return;
      const text = textarea.value.trim();
      textarea.value = '';
      const userMsg = addMessage('user', text);
      const assistant = addMessage('assistant', '');
      render();
      const history = state.messages.filter(function (msg) { return msg.id !== assistant.id; });
      streamToApi(userMsg, assistant, history);
    }

    function handleRegenerate() {
      if (isStreaming) return;
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
      isStreaming = true;
      stopBtn && (stopBtn.hidden = true);
      setStatus('Генерируем ответ…', 'info');
      try {
        const resp = await fetch('/api/chat/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
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
            window.ParkShare.handleApiError({ message: detail || 'LLM недоступен. Настройте /api/chat/' });
          }
          throw new Error(detail || 'LLM недоступен. Настройте /api/chat/');
        }

        const contentType = resp.headers.get('content-type') || '';
        if (contentType.indexOf('application/json') !== -1) {
          const data = await resp.json();
          updateMessage(assistantMsg.id, function (msg) {
            return { ...msg, content: data.reply || '' };
          });
          render();
          renderSuggestions(data);
          setStatus('Готово. Можно задавать следующий вопрос.', 'info');
          isStreaming = false;
          return;
        }

        // Fallback: stream text
        abortController = new AbortController();
        isStreaming = true;
        stopBtn && (stopBtn.hidden = false);
        setStatus('Генерируем ответ…', 'info');
        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          const chunk = decoder.decode(value, { stream: true });
          updateMessage(assistantMsg.id, function (msg) {
            return { ...msg, content: (msg.content || '') + chunk };
          });
          render();
        }
        setStatus('Готово. Можно задавать следующий вопрос.', 'info');
      } catch (error) {
        if (error.name === 'AbortError') {
          setStatus('Остановлено пользователем.', 'info');
        } else {
          console.warn('Chat error', error);
          if (window.ParkShare && window.ParkShare.handleApiError) {
            window.ParkShare.handleApiError(error);
          }
          updateMessage(assistantMsg.id, function (msg) {
            return { ...msg, content: 'Сервис временно недоступен. Проверьте /api/chat/ или ключи LLM.' };
          });
          setStatus('Ошибка сети или LLM. Попробуйте ещё раз.', 'error');
        }
      } finally {
        isStreaming = false;
        stopBtn && (stopBtn.hidden = true);
        abortController = null;
        render();
      }
    }

    function handleStop() {
      if (abortController) {
        abortController.abort();
        abortController = null;
      }
      isStreaming = false;
      stopBtn && (stopBtn.hidden = true);
      setStatus('Остановлено пользователем.', 'info');
    }

    function handleClear() {
      state = { messages: [createWelcomeMessage()] };
      setStatus('История очищена. Новый диалог.', 'info');
      renderSuggestions({ suggestions: [] });
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

    sendBtn && sendBtn.addEventListener('click', handleSend);
    clearBtn && clearBtn.addEventListener('click', handleClear);
    stopBtn && stopBtn.addEventListener('click', handleStop);
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
