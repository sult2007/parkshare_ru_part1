import { useState } from 'react';

type Props = {
  onVK?: () => void;
  onYandex?: () => void;
  onGoogle?: () => void;
};

function GoogleLogo() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="h-6 w-6">
      <path fill="#4285F4" d="M21.6 12.23c0-.8-.07-1.6-.21-2.36H12v4.48h5.36a4.6 4.6 0 0 1-2 3.02v2.5h3.24c1.9-1.75 3-4.33 3-7.64Z" />
      <path fill="#34A853" d="M12 22c2.7 0 4.96-.9 6.62-2.43l-3.24-2.5c-.9.6-2.06.96-3.38.96-2.6 0-4.8-1.76-5.58-4.12H3.08v2.59A10 10 0 0 0 12 22Z" />
      <path fill="#FBBC05" d="M6.42 13.91c-.2-.6-.32-1.24-.32-1.91s.12-1.32.32-1.91V7.5H3.08A10 10 0 0 0 2 12c0 1.6.38 3.1 1.08 4.5l3.34-2.59Z" />
      <path fill="#EA4335" d="M12 6.08c1.46 0 2.77.5 3.8 1.47l2.84-2.84C16.96 2.9 14.7 2 12 2 7.92 2 4.36 4.3 3.08 7.5l3.34 2.59C7.2 7.84 9.4 6.08 12 6.08Z" />
    </svg>
  );
}

function VkLogo() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="h-6 w-6">
      <path
        d="M3.5 7h2.7l2.2 4 2.1-4h2.4l-1.4 4.3 3.2-4.3h2.6l-4.2 5.3 3.8 5.7h-2.7l-2.3-3.5-2.3 3.5H8.9l3.8-5.4L7.6 7H3.5Z"
        fill="currentColor"
      />
    </svg>
  );
}

function YandexLogo() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="h-6 w-6">
      <path d="M8 3h3.6l2 6.3L15.6 3H19l-3.5 8V21h-2.6v-5.5L8 3Z" fill="currentColor" />
    </svg>
  );
}

export default function SocialLoginButtons({ onVK, onYandex, onGoogle }: Props) {
  const [loading, setLoading] = useState<string | null>(null);

  const handleClick = (key: string, fn?: () => void) => {
    if (!fn) return;
    setLoading(key);
    fn();
  };

  return (
    <div className="space-y-3">
      <button
        type="button"
        aria-label="Sign in with Google"
        onClick={() => handleClick('google', onGoogle)}
        disabled={loading === 'google'}
        className="group relative flex w-full items-center gap-3 overflow-hidden rounded-2xl border border-slate-200 bg-white px-4 py-3 text-left shadow-sm transition hover:-translate-y-[1px] hover:shadow-lg disabled:opacity-60 dark:border-slate-800 dark:bg-slate-900"
      >
        <span className="absolute inset-y-0 left-0 w-1.5 bg-[#4285F4]/80" aria-hidden="true" />
        <span className="flex h-12 w-16 items-center justify-center rounded-xl border border-slate-200 bg-white text-lg font-bold shadow-inner dark:border-slate-700">
          <GoogleLogo />
        </span>
        <div className="flex flex-col gap-0.5 leading-tight">
          <span className="text-sm font-semibold text-slate-900 dark:text-white">
            {loading === 'google' ? 'Перенаправляем…' : 'Sign in with Google'}
          </span>
          <span className="text-[11px] text-slate-500 dark:text-slate-300">Быстрый вход по аккаунту Google</span>
        </div>
        <span className="ml-auto text-xs font-semibold text-slate-400 dark:text-slate-300" aria-hidden="true">
          →
        </span>
      </button>

      <button
        type="button"
        aria-label="Войти через VK ID"
        onClick={() => handleClick('vk', onVK)}
        disabled={loading === 'vk'}
        className="group relative flex w-full items-center gap-3 overflow-hidden rounded-2xl border border-[#4c75a3]/60 bg-white px-4 py-3 text-left shadow-sm transition hover:-translate-y-[1px] hover:shadow-lg disabled:opacity-60 dark:border-[#4c75a3]/50 dark:bg-slate-900"
      >
        <span className="absolute inset-y-0 left-0 w-1.5 bg-[#4c75a3]" aria-hidden="true" />
        <span className="flex h-12 w-16 items-center justify-center rounded-xl bg-[#4c75a3] text-white shadow-inner shadow-[#4c75a3]/30">
          <VkLogo />
        </span>
        <div className="flex flex-col gap-0.5 leading-tight">
          <span className="text-sm font-semibold text-slate-900 dark:text-white">
            {loading === 'vk' ? 'Перенаправляем…' : 'Войти через VK ID'}
          </span>
          <span className="text-[11px] text-slate-500 dark:text-slate-300">Имя и email, без публикаций</span>
        </div>
        <span className="ml-auto text-xs font-semibold text-slate-400 dark:text-slate-300" aria-hidden="true">
          →
        </span>
      </button>

      <button
        type="button"
        aria-label="Войти через Яндекс ID"
        onClick={() => handleClick('yandex', onYandex)}
        disabled={loading === 'yandex'}
        className="group relative flex w-full items-center gap-3 overflow-hidden rounded-2xl border border-[#ffcc00]/50 bg-white px-4 py-3 text-left shadow-sm transition hover:-translate-y-[1px] hover:shadow-lg disabled:opacity-60 dark:border-[#ffcc00]/40 dark:bg-slate-900"
      >
        <span className="absolute inset-y-0 left-0 w-1.5 bg-[#ffcc00]" aria-hidden="true" />
        <span className="flex h-12 w-16 items-center justify-center rounded-xl bg-[#ffcc00] text-black shadow-inner shadow-amber-200/60">
          <YandexLogo />
        </span>
        <div className="flex flex-col gap-0.5 leading-tight">
          <span className="text-sm font-semibold text-slate-900 dark:text-white">
            {loading === 'yandex' ? 'Перенаправляем…' : 'Войти через Яндекс ID'}
          </span>
          <span className="text-[11px] text-slate-500 dark:text-slate-300">Профиль без лишних прав</span>
        </div>
        <span className="ml-auto text-xs font-semibold text-slate-400 dark:text-slate-300" aria-hidden="true">
          →
        </span>
      </button>
    </div>
  );
}
