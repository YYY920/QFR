# Login Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `/login` route that guards the existing `/` dashboard, using hardcoded credentials structured for easy backend swap-in.

**Architecture:** Three new files — `auth.ts` (pure credential logic + cookie side-effects), `app/login/page.tsx` (form UI), and `middleware.ts` (server-side redirect based on `qfr_auth` cookie). No existing files modified.

**Tech Stack:** Next.js 16 App Router, TypeScript, Tailwind CSS, shadcn/ui (`Card`, `Input`, `Label`, `Button`), Vitest

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `frontend/src/lib/auth.ts` | Create | Credential check, cookie + sessionStorage write |
| `frontend/src/lib/auth.test.ts` | Create | Unit tests for `checkCredentials` |
| `frontend/src/app/login/page.tsx` | Create | Login form UI, calls `login()`, redirects on success |
| `frontend/src/middleware.ts` | Create | Redirect unauthenticated requests to `/login` |

---

## Task 1: Auth utility (`frontend/src/lib/auth.ts`)

**Files:**
- Create: `frontend/src/lib/auth.ts`
- Create: `frontend/src/lib/auth.test.ts`

- [ ] **Step 1: Write failing tests**

Create `frontend/src/lib/auth.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { checkCredentials } from './auth'

describe('checkCredentials', () => {
  it('returns true for correct credentials', () => {
    expect(checkCredentials('admin', 'admin123')).toBe(true)
  })
  it('returns false for wrong password', () => {
    expect(checkCredentials('admin', 'wrong')).toBe(false)
  })
  it('returns false for wrong username', () => {
    expect(checkCredentials('user', 'admin123')).toBe(false)
  })
  it('returns false for empty credentials', () => {
    expect(checkCredentials('', '')).toBe(false)
  })
})
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd frontend && npm test -- --reporter=verbose 2>&1 | grep -A5 'checkCredentials'
```

Expected: `FAIL` — "Cannot find module './auth'"

- [ ] **Step 3: Implement `auth.ts`**

Create `frontend/src/lib/auth.ts`:

```ts
// Temporary hardcoded credentials — replace the body of login() with a fetch() call when backend is ready
const TEMP_USERNAME = 'admin'
const TEMP_PASSWORD = 'admin123'

export function checkCredentials(username: string, password: string): boolean {
  return username === TEMP_USERNAME && password === TEMP_PASSWORD
}

export function login(username: string, password: string): boolean {
  const ok = checkCredentials(username, password)
  if (ok) {
    document.cookie = 'qfr_auth=1; path=/'
    sessionStorage.setItem('qfr_session', '1')
  }
  return ok
}

export function logout(): void {
  document.cookie = 'qfr_auth=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT'
  sessionStorage.removeItem('qfr_session')
}
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd frontend && npm test -- --reporter=verbose 2>&1 | grep -A5 'checkCredentials'
```

Expected: 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/auth.ts frontend/src/lib/auth.test.ts
git commit -m "feat: add auth utility with hardcoded credentials"
```

---

## Task 2: Middleware (`frontend/src/middleware.ts`)

**Files:**
- Create: `frontend/src/middleware.ts`

> **Note (Next.js 16):** The AGENTS.md warns of breaking changes. Before writing, skim `frontend/node_modules/next/dist/docs/` for middleware docs to confirm `NextRequest`/`NextResponse` API is unchanged. The code below uses the standard App Router middleware pattern.

- [ ] **Step 1: Create middleware**

Create `frontend/src/middleware.ts`:

```ts
import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

export function middleware(request: NextRequest) {
  const isAuthenticated = request.cookies.has('qfr_auth')
  const isLoginPage = request.nextUrl.pathname === '/login'

  if (!isAuthenticated && !isLoginPage) {
    return NextResponse.redirect(new URL('/login', request.url))
  }
  if (isAuthenticated && isLoginPage) {
    return NextResponse.redirect(new URL('/', request.url))
  }
  return NextResponse.next()
}

export const config = {
  matcher: ['/', '/login'],
}
```

- [ ] **Step 2: Run full test suite to confirm nothing broke**

```bash
cd frontend && npm test
```

Expected: all existing tests still pass (middleware has no unit test — it's verified in Task 4)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/middleware.ts
git commit -m "feat: add middleware to protect dashboard route"
```

---

## Task 3: Login page (`frontend/src/app/login/page.tsx`)

**Files:**
- Create: `frontend/src/app/login/page.tsx`

- [ ] **Step 1: Create login page**

Create `frontend/src/app/login/page.tsx`:

```tsx
'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { login } from '@/lib/auth'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'

export default function LoginPage() {
  const router = useRouter()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const ok = login(username, password)
    if (ok) {
      router.push('/')
    } else {
      setError('用户名或密码错误')
    }
  }

  return (
    <div className="flex flex-1 items-center justify-center">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Peak Advisory</CardTitle>
          <CardDescription>请登录以访问报告仪表板</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="username">用户名</Label>
              <Input
                id="username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="password">密码</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
              />
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <Button type="submit" className="w-full">登录</Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
```

- [ ] **Step 2: Run full test suite**

```bash
cd frontend && npm test
```

Expected: all tests pass

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/login/page.tsx
git commit -m "feat: add login page UI"
```

---

## Task 4: Manual verification

- [ ] **Step 1: Start dev server**

```bash
cd frontend && npm run dev
```

- [ ] **Step 2: Verify redirect — open `http://localhost:3000` without login**

Expected: browser redirects to `http://localhost:3000/login`

- [ ] **Step 3: Verify wrong credentials**

Enter `admin` / `wrongpassword`, click 登录.
Expected: error message "用户名或密码错误" appears below the form.

- [ ] **Step 4: Verify correct credentials**

Enter `admin` / `admin123`, click 登录.
Expected: redirects to `http://localhost:3000/` and the AI Mapping Report dashboard loads.

- [ ] **Step 5: Verify already-logged-in redirect**

While the `qfr_auth` cookie is set, navigate to `http://localhost:3000/login`.
Expected: immediately redirects to `/`.
