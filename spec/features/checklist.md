# Project Checklist — Frontend & Backend Status

Last updated: 2026-07-10

## Frontend (deliv_project)

| Task | Status | Notes |
|------|--------|-------|
| JWT interceptor tests (001 T15) | ✅ | 14 tests pass |
| WebSocket reconnect service (004 T13) | ✅ | ws.js with exp backoff + queue |
| Background location service (005 T11) | ✅ | 3s cadence, offline queue, auth |
| FCM registration service (008 T12) | ✅ | expo-notifications + SecureStore auth |
| Config centralization (C-1) | ✅ | app.json extra + utils/config.js |
| SecureStore migration (C-2) | ✅ | authApi.js uses SecureStore |
| Remove deliveryApi.js (C-3) | ✅ | Orphaned dead code removed |
| Location auth header (C-4) | ✅ | Bearer token from SecureStore |
| Notification auth header (C-5) | ✅ | Bearer token from SecureStore |
| ProjectId fix (C-6) | ✅ | Constants.expoConfig extra |
| **015 Frontend Modernization — Wave 1** | ✅ | Bug fixes, deprecation cleanup |
| **015 Frontend Modernization — Wave 2** | ✅ | HTTP unification → fetch + React Query |
| **015 Frontend Modernization — Wave 3** | ✅ | AsyncStorage → expo-sqlite |
| **015 Frontend Modernization — Wave 4** | ⏳ | Expo Router (pending) |
| **015 Frontend Modernization — Wave 5** | ⏳ | @expo/ui + TS strict (pending) |

## Backend (deliv_ST)

| Feature | Status | Notes |
|---------|--------|-------|
| 001 Users & Auth | 16/16 ✅ | JWT, register, login, roles |
| 002 Customers | 12/12 ✅ | Profile, addresses, CRUD |
| 003 Vendors | 12/12 ✅ | **T2 haversine completed** |
| 004 Orders | 15/15 ✅ | Status machine, WS, assignment |
| 005 Delivery | 13/13 ✅ | Availability, location, earnings |
| 006 Mobility | 14/14 ✅ | Trips, driver pool, WS |
| 007 Payments | 15/15 ✅ | Stripe/MP, webhooks, refunds |
| 008 Notifications | 14/14 ✅ | FCM, in-app, WS, hooks |

## Infrastructure

| Item | Status | Notes |
|------|--------|-------|
| GitHub Actions CI (backend) | ✅ | Lint + test workflows |
| GitHub Actions CI (frontend) | ✅ | ESLint + Jest workflows |
| CI workflows | ⏳ Pending | Phase 0, deferred |
| Frontend tests | 15/15 ✅ | 3 suites pass (smoke, authApi, AuthContext) |

## Security (Post-Fix)

| Finding | Status | Notes |
|---------|--------|-------|
| C-1: Hardcoded URLs | ✅ Fixed | Centralized in utils/config.js + env vars |
| C-2: AsyncStorage tokens | ✅ Fixed | Migrated to SecureStore |
| C-3: Broken deliveryApi | ✅ Fixed | Deleted (dead code) |
| C-4: Location no auth | ✅ Fixed | Bearer token added |
| C-5: Notifications no auth | ✅ Fixed | Bearer token added |
| C-6: Placeholder projectId | ✅ Fixed | Constants.expoConfig used |

## Real-Time Tracking

| Feature | Status | Notes |
|---------|--------|-------|
| Order WebSocket consumer | ✅ | ws/orders/<id>/ with status_update + location_update |
| Trip WebSocket consumer | ✅ | ws/trips/<id>/ with driver_location |
| Payment WebSocket consumer | ✅ | ws/payments/<id>/ with payment_update |
| ASGI routing | ✅ | All 4 apps wired (notifications, orders, mobility, payments) |
| OrderTrackingScreen WS | ✅ | Connected to ws/orders/ via ws.js |
| RideTrackingScreen WS | ✅ | Connected to ws/trips/ via ws.js |
| DeliveryMapScreen WS | ✅ | Broadcasts location via ws.js |
| MobilityMapScreen WS | ✅ | Broadcasts location via ws.js |

## Refunds & Admin

| Feature | Status | Notes |
|---------|--------|-------|
| Refund model | ✅ | Status, amount, reason, timestamps |
| Refund CRUD | ✅ | RefundViewSet with list/create/retrieve |
| Admin approve/reject | ✅ | POST approve/ + POST reject/ actions |
| Partial refunds | ✅ | Multiple refunds per payment, partial amounts |
| Celery refund processing | ✅ | process_refund task via gateway |
| Payment status update | ✅ | → partially_refunded or refunded on completion |
| Admin-only permissions | ✅ | approve/reject gated to admin role |

## Rate Limiting & Lockout

| Layer | Mechanism | Status | Config |
|-------|-----------|--------|--------|
| Middleware | IP + endpoint rate limit | ✅ | 5/5min login, 3/10min register, 2/5min reset |
| DRF Throttles | AnonRateThrottle + UserRateThrottle | ✅ | Anon 100/h, User 1000/h |
| Login throttle | LoginRateThrottle | ✅ | 5/min |
| Register throttle | RegisterRateThrottle | ✅ | 3/min |
| Location throttle | LocationRateThrottle | ✅ | 20/min |
| Account lockout | LockoutService (core/utils/lockout.py) | ✅ | 5 fails → exp backoff 1m→5m→15m→1h→1h |
| Lockout integrated | LoginSerializer | ✅ | check_lockout + record_failed_attempt + reset_attempts |
| Redis cache | CACHES config | ✅ | Redis backend for lockout + middleware |

## Phase 3 — Scale

| Item | Status | Notes |
|------|--------|-------|
| Celery queue split | ✅ | 3 queues (default/payments/notifications), 13 task routes |
| Read replicas catalogue | ✅ | CatalogueRouter routes Vendor+Product reads to 'replica' |
| PgBouncer config | ✅ | transaction-mode, pool 25, max client 100 (docker-compose) |
| Redis Sentinel | ✅ | Port 26379, monitor redis:6379, auto-failover (docker-compose) |
| DB replica service | ✅ | Hot standby PostgreSQL (profile: replica) |

## Frontend Modernization Detail

| Wave | Task | Status |
|------|------|--------|
| 1 | Bug fixes + deprecation cleanup | ✅ 8/8 |
| 2 | HTTP unification + React Query | ✅ 12/12 |
| 3 | Storage (expo-sqlite) + icons | ✅ 7/7 |
| 4 | Expo Router navigation | ⏳ Pending |
| 5 | @expo/ui + TypeScript strict | ⏳ Pending |
| V | Tests | ✅ 15/15 |

### Key files created during modernization
- `src/services/apiClient.ts` — typed fetch wrapper
- `src/utils/storage.js` — expo-sqlite key-value wrapper
- `.env.development` / `.env.production` — environment config
- `src/services/apiClient.ts` — installed @tanstack/react-query

### Key files deleted
- `metro.config.js` — Expo defaults only
- `__mocks__/@react-native-async-storage/` — no longer needed
- All `react-native-vector-icons` imports replaced with `@expo/vector-icons`

### Key packages removed
- `axios` → native fetch
- `react-native-vector-icons` → `@expo/vector-icons`
- `@react-native-async-storage/async-storage` → `expo-sqlite`
