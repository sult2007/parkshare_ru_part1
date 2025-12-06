import { ChatPanel } from '@/components/chat/chat-panel';

export default function HomePage() {
  return (
    <section className="flex flex-1 flex-col gap-6">
      <div className="overflow-hidden rounded-[28px] border border-[var(--border-subtle)]/80 bg-gradient-to-r from-white/85 via-[var(--bg-surface)] to-white/90 p-6 shadow-[0_25px_60px_rgba(15,23,42,0.08)] backdrop-blur dark:border-slate-800 dark:from-slate-950 dark:via-slate-900 dark:to-indigo-950/40">
        <div className="flex flex-col gap-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.3em] text-[var(--accent-strong)]">AI Concierge</p>
          <h1 className="text-3xl font-semibold leading-tight text-[var(--text-primary)] sm:text-4xl">Премиальный чат для парковок и гостей ParkShare</h1>
          <p className="max-w-3xl text-sm text-[var(--text-muted)] sm:text-base">
            Сфокусирован на мобильном опыте: липкое поле ввода, аккуратные карточки, мгновенные подсказки и готовность к офлайн.
            Начните новый диалог или возобновите прежний в один тап.
          </p>
          <div className="flex flex-wrap gap-2 text-[11px] font-semibold uppercase tracking-[0.15em] text-[var(--text-muted)]">
            <span className="rounded-full border border-[var(--border-subtle)]/60 bg-white px-3 py-1 shadow-sm">Локальная история</span>
            <span className="rounded-full border border-[var(--border-subtle)]/60 bg-white px-3 py-1 shadow-sm">Поддержка тем</span>
            <span className="rounded-full border border-[var(--border-subtle)]/60 bg-white px-3 py-1 shadow-sm">AI потоковые ответы</span>
          </div>
        </div>
      </div>
      <ChatPanel />
      <div id="features" className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {[
          { title: 'Мульти-провайдерный AI', desc: 'LLM через OpenAI/прокси. Потоковые ответы, обработка ошибок и перегенерация.' },
          { title: 'Безопасный вход', desc: 'Телефон + OTP, почта + пароль, VK/Яндекс OAuth. История привязывается к профилю.' },
          { title: 'PWA и офлайн', desc: 'Сервис-воркер, манифест, кеш оболочки и мягкие лоадеры для мобильного опыта.' }
        ].map((feature) => (
          <div
            key={feature.title}
            className="rounded-[22px] border border-[var(--border-subtle)]/70 bg-[var(--bg-elevated)] p-4 shadow-[0_14px_40px_rgba(15,23,42,0.06)]"
          >
            <p className="text-sm font-semibold text-[var(--text-primary)]">{feature.title}</p>
            <p className="mt-1 text-sm text-[var(--text-muted)]">{feature.desc}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
