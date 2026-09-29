import { BookOpenText } from "lucide-react"

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <main className="flex min-h-svh flex-col items-center justify-center gap-6 p-4">
      <div className="flex items-center gap-2 font-semibold">
        <span className="flex size-8 items-center justify-center rounded-md bg-primary text-primary-foreground">
          <BookOpenText className="size-4" aria-hidden />
        </span>
        Knowledge Copilot
      </div>
      <div className="w-full max-w-sm">{children}</div>
    </main>
  )
}
