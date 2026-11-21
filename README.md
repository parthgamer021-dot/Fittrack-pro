# FITTRACK PRO — Full-Stack Mobile-First Fitness & Recomposition PWA

FITTRACK PRO is a full-stack, mobile-first Progressive Web App (PWA) for body recomposition, nutrition tracking, 4-day upper/lower strength training, pedometer/activity logging, body transformation tracking, AI coaching, and social leaderboards/challenges.

## Architecture
- **Frontend (`public/index.html`)**: Mobile-first responsive PWA with Charcoal/Black + Neon Green dark mode, Light theme toggle, English + Marathi (`मराठी`) localization, Chart.js analytics, offline `localStorage` queue, and Service Worker (`public/sw.js`).
- **Backend (`server.py`)**: Zero-dependency Python 3 `ThreadingHTTPServer` with PBKDF2 password hashing, HMAC-SHA256 bearer tokens, strict `user_id` ownership checks, CSV/JSON export, and server-side API proxy for Gemini Vision/Coach.
- **Database (`schema.sql`)**: Normalized SQLite schema (PostgreSQL-compatible) covering users, profiles, meals, custom foods, supplements, workout splits, workout logs, PRs, activity logs, body metrics, private progress photos, sleep/water/habit logs, friendships, groups, challenges, notifications, and reports.

## Quick Start (Local / Self-Hosted)
```bash
cd fittrack-pro
cp .env.example .env
# Edit .env with your APP_SECRET and optional API keys
python3 server.py
# Open http://localhost:8080
```
Demo account seeded on first boot: `demo@fittrack.pro` / `DemoPass123!`

## Configuring External API Keys (Server-Side Only)
Add keys to `.env` (never expose them in frontend code):
- `GEMINI_API_KEY` or `OPENAI_API_KEY`: Enables live AI Food Photo Vision & AI Personal Coach endpoints (`/api/ai/food-scan`, `/api/ai/coach`). Without a key, the app honestly reports `Not Configured` and provides full manual entry and local rule-based wellness guidance.
- `USDA_API_KEY` / `NUTRITIONIX_APP_ID` + `NUTRITIONIX_API_KEY`: Enables external food database lookup. Without keys, the built-in Indian/hostel/high-protein catalog and custom food creator are active.
- `GOOGLE_MAPS_API_KEY`: Optional enhanced map tiles; browser `navigator.geolocation` works for GPS route capture with explicit user permission.
- `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY`: Enables Web Push notifications.

## Installing on Android (PWA)
1. Host `fittrack-pro` behind HTTPS (e.g., Render, Railway, Fly.io, or local LAN with HTTPS).
2. Open the URL in **Google Chrome** on Android.
3. Tap the **⋮** browser menu -> **Add to Home screen** / **Install app**.
4. Launch FITTRACK PRO from your home screen in standalone full-screen mode.
5. *Note on Android Health Connect & Background Steps*: Web PWAs cannot directly read Android Health Connect or run guaranteed background step daemons. To enable Health Connect sync, wrap the PWA with **Trusted Web Activity (TWA)** or **Capacitor** + the Android Health Connect SDK.

## Implemented vs. Credential/Native-Gated Checklist
### Fully Implemented (Works Immediately)
- Auth (signup, login, logout, password recovery flow, friend code & QR invite)
- Onboarding & editable macro/calorie/step/water goals + BMR/TDEE calculator
- Home Dashboard with customizable widgets, streaks, XP, and weekly overview
- Nutrition Tracker (meals, custom foods, barcode field, vegetarian & hostel-mess planner, budget protein foods, grocery list generator, supplement tracker)
- AI Food Photo Scanner UI (image upload/capture, editable macro estimates, clear "Estimate" labeling, manual fallback)
- Workout Tracker (editable 4-day Upper/Lower split, exercise library, rest timer, warmup/cooldown, PRs & 1RM, progressive overload, substitutions, volume analytics)
- Activity & Pedometer Tracker (GPS route tracking with permission prompt, running/walking logs, manual entry with clear source labels, charts)
- Body Transformation Tracker (measurements, body-fat %, private photo gallery, before/after comparison slider, milestone timeline)
- AI Coach UI (calorie deficit/surplus explainer, meal gap suggestions, recovery advice, natural-language Q&A, wellness vs. medical disclaimer)
- Social, Leaderboards, 1v1/Group Challenges, Gamification (XP, levels, leagues, anti-cheat verified vs. manual badges, block/report)
- Sleep, Water, Recovery, Habit Journal, Notifications, CSV/PDF/JSON Export, Dark/Light & English/Marathi

### Requires API Keys or Native Android Wrapper
- Live AI Vision food recognition (`GEMINI_API_KEY` / `OPENAI_API_KEY`)
- Live external nutrition API search (`USDA_API_KEY` / `NUTRITIONIX_API_KEY`)
- Android Health Connect & persistent background pedometer (requires native Android / Capacitor / TWA)
- Live Web Push delivery when app is closed (`VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` + HTTPS)
