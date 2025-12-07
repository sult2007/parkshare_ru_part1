'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  ArrowRightIcon,
  EnvelopeIcon,
  LockClosedIcon,
  PhoneIcon,
  SparklesIcon,
  ShieldCheckIcon
} from '@heroicons/react/24/outline';
import { useAuth } from '@/hooks/useAuth';
import SocialLoginButtons from '@/components/auth/SocialLoginButtons';

export default function AuthPage() {
  const {
    user,
    isAuthenticated,
    loading: authLoading,
    loginWithEmail,
    registerWithEmail,
    requestPhoneOtp,
    verifyPhoneOtp,
    verifyMfaCode,
    loginWithVK,
    loginWithYandex,
    logout,
    mfaChallenge
  } = useAuth();

  const [phone, setPhone] = useState('');
  const [otp, setOtp] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [otpRequested, setOtpRequested] = useState(false);
  const [mfaCode, setMfaCode] = useState('');

  const isPhoneValid = useMemo(() => phone.replace(/[^\d]/g, '').length >= 10, [phone]);

  useEffect(() => {
    if (mfaChallenge) {
      setStatus('Требуется подтверждение второго фактора. Введите код ниже.');
    }
  }, [mfaChallenge]);

  const handleSendOtp = async () => {
    setIsSubmitting(true);
    setError(null);
    setStatus(null);
    try {
      await requestPhoneOtp(phone);
      setOtpRequested(true);
      setStatus('Код отправлен. Введите его, чтобы подтвердить вход.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось отправить код.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleVerifyMfa = async () => {
    setIsSubmitting(true);
    setError(null);
    setStatus(null);
    try {
      const verified = await verifyMfaCode(mfaCode);
      if (verified) {
        setStatus('MFA подтверждена, вход завершён.');
        setMfaCode('');
      } else {
        setError('Не удалось подтвердить MFA.');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Код MFA не подошёл.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleVerifyOtp = async () => {
    setIsSubmitting(true);
    setError(null);
    setStatus(null);
    try {
      const verified = await verifyPhoneOtp(phone, otp);
      if (verified) {
        setStatus('Успешно! Сессия активна и готова к работе.');
      } else if (mfaChallenge) {
        setStatus('SMS/Email код принят. Подтвердите MFA.');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось подтвердить код.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleEmailAuth = async () => {
    setIsSubmitting(true);
    setError(null);
    setStatus(null);
    try {
      if (mode === 'login') {
        const loggedIn = await loginWithEmail(email, password);
        if (loggedIn) {
          setStatus('Вход выполнен. Продолжайте в чате.');
        } else if (mfaChallenge) {
          setStatus('Требуется подтверждение MFA. Введите код ниже.');
        }
      } else {
        const created = await registerWithEmail(email, password);
        if (created) {
          setStatus('Аккаунт создан, вы уже вошли.');
        } else if (mfaChallenge) {
          setStatus('Аккаунт создан. Подтвердите MFA, чтобы закончить.');
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось выполнить действие.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-6 py-6">
      <div className="flex flex-col gap-3 rounded-[28px] border border-[var(--border-subtle)]/80 bg-[var(--bg-elevated)] p-6 shadow-[0_25px_60px_rgba(15,23,42,0.08)]">
        <div className="flex items-start gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-[var(--accent)] to-[var(--accent-strong)] text-white shadow-[0_14px_38px_rgba(59,130,246,0.35)]">
            <SparklesIcon className="h-6 w-6" />
          </div>
          <div className="flex-1">
            <p className="text-[11px] font-semibold uppercase tracking-[0.3em] text-[var(--accent-strong)]">Единый вход</p>
            <h1 className="text-3xl font-semibold leading-tight text-[var(--text-primary)]">Вход в ParkShare</h1>
            <p className="mt-2 text-sm text-[var(--text-muted)]">
              Выберите способ: телефон с OTP, почта с паролем или VK/Яндекс. Одна учётка для всех сервисов ParkShare.
            </p>
            {isAuthenticated && (
              <div className="mt-3 flex items-center gap-3 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800 shadow-sm dark:border-emerald-800/60 dark:bg-emerald-950/40 dark:text-emerald-100">
                <ShieldCheckIcon className="h-5 w-5" />
                <div>
                  <p className="font-semibold">Вы вошли как {user?.name || user?.email || user?.phone || 'пользователь'}</p>
                  <p className="text-xs text-emerald-700/80 dark:text-emerald-100/80">Продолжайте в чате или выйдите, чтобы сменить профиль.</p>
                </div>
                <button
                  onClick={() => void logout()}
                  className="rounded-full bg-white/80 px-3 py-1 text-xs font-semibold text-emerald-700 transition hover:-translate-y-[1px] hover:shadow-sm"
                >
                  Выйти
                </button>
              </div>
            )}
          </div>
        </div>
        {status && (
          <p className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700 shadow-sm dark:border-emerald-900/60 dark:bg-emerald-950/40 dark:text-emerald-100">
            {status}
          </p>
        )}
        {error && (
          <p className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 shadow-sm dark:border-red-900/60 dark:bg-red-950/40 dark:text-red-100">
            {error}
          </p>
        )}
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div className="rounded-[20px] border border-[var(--border-subtle)]/70 bg-white/70 p-4 shadow-sm backdrop-blur dark:border-slate-800 dark:bg-slate-900/70">
            <div className="flex items-center gap-2 text-sm font-semibold text-[var(--text-primary)]">
              <PhoneIcon className="h-5 w-5" />
              <span>Телефон + SMS</span>
            </div>
            <p className="mt-1 text-xs text-[var(--text-muted)]">Отправим код на ваш номер. Без пароля.</p>
            <div className="mt-3 space-y-2">
              <input
                type="tel"
                inputMode="tel"
                placeholder="+7 (___) ___-__-__"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
              />
              <div className="flex gap-2">
                <button
                  className="w-full rounded-2xl bg-gradient-to-r from-[var(--accent)] to-[var(--accent-strong)] px-4 py-2 text-sm font-semibold text-white shadow-[0_14px_38px_rgba(59,130,246,0.35)] disabled:cursor-not-allowed disabled:opacity-60"
                  onClick={handleSendOtp}
                  disabled={!isPhoneValid || isSubmitting || authLoading}
                >
                  {otpRequested ? 'Отправить снова' : 'Отправить код'}
                </button>
                <button
                  className="min-w-[110px] rounded-2xl border border-[var(--border-subtle)]/70 bg-[var(--bg-elevated)] px-3 py-2 text-xs font-semibold text-[var(--text-primary)] shadow-sm disabled:opacity-50"
                  onClick={handleVerifyOtp}
                  disabled={!otp || isSubmitting || authLoading}
                >
                  Подтвердить
                </button>
              </div>
              <input
                type="text"
                inputMode="numeric"
                placeholder="Код из SMS"
                value={otp}
                onChange={(e) => setOtp(e.target.value)}
              />
            </div>
          </div>
          <div className="flex flex-col gap-3 rounded-[20px] border border-[var(--border-subtle)]/70 bg-white/70 p-4 shadow-sm backdrop-blur dark:border-slate-800 dark:bg-slate-900/70">
            <div className="flex items-center gap-2 text-sm font-semibold text-[var(--text-primary)]">
              <EnvelopeIcon className="h-5 w-5" />
              <span>Почта + пароль</span>
            </div>
            <div className="flex items-center gap-2 text-xs text-[var(--text-muted)]">
              <button
                onClick={() => setMode('login')}
                className={`rounded-full px-2 py-1 font-semibold transition ${mode === 'login' ? 'bg-[var(--bg-surface)] text-[var(--text-primary)] shadow-sm' : 'text-[var(--text-muted)]'}`}
              >
                Вход
              </button>
              <button
                onClick={() => setMode('register')}
                className={`rounded-full px-2 py-1 font-semibold transition ${mode === 'register' ? 'bg-[var(--bg-surface)] text-[var(--text-primary)] shadow-sm' : 'text-[var(--text-muted)]'}`}
              >
                Регистрация
              </button>
            </div>
            <input type="email" placeholder="you@example.com" value={email} onChange={(e) => setEmail(e.target.value)} />
            <input
              type="password"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <button
              className="flex items-center justify-center gap-2 rounded-2xl bg-[var(--text-primary)] px-4 py-3 text-sm font-semibold text-white shadow-[0_14px_38px_rgba(15,23,42,0.15)] transition hover:-translate-y-[1px] hover:shadow-lg disabled:opacity-50"
              onClick={handleEmailAuth}
              disabled={!email || !password || isSubmitting || authLoading}
            >
              <LockClosedIcon className="h-4 w-4" />
              {mode === 'login' ? 'Войти' : 'Создать аккаунт'}
              <ArrowRightIcon className="h-4 w-4" />
            </button>
            <p className="text-[11px] text-[var(--text-muted)]">Пароли передаются только по HTTPS. После входа используйте чат или бронирования без повторного подтверждения.</p>
          </div>
        </div>
        <div className="rounded-[20px] border border-[var(--border-subtle)]/70 bg-white/70 p-4 shadow-sm backdrop-blur dark:border-slate-800 dark:bg-slate-900/70">
          <p className="text-sm font-semibold text-[var(--text-primary)]">Соцсети</p>
          <p className="text-xs text-[var(--text-muted)]">VK и Яндекс через OAuth с редиректом назад в ParkShare.</p>
          <div className="mt-3">
            <SocialLoginButtons
              onVK={loginWithVK}
              onYandex={loginWithYandex}
              onGoogle={() => {
                window.location.href = '/api/auth/signin';
              }}
            />
          </div>
          <p className="mt-2 text-[11px] text-[var(--text-muted)]">OAuth перенаправит вас к провайдеру, затем вернёт сюда. MFA запрашивается после соц-входа, если включена.</p>
        </div>
      </div>
      {mfaChallenge && (
        <div className="mt-4 rounded-[20px] border border-[var(--border-subtle)]/70 bg-white/80 p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900/80">
          <div className="flex items-center gap-2 text-sm font-semibold text-[var(--text-primary)]">
            <ShieldCheckIcon className="h-5 w-5" />
            <span>Подтверждение MFA ({mfaChallenge.method})</span>
          </div>
          <p className="mt-1 text-xs text-[var(--text-muted)]">Введите код из приложения или сообщения. Мы не храним коды в браузере.</p>
          <div className="mt-3 flex flex-col gap-2 sm:flex-row">
            <input
              type="text"
              inputMode="numeric"
              placeholder="Код MFA"
              value={mfaCode}
              onChange={(e) => setMfaCode(e.target.value)}
              className="sm:w-1/3"
            />
            <button
              onClick={handleVerifyMfa}
              disabled={!mfaCode || isSubmitting || authLoading}
              className="rounded-2xl bg-[var(--text-primary)] px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:-translate-y-[1px] hover:shadow-lg disabled:opacity-50"
            >
              Подтвердить MFA
            </button>
          </div>
          <p className="mt-2 text-[11px] text-[var(--text-muted)]">Если провайдер не доставляет код — переключитесь на TOTP в настройках профиля.</p>
        </div>
      )}
    </div>
  );
}
