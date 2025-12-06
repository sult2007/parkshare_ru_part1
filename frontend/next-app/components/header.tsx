'use client';

import { ThemeToggle } from './theme-toggle';
import { Bars3Icon } from '@heroicons/react/24/outline';
import { useAuth } from '@/hooks/useAuth';

export function Header() {
  const { user, isAuthenticated, logout, loading } = useAuth();
  const userLabel = user?.name || user?.email || user?.phone || 'Гость';

  return (
    <header className="sticky top-0 z-20 border-b border-[var(--border-subtle)]/60 bg-[var(--bg-elevated)]/90 backdrop-blur-lg">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-gradient-to-br from-[var(--accent)] to-[var(--accent-strong)] text-white shadow-[0_10px_30px_rgba(59,130,246,0.25)]">
            <Bars3Icon className="h-6 w-6" />
          </div>
          <div className="leading-tight">
            <p className="text-lg font-semibold tracking-tight">ParkShare Concierge</p>
            <p className="text-xs text-[var(--text-muted)]">Премиальный ассистент для партнёров</p>
          </div>
        </div>
        <nav className="hidden items-center gap-4 text-sm font-medium text-[var(--text-muted)] sm:flex">
          <a className="rounded-full px-3 py-1 transition hover:text-[var(--text-primary)] hover:shadow-sm" href="/">Чат</a>
          <a className="rounded-full px-3 py-1 transition hover:text-[var(--text-primary)] hover:shadow-sm" href="/auth">Вход</a>
          <a className="rounded-full px-3 py-1 transition hover:text-[var(--text-primary)] hover:shadow-sm" href="#features">Особенности</a>
        </nav>
        <div className="flex items-center gap-3">
          <ThemeToggle />
          <div className="hidden sm:flex items-center gap-2 rounded-full border border-[var(--border-subtle)]/70 bg-[var(--bg-surface)] px-3 py-1.5 text-xs font-semibold text-[var(--text-muted)] shadow-sm">
            <span
              className={`h-2 w-2 rounded-full ${isAuthenticated ? 'bg-emerald-400' : 'bg-amber-400'}`}
              aria-hidden
            />
            <span className="text-[var(--text-primary)]">{loading ? 'Загрузка…' : userLabel}</span>
            {isAuthenticated ? (
              <button
                onClick={() => void logout()}
                className="rounded-full bg-white/70 px-2 py-1 text-[11px] font-semibold text-[var(--text-muted)] transition hover:-translate-y-[1px] hover:text-[var(--text-primary)]"
              >
                Выйти
              </button>
            ) : (
              <a
                href="/auth"
                className="rounded-full bg-white/80 px-2 py-1 text-[11px] font-semibold text-[var(--text-muted)] transition hover:-translate-y-[1px] hover:text-[var(--text-primary)]"
              >
                Войти
              </a>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
