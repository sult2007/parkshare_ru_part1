'use client';

import Image from 'next/image';
import { ThemeToggle } from './theme-toggle';
import { Bars3Icon } from '@heroicons/react/24/outline';

export function Header() {
  return (
    <header className="sticky top-0 z-20 border-b border-slate-200/60 dark:border-slate-800/60 backdrop-blur bg-white/70 dark:bg-slate-900/70">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-r from-blue-500 to-indigo-500 text-white shadow-sm">
            <Bars3Icon className="h-6 w-6" />
          </div>
          <div>
            <p className="text-lg font-semibold">ParkShare AI Concierge</p>
            <p className="text-xs text-slate-500 dark:text-slate-400">Smart assistant for parking partners</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <ThemeToggle />
          <div className="hidden sm:block text-right">
            <p className="text-sm font-medium leading-tight">Local dev user</p>
            <p className="text-xs text-slate-500 dark:text-slate-400 leading-tight">localhost</p>
          </div>
          <div className="h-9 w-9 rounded-full bg-slate-200 dark:bg-slate-700" />
        </div>
      </div>
    </header>
  );
}
