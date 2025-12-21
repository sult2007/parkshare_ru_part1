'use client';

import { useAuth } from '@/hooks/useAuth';
import { planParking, PlannerPlanPayload, PlannerRecommendation } from '@/lib/plannerClient';
import { useState } from 'react';

export default function PlannerPage() {
  const { isAuthenticated } = useAuth();
  const [payload, setPayload] = useState<PlannerPlanPayload>({
    destination_lat: 55.7558,
    destination_lon: 37.6176,
    max_price_level: 0
  });
  const [status, setStatus] = useState<string>('');
  const [results, setResults] = useState<PlannerRecommendation[]>([]);

  if (!isAuthenticated) {
    return (
      <section className="flex min-h-[60vh] flex-col items-center justify-center gap-3 text-center">
        <h1 className="text-3xl font-semibold text-[var(--text-primary)]">Войдите, чтобы планировать парковку</h1>
        <p className="max-w-xl text-[var(--text-muted)]">
          Smart Parking Planner доступен авторизованным пользователям. Пройдите вход по email/SMS или через VK, Яндекс ID, Google.
        </p>
        <a
          href="/auth"
          className="rounded-full bg-[var(--accent)] px-4 py-2 text-sm font-semibold text-white shadow-[0_14px_30px_rgba(79,195,255,0.25)]"
        >
          Войти
        </a>
      </section>
    );
  }

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setStatus('Готовим план…');
    try {
      const data = await planParking(payload);
      setResults(data.recommendations || []);
      setStatus('');
    } catch (err) {
      setStatus('Не удалось получить рекомендации');
    }
  };

  return (
    <section className="grid gap-4">
      <div className="rounded-[24px] border border-[var(--border-subtle)]/80 bg-[var(--bg-elevated)] p-4 shadow-[0_18px_44px_rgba(15,23,42,0.08)]">
        <p className="text-[11px] font-semibold uppercase tracking-[0.25em] text-[var(--accent-strong)]">Smart Planner</p>
        <h1 className="text-3xl font-semibold text-[var(--text-primary)]">Маршрут и прогноз загруженности</h1>
        <p className="max-w-3xl text-[var(--text-muted)]">Настройте координаты назначения, предпочтения и получите лучшие споты рядом.</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <form onSubmit={submit} className="rounded-[20px] border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-4 shadow-[0_18px_38px_rgba(15,23,42,0.05)]">
          <div className="grid gap-3">
            <div className="grid grid-cols-2 gap-3">
              <label className="grid gap-1 text-sm text-[var(--text-muted)]">
                Широта
                <input
                  className="rounded-2xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] px-3 py-2 text-sm text-[var(--text-primary)]"
                  type="number"
                  step="0.0001"
                  value={payload.destination_lat}
                  onChange={(e) => setPayload({ ...payload, destination_lat: parseFloat(e.target.value) })}
                  required
                />
              </label>
              <label className="grid gap-1 text-sm text-[var(--text-muted)]">
                Долгота
                <input
                  className="rounded-2xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] px-3 py-2 text-sm text-[var(--text-primary)]"
                  type="number"
                  step="0.0001"
                  value={payload.destination_lon}
                  onChange={(e) => setPayload({ ...payload, destination_lon: parseFloat(e.target.value) })}
                  required
                />
              </label>
            </div>
            <label className="grid gap-1 text-sm text-[var(--text-muted)]">
              Время прибытия
              <input
                className="rounded-2xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] px-3 py-2 text-sm text-[var(--text-primary)]"
                type="datetime-local"
                onChange={(e) => setPayload({ ...payload, arrival_at: e.target.value || null })}
              />
            </label>
            <div className="grid grid-cols-2 gap-3">
              <label className="inline-flex items-center gap-2 text-sm text-[var(--text-primary)]">
                <input
                  type="checkbox"
                  checked={payload.requires_ev_charging || false}
                  onChange={(e) => setPayload({ ...payload, requires_ev_charging: e.target.checked })}
                />
                Нужна зарядка
              </label>
              <label className="inline-flex items-center gap-2 text-sm text-[var(--text-primary)]">
                <input
                  type="checkbox"
                  checked={payload.requires_covered || false}
                  onChange={(e) => setPayload({ ...payload, requires_covered: e.target.checked })}
                />
                Крытое место
              </label>
            </div>
            <label className="grid gap-1 text-sm text-[var(--text-muted)]">
              Максимальный уровень цены (0-5)
              <input
                className="rounded-2xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] px-3 py-2 text-sm text-[var(--text-primary)]"
                type="number"
                min={0}
                max={5}
                value={payload.max_price_level || 0}
                onChange={(e) => setPayload({ ...payload, max_price_level: parseInt(e.target.value || '0', 10) })}
              />
            </label>
            <div className="flex items-center justify-between gap-3">
              <button
                type="submit"
                className="rounded-full bg-[var(--accent)] px-4 py-2 text-sm font-semibold text-white shadow-[0_14px_30px_rgba(79,195,255,0.25)] transition hover:-translate-y-[1px]"
              >
                Получить план
              </button>
              <span className="text-sm text-[var(--text-muted)]">{status}</span>
            </div>
          </div>
        </form>

        <div className="rounded-[20px] border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-4 shadow-[0_18px_38px_rgba(15,23,42,0.05)]">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-[var(--text-primary)]">Рекомендации</h2>
            <span className="rounded-full border border-[var(--border-subtle)] px-3 py-1 text-xs font-semibold text-[var(--text-muted)]">
              β
            </span>
          </div>
          <div className="mt-3 grid gap-3">
            {results.length === 0 ? (
              <p className="text-sm text-[var(--text-muted)]">Запросите план, чтобы увидеть лучшие споты.</p>
            ) : (
              results.map((item) => (
                <article
                  key={item.spot_id}
                  className="rounded-2xl border border-[var(--border-subtle)] bg-gradient-to-br from-[var(--bg-surface)] to-[var(--bg-elevated)] p-3 shadow-[0_14px_34px_rgba(15,23,42,0.08)]"
                >
                  <p className="text-base font-semibold text-[var(--text-primary)]">{item.lot_name}</p>
                  <p className="text-sm text-[var(--text-muted)]">{item.address}</p>
                  <div className="mt-2 flex flex-wrap gap-2 text-xs text-[var(--text-muted)]">
                    <span>~{item.distance_km} км</span>
                    <span>Загруженность {(item.predicted_occupancy * 100).toFixed(0)}%</span>
                    <span>EV {item.has_ev_charging ? 'да' : 'нет'}</span>
                    <span>Крытая {item.is_covered ? 'да' : 'нет'}</span>
                  </div>
                </article>
              ))
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
