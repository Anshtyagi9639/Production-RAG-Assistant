"use client"

import { useMutation } from "@tanstack/react-query"
import { Loader2 } from "lucide-react"
import Link from "next/link"
import { Suspense, useState } from "react"

import { FormError } from "@/components/auth/form-error"
import { useSignedInRedirect } from "@/components/auth/use-signed-in-redirect"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { authApi } from "@/lib/api/endpoints"
import { accessToken } from "@/lib/session"

const MIN_PASSWORD_LENGTH = 8

function RegisterForm() {
  useSignedInRedirect()
  const [fullName, setFullName] = useState("")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const register = useMutation({
    // Registration creates the user, a default workspace and the owner membership; then sign in.
    mutationFn: async () => {
      await authApi.register({ full_name: fullName.trim(), email: email.trim(), password })
      return authApi.login(email.trim(), password)
    },
    onSuccess: (token) => accessToken.set(token.access_token),
  })

  return (
    <Card>
      <title>Create account · Knowledge Copilot</title>
      <CardHeader>
        <CardTitle>
          <h1>Create your account</h1>
        </CardTitle>
        <CardDescription>You&apos;ll get a workspace you own right away.</CardDescription>
      </CardHeader>
      <CardContent>
        <form
          className="space-y-4"
          onSubmit={(event) => {
            event.preventDefault()
            register.mutate()
          }}
        >
          <FormError error={register.error} />
          <div className="space-y-2">
            <Label htmlFor="full-name">Full name</Label>
            <Input
              id="full-name"
              autoComplete="name"
              required
              maxLength={200}
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
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              autoComplete="new-password"
              required
              minLength={MIN_PASSWORD_LENGTH}
              aria-describedby="password-hint"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
            <p id="password-hint" className="text-xs text-muted-foreground">
              At least {MIN_PASSWORD_LENGTH} characters.
            </p>
          </div>
          <Button type="submit" className="w-full" disabled={register.isPending}>
            {register.isPending && <Loader2 className="animate-spin" aria-hidden />}
            Create account
          </Button>
          <p className="text-center text-sm text-muted-foreground">
            Already have an account?{" "}
            <Link href="/login" className="font-medium text-primary hover:underline">
              Sign in
            </Link>
          </p>
        </form>
      </CardContent>
    </Card>
  )
}

export default function RegisterPage() {
  return (
    <Suspense>
      <RegisterForm />
    </Suspense>
  )
}
