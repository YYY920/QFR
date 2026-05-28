# Login Page Design

## Overview

Add a login page to the QFR frontend. Users must log in before accessing the report dashboard. Authentication is currently fake (hardcoded credentials), structured so the auth function can be swapped for a real API call later without touching the UI or routing logic.

## Routes

| Path | Description |
|------|-------------|
| `/login` | Login page — public, accessible without auth |
| `/` | Report dashboard — protected, redirects to `/login` if not authenticated |

## Auth Layer

**`src/lib/auth.ts`**

Exports a single `login(username, password): Promise<boolean>` function. Currently checks against hardcoded values:

```
username: admin
password: admin123
```

Returns `true` on match, `false` otherwise. To connect a real backend later, replace the body of this function with a `fetch` call — nothing else changes.

On successful login, writes a `qfr_session` key to `sessionStorage` (value: `"1"`). On logout (future), remove this key.

## Route Protection

**`src/middleware.ts`** (Next.js middleware)

Checks for `qfr_session` in the request cookies or session. Since `sessionStorage` is not accessible server-side, the middleware checks a cookie `qfr_auth` instead. The `auth.ts` login function sets both `sessionStorage` and a `qfr_auth` cookie on success.

- Request to `/` without `qfr_auth` cookie → redirect to `/login`
- Request to `/login` with `qfr_auth` cookie → redirect to `/`

## Login Page UI

**`src/app/login/page.tsx`**

Centered card layout (vertically and horizontally centered on the page). Uses existing `Card`, `Input`, `Button`, `Label` components from `src/components/ui/`.

Contents of the card:
1. Title: "QFR Login" (or the app name)
2. Username field (`<Input type="text">` with `<Label>`)
3. Password field (`<Input type="password">` with `<Label>`)
4. Login button (`<Button>`, full width)
5. Error message area: shown inline below the fields when credentials are wrong ("用户名或密码错误")

On submit:
1. Call `login(username, password)`
2. If `true` → `router.push('/')`
3. If `false` → show error message

## Files to Create / Modify

| File | Action |
|------|--------|
| `src/lib/auth.ts` | Create — auth function |
| `src/app/login/page.tsx` | Create — login UI |
| `src/middleware.ts` | Create — route protection |

No existing files are modified.

## Temporary Credentials

```
username: admin
password: admin123
```

These live only in `src/lib/auth.ts` and are clearly marked with a comment for easy replacement.
