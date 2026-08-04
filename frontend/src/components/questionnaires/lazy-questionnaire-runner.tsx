"use client";

import dynamic from "next/dynamic";

import { Skeleton } from "@/components/ui/skeleton";
import type { QuestionnaireRunnerProps } from "./questionnaire-runner";

const DynamicQuestionnaireRunner = dynamic<QuestionnaireRunnerProps>(
  () => import("./questionnaire-runner").then((mod) => mod.QuestionnaireRunner),
  {
    loading: () => <QuestionnaireRunnerSkeleton />,
    ssr: false,
  },
);

export function LazyQuestionnaireRunner(props: QuestionnaireRunnerProps) {
  return <DynamicQuestionnaireRunner {...props} />;
}

function QuestionnaireRunnerSkeleton() {
  return (
    <section
      role="status"
      aria-live="polite"
      aria-label="Pregătim chestionarul"
      className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_17rem] lg:items-start"
    >
      <div className="overflow-hidden rounded-lg bg-surface ring-1 ring-border">
        <div className="px-5 py-5 md:px-6">
          <div className="flex items-center justify-between gap-4">
            <Skeleton className="h-9 w-24" />
            <Skeleton className="h-7 w-24" />
          </div>
          <Skeleton className="mt-6 h-4 w-40" />
          <Skeleton className="mt-3 h-10 w-full max-w-2xl" />
          <Skeleton className="mt-3 h-4 w-72 max-w-full" />
        </div>
        <div className="border-t border-border bg-muted px-5 py-3 md:px-6">
          <Skeleton className="h-4 w-44" />
        </div>
        <div className="divide-y divide-border">
          {Array.from({ length: 4 }).map((_, index) => (
            <div key={index} className="px-5 py-5 md:px-6">
              <div className="grid gap-3 md:grid-cols-[1.5rem_1fr]">
                <Skeleton className="size-5" />
                <div className="min-w-0">
                  <Skeleton className="h-5 w-full max-w-xl" />
                  <Skeleton className="mt-3 h-4 w-2/3" />
                  <div className="mt-4 grid gap-2 sm:grid-cols-5">
                    {Array.from({ length: 5 }).map((__, optionIndex) => (
                      <Skeleton key={optionIndex} className="h-11" />
                    ))}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
      <aside className="rounded-lg bg-surface p-4 ring-1 ring-border">
        <div className="flex items-center justify-between gap-3">
          <Skeleton className="h-5 w-20" />
          <Skeleton className="h-5 w-12" />
        </div>
        <div className="mt-4 h-2 overflow-hidden rounded-full bg-muted">
          <div className="loading-bar-sweep h-full w-1/3 rounded-full bg-primary" />
        </div>
        <Skeleton className="mt-5 h-11 w-full" />
        <Skeleton className="mt-4 h-16 w-full" />
      </aside>
    </section>
  );
}
