import { useState } from 'react';

type Props = {
  onVK?: () => void;
  onYandex?: () => void;
  onGoogle?: () => void;
};

export default function SocialLoginButtons({ onVK, onYandex, onGoogle }: Props) {
  const [loading, setLoading] = useState<string | null>(null);

  const handleClick = (key: string, fn?: () => void) => {
    if (!fn) return;
    setLoading(key);
    fn();
  };

  return (
    <div className="space-y-2">
      <button
        type="button"
        onClick={() => handleClick('google', onGoogle)}
        disabled={loading === 'google'}
        className="group flex w-full items-center justify-between rounded-2xl border border-slate-200 bg-white px-4 py-3 text-left shadow-sm transition hover:-translate-y-[1px] hover:shadow-lg disabled:opacity-60 dark:border-slate-800 dark:bg-slate-900"
      >
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl border border-slate-200 bg-white text-lg font-bold shadow-inner dark:border-slate-700">
            <span className="block h-5 w-5 bg-gradient-to-br from-[#ea4335] via-[#fbbc05] to-[#4285f4] [mask:radial-gradient(circle_at_center,#000_45%,transparent_46%)]" />
          </span>
          <div className="flex flex-col leading-tight">
            <span className="text-sm font-semibold text-slate-900 dark:text-white">Sign in with Google</span>
            <span className="text-[11px] text-slate-500 dark:text-slate-300">Доступ только к имени и email</span>
          </div>
        </div>
        <span title="Мы не публикуем записи и не запрашиваем лишних прав." className="text-xs font-semibold text-slate-400">
          {loading === 'google' ? '...' : 'i'}
        </span>
      </button>

      <button
        type="button"
        onClick={() => handleClick('vk', onVK)}
        disabled={loading === 'vk'}
        className="group flex w-full items-center justify-between rounded-2xl border border-[#3b5ea9] bg-[#4C75A3] px-4 py-3 text-left text-white shadow-md transition hover:-translate-y-[1px] hover:shadow-lg disabled:opacity-60"
      >
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-white/15 text-sm font-bold">VK</span>
          <div className="flex flex-col leading-tight">
            <span className="text-sm font-semibold">Continue with VK</span>
            <span className="text-[11px] text-white/80">Никаких постов, только проверка профиля</span>
          </div>
        </div>
        <span title="Имя и email, без права публикации." className="text-xs font-semibold text-white/80">
          {loading === 'vk' ? '...' : 'i'}
        </span>
      </button>

      <button
        type="button"
        onClick={() => handleClick('yandex', onYandex)}
        disabled={loading === 'yandex'}
        className="group flex w-full items-center justify-between rounded-2xl border border-slate-200 bg-white px-4 py-3 text-left shadow-sm transition hover:-translate-y-[1px] hover:shadow-lg disabled:opacity-60 dark:border-slate-800 dark:bg-slate-900"
      >
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#ffd633] text-sm font-bold text-black shadow-inner">Я</span>
          <div className="flex flex-col leading-tight">
            <span className="text-sm font-semibold text-slate-900 dark:text-white">Войти через Yandex ID</span>
            <span className="text-[11px] text-slate-500 dark:text-slate-300">Без публикаций, только профиль</span>
          </div>
        </div>
        <span title="Получаем только email и имя." className="text-xs font-semibold text-slate-400 dark:text-slate-300">
          {loading === 'yandex' ? '...' : 'i'}
        </span>
      </button>
    </div>
  );
}
