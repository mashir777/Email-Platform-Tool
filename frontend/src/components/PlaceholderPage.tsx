import type { ReactNode } from "react";

interface PlaceholderPageProps {
  title: string;
  description: string;
  phase: string;
  children?: ReactNode;
}

export function PlaceholderPage({
  title,
  description,
  phase,
  children,
}: PlaceholderPageProps) {
  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-dashed border-slate-700 bg-slate-900/40 p-8 text-center">
        <p className="text-xs font-semibold uppercase tracking-wider text-indigo-400">
          {phase}
        </p>
        <h2 className="mt-2 text-xl font-semibold text-white">{title}</h2>
        <p className="mx-auto mt-2 max-w-lg text-sm text-slate-400">{description}</p>
        <p className="mt-4 text-xs text-slate-500">
          Django API integration will be added in a future phase.
        </p>
      </div>
      {children}
    </div>
  );
}
