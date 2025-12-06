'use client';

import { signIn } from 'next-auth/react';
import { FcGoogle } from 'react-icons/fc';

export function SignInCard() {
  return (
    <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-8 shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <h1 className="text-2xl font-semibold">Sign in to continue</h1>
      <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
        Use your verified Google account to access the ParkShare AI concierge.
      </p>
      <button
        onClick={() => signIn('google', { callbackUrl: '/' })}
        className="mt-6 flex w-full items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 py-3 text-white shadow hover:bg-blue-700"
        type="button"
      >
        <FcGoogle className="h-5 w-5" />
        Sign in with Google
      </button>
      <p className="mt-3 text-xs text-slate-500 dark:text-slate-400">
        We require Google-verified email addresses to keep your data secure.
      </p>
    </div>
  );
}
