# Mobile app (React Native / Expo)

Staff companion to the hotel PMS web. Uses the same Django backend via `/api/v1/`.

## Stack

- Expo (React Native)
- Auth: Bearer token from `POST /api/v1/auth/login/`
- First screens: Login + Board (doska)

## Run

1. Start Django (from repo root):

```bash
.venv/bin/python manage.py runserver 0.0.0.0:8000
```

2. Point the app at your machine (phone cannot use `127.0.0.1`):

```bash
cd mobile
# macOS LAN example — use your Mac IP
export EXPO_PUBLIC_API_URL=http://192.168.1.10:8000/api/v1
npm start
```

iOS Simulator may use `http://127.0.0.1:8000/api/v1` (default).

3. Log in with the same staff username/password as the web.

## Sync with web

Web and mobile share one database. Check-in on mobile appears on the web board immediately (after refresh).

## Screens (MVP)

1. **Login** — same staff credentials as web
2. **Board** — room tiles; tap occupied/confirmed stay to open detail
3. **Reservation** — guest info, **Kirish** / **Chiqish** (calls `/api/v1/.../check-in|out/`)

## Structure

```
mobile/
  App.tsx
  src/api/       # HTTP client + types
  src/auth/      # token storage + API helpers
  src/screens/   # Login, Board, Reservation detail
```

Do not put business logic here — call `/api/v1/` only.
