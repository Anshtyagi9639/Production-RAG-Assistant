"use client"

import { useMutation } from "@tanstack/react-query"
import { ArrowRight, Check, Loader2 } from "lucide-react"
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
import { cn } from "@/lib/utils"

// Matches the API's minimum (RegisterRequest.password).
const MIN_PASSWORD_LENGTH = 8

function RegisterForm() {
  useSignedInRedirect()
  const [fullName, setFullName] = useState("")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const longEnough = password.length >= MIN_PASSWORD_LENGTH
  const register = useMutation({
    // Registration creates the user, a default workspace and the owner membership; then sign in.
    mutationFn: async () => {
      await authApi.register({ full_name: fullName.trim(), email: email.trim(), password })
      return authApi.login(email.trim(), password)
    },
    onSuccess: (token) => accessToken.set(token.access_token),
  })

  return (
    <div className="space-y-6">
      <title>Create account · Knowledge Copilot</title>
      <div className="space-y-1.5">
        <h1 className="text-2xl font-semibold tracking-tight">Create your account</h1>
        <p className="text-sm text-muted-foreground">
          You&apos;ll get your own workspace right away.
        </p>
      </div>
      <form
        className="space-y-4"
        onSubmit={(event) => {
          event.preventDefault()
          register.mutate()
        }}
      >
        <FormError
          error={register.error}
          describe={(error) => authErrorMessage(error, "create your account")}
        />
        <div className="space-y-2">
          <Label htmlFor="full-name">Full name</Label>
          <Input
            id="full-name"
            autoComplete="name"
            placeholder="Alex Morgan"
            required
            maxLength={200}
            className="h-10"
            value={fullName}
            onChange={(event) => setFullName(event.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="email">Work email</Label>
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
            autoComplete="new-password"
            required
            minLength={MIN_PASSWORD_LENGTH}
            maxLength={128}
            aria-describedby="password-hint"
            className="h-10"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
          <p
            id="password-hint"
            className={cn(
              "flex items-center gap-1.5 text-xs text-muted-foreground transition-colors",
              longEnough && "text-success",
            )}
          >
            <Check className={cn("size-3.5", !longEnough && "opacity-40")} aria-hidden />
            At least {MIN_PASSWORD_LENGTH} characters
          </p>
        </div>
        <Button type="submit" size="lg" className="h-10 w-full" disabled={register.isPending}>
          {register.isPending ? (
            <>
              <Loader2 className="animate-spin" aria-hidden />
              Creating account…
            </>
          ) : (
            <>
              Create account
              <ArrowRight aria-hidden />
            </>
          )}
        </Button>
      </form>
      <p className="text-center text-sm text-muted-foreground">
        Already have an account?{" "}
        <Link href="/login" className="font-medium text-primary hover:underline">
          Sign in
        </Link>
      </p>
    </div>
  )
}

export default function RegisterPage() {
  return (
    <Suspense>
      <RegisterForm />
    </Suspense>
  )
}
