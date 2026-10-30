"use client"

import { useMutation } from "@tanstack/react-query"
import { ArrowRight, Loader2 } from "lucide-react"
import Link from "next/link"
import { Suspense, useState } from "react"

import { authErrorMessage } from "@/components/auth/auth-error-message"
import { FormError } from "@/components/auth/form-error"
import { PasswordInput } from "@/components/auth/password-input"
import { useSignedInRedirect } from "@/components/auth/use-signed-in-redirect"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { authApi } from "@/lib/api/endpoints"
import { accessToken } from "@/lib/session"

function LoginForm() {
  useSignedInRedirect()
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const login = useMutation({
    mutationFn: () => authApi.login(email.trim(), password),
    // Storing the token triggers useSignedInRedirect.
    onSuccess: (token) => accessToken.set(token.access_token),
  })

  return (
    <div className="space-y-6">
      <title>Sign in · Knowledge Copilot</title>
      <div className="space-y-1.5">
        <h1 className="text-2xl font-semibold tracking-tight">Welcome back</h1>
        <p className="text-sm text-muted-foreground">Sign in to your workspace.</p>
      </div>
      <form
        className="space-y-4"
        onSubmit={(event) => {
          event.preventDefault()
          login.mutate()
        }}
      >
        <FormError error={login.error} describe={(error) => authErrorMessage(error, "sign in")} />
        <div className="space-y-2">
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            placeholder="you@company.com"
            required
            className="h-10"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="password">Password</Label>
          <PasswordInput
            id="password"
            autoComplete="current-password"
            required
            className="h-10"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </div>
        <Button type="submit" size="lg" className="h-10 w-full" disabled={login.isPending}>
          {login.isPending ? (
            <>
              <Loader2 className="animate-spin" aria-hidden />
              Signing in…
            </>
          ) : (
            <>
              Sign in
              <ArrowRight aria-hidden />
            </>
          )}
        </Button>
      </form>
      <p className="text-center text-sm text-muted-foreground">
        New to Knowledge Copilot?{" "}
        <Link href="/register" className="font-medium text-primary hover:underline">
          Create an account
        </Link>
      </p>
    </div>
  )
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  )
}
