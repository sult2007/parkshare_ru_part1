'use client';

interface SuggestedPromptsProps {
  onSelect: (prompt: string) => void;
}

const PROMPTS = [
  'Analyze occupancy trends for the last 7 days.',
  'Suggest dynamic pricing for weekend events.',
  'Generate a customer journey improvement plan.',
  'What KPIs should I monitor for a new garage launch?',
  'Draft a personalized outreach message for high-value partners.'
];

export function SuggestedPrompts({ onSelect }: SuggestedPromptsProps) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      {PROMPTS.map((prompt) => (
        <button
          key={prompt}
          onClick={() => onSelect(prompt)}
          className="group rounded-full border border-slate-200/70 bg-white/70 px-3 py-2 text-xs text-slate-700 shadow-sm transition hover:-translate-y-[1px] hover:border-indigo-300 hover:bg-indigo-50 hover:text-indigo-700 dark:border-slate-800 dark:bg-slate-800/80 dark:text-slate-200 dark:hover:border-indigo-500/60 dark:hover:bg-indigo-900/40 dark:hover:text-indigo-100"
        >
          <span className="mr-1 inline-block h-2 w-2 rounded-full bg-gradient-to-r from-blue-500 to-indigo-500 transition group-hover:scale-110" />
          {prompt}
        </button>
      ))}
    </div>
  );
}
