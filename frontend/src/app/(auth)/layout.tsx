import { Bot, FileText, Quote, ShieldCheck } from "lucide-react"

import { BrandMark, BrandName } from "@/components/brand"

const FEATURES = [
  {
    icon: Quote,
    title: "Answers you can verify",
    text: "Every answer links to the exact passages it was drawn from.",
  },
  {
    icon: Bot,
    title: "Multi-step analysis",
    text: "An agent compares documents, checks each claim and shows its steps.",
  },
  {
    icon: ShieldCheck,
    title: "Private workspaces",
    text: "Documents and answers stay inside the workspace they belong to.",
  },
]

const EXAMPLE_SOURCES = ["Travel policy.pdf · p. 4", "Expense handbook.docx · p. 12"]

/** Decorative: a faint dot grid that fades out toward the edges. */
function Backdrop() {
  return (
    <div aria-hidden className="pointer-events-none absolute inset-0">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_1px_1px,color-mix(in_oklch,var(--foreground)_12%,transparent)_1px,transparent_0)] [mask-image:radial-gradient(ellipse_at_center,black_20%,transparent_75%)] [background-size:22px_22px]" />
    </div>
  )
}

/** A static, labelled illustration of a cited answer (not live data). */
function ExampleAnswer() {
  return (
    <figure
      aria-label="Example of a cited answer"
      className="rounded-xl border bg-card p-4 shadow-md"
    >
      <figcaption className="mb-3 flex items-center justify-between">
        <span className="text-[11px] font-medium tracking-wide text-muted-foreground uppercase">
          Example
        </span>
        <span className="rounded-full border px-2 py-0.5 text-[11px] text-muted-foreground">
          2 sources
        </span>
      </figcaption>
      <p className="mb-2 text-sm font-medium">How long do I have to submit travel receipts?</p>
      <p className="text-sm leading-relaxed text-muted-foreground">
        Within 14 days of returning from a trip
        <span className="mx-1 inline-flex size-4 items-center justify-center rounded border border-primary/20 bg-accent align-[0.1em] text-[10px] font-semibold text-accent-foreground">
          1
        </span>
        . Hotel stays above the nightly limit need a director&apos;s approval
        <span className="mx-1 inline-flex size-4 items-center justify-center rounded border border-primary/20 bg-accent align-[0.1em] text-[10px] font-semibold text-accent-foreground">
          2
        </span>
        .
      </p>
      <ul className="mt-3 flex flex-wrap gap-1.5 border-t pt-3" aria-label="Sources">
        {EXAMPLE_SOURCES.map((source, index) => (
          <li
            key={source}
            className="flex items-center gap-1.5 rounded-md border bg-muted/50 px-2 py-1 text-[11px] text-muted-foreground"
          >
            <span className="font-semibold text-accent-foreground">{index + 1}</span>
            <FileText className="size-3" aria-hidden />
            {source}
          </li>
        ))}
      </ul>
    </figure>
  )
}

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid min-h-svh grid-cols-1 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
      <aside className="relative hidden flex-col justify-between overflow-hidden border-r bg-sidebar p-10 lg:flex">
        <Backdrop />
        <div className="relative flex items-center gap-2.5">
          <BrandMark />
          <BrandName />
        </div>
        <div className="relative mx-auto w-full max-w-md space-y-10">
          <div className="space-y-3">
            <h2 className="text-3xl font-semibold tracking-tight text-balance">
              Answers from your team&apos;s documents, with the sources to prove it.
            </h2>
            <p className="text-muted-foreground">
              Upload policies, contracts and handbooks. Ask questions in plain language and get
              grounded, cited answers.
            </p>
          </div>
          <ExampleAnswer />
          <ul className="space-y-4">
            {FEATURES.map(({ icon: Icon, title, text }) => (
              <li key={title} className="flex gap-3">
                <span className="flex size-8 shrink-0 items-center justify-center rounded-lg border bg-card shadow-xs">
                  <Icon className="size-4 text-primary" aria-hidden />
                </span>
                <div>
                  <p className="text-sm font-medium">{title}</p>
                  <p className="text-sm text-muted-foreground">{text}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>
        <p className="relative text-xs text-muted-foreground">
          Answers use only the documents in your workspace.
        </p>
      </aside>
      <main className="flex flex-col items-center justify-center px-4 py-10 sm:px-8">
        <div className="mb-8 flex items-center gap-2.5 lg:hidden">
          <BrandMark />
          <BrandName />
        </div>
        <div className="w-full max-w-sm">{children}</div>
      </main>
    </div>
  )
}
