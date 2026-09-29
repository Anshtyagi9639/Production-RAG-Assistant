import type { Metadata } from "next"
import { Geist } from "next/font/google"

import { Providers } from "@/app/providers"
import { cn } from "@/lib/utils"

import "./globals.css"

const geist = Geist({ subsets: ["latin"], variable: "--font-sans" })

export const metadata: Metadata = {
  title: "Knowledge Copilot",
  description: "Search, ask and analyze your team's internal documents with cited answers.",
}

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={cn("font-sans", geist.variable)}>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}
