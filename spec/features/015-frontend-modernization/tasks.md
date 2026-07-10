# Tasks — Feature 015: Frontend Modernization

## Wave 1 — Bug fixes & deprecation cleanup
- [x] 1.1 Replace `<div>` in `MainStack.js` (Favorites & About screens) with `<View><Text>...`
- [x] 1.2 Remove duplicate Android permissions from `app.json`
- [x] 1.3 Remove `newArchEnabled: true` from `app.json`
- [x] 1.4 Remove `@babel/plugin-transform-private-methods` and `@babel/plugin-transform-class-properties` from `babel.config.js`
- [x] 1.5 Delete `metro.config.js` if it only contains Expo defaults
- [x] 1.6 Remove `react-native-vector-icons` from `package.json`
- [x] 1.7 Remove `@types/react` and `typescript` from `dependencies` (keep in `devDependencies`)
- [x] 1.8 Run `npx expo install --fix` to sync versions

## Wave 2 — HTTP unification & React Query
- [x] 2.1 Create `.env.development` and `.env.production` with `EXPO_PUBLIC_API_URL`
- [x] 2.2 Update `src/utils/config.js` to use `process.env.EXPO_PUBLIC_API_URL`
- [x] 2.3 Install `@tanstack/react-query` and `expo-constants`
- [x] 2.4 Create `src/services/apiClient.ts` with typed fetch wrapper + token interceptor
- [x] 2.5 Wrap `App.js` with `QueryClientProvider`
- [x] 2.6 Rewrite `src/services/authApi.js` to use fetch + apiClient
- [x] 2.7 Rewrite `src/services/locationBackgroundService.js` to use fetch
- [x] 2.8 Remove `axios` from `package.json` and all imports
- [x] 2.9 Refactor `AuthContext.js` to use React Query for token verification and profile
- [x] 2.10 Refactor `VendorContext.js` to use React Query for products, orders, stats
- [ ] 2.11 Refactor `HomeScreen.js` data loading to use React Query
- [ ] 2.12 Refactor all remaining screens with `useEffect`+`fetch` to use React Query

> Note: 2.11–2.12 deferred — core contexts already use React Query; per-screen refactors can be done incrementally.

## Wave 3 — Storage & icons
- [ ] 3.1 Install `expo-sqlite`
- [ ] 3.2 Replace `AsyncStorage` with `expo-sqlite/localStorage` in `AuthContext.js` (userData only, tokens stay in SecureStore)
- [ ] 3.3 Replace `AsyncStorage` in `NotificationContext.js`
- [ ] 3.4 Replace `AsyncStorage` in `VendorContext.js`
- [ ] 3.5 Replace `AsyncStorage` in `i18n/index.js`
- [x] 3.6 Replace all `react-native-vector-icons` imports with `@expo/vector-icons` across all screens/components
- [ ] 3.7 Remove `@react-native-async-storage/async-storage` from `package.json`

> Note: 3.6 completed early as part of Wave 2 (needed before removing react-native-vector-icons).

## Wave 4 — Navigation migration
- [ ] 4.1 Install `expo-router`
- [ ] 4.2 Create `app/_layout.tsx` root layout with providers (AuthProvider, QueryClientProvider, etc.)
- [ ] 4.3 Create `app/(auth)/` routes: `_layout.tsx`, `welcome.tsx`, `login.tsx`, `register.tsx`
- [ ] 4.4 Create `app/(customer)/` routes: `_layout.tsx`, `index.tsx` (home), `cart.tsx`, `checkout.tsx`, etc.
- [ ] 4.5 Create `app/(vendor)/` routes: `_layout.tsx`, `index.tsx` (dashboard), `orders/`, `products/`
- [ ] 4.6 Create `app/(delivery)/` routes: `_layout.tsx`, `index.tsx` (dashboard), `map.tsx`
- [ ] 4.7 Create `app/(mobility)/` routes: `_layout.tsx`, `index.tsx` (dashboard), `trips/`
- [ ] 4.8 Create `app/(admin)/` routes: `_layout.tsx`, `index.tsx`
- [ ] 4.9 Update imports: `navigation.navigate()` → `router.push()`
- [ ] 4.10 Update `App.js` to use Expo Router instead of NavigationContainer
- [ ] 4.11 Delete old `src/navigation/` directory
- [ ] 4.12 Remove `@react-navigation/*` packages from `package.json`

## Wave 5 — UI & TypeScript
- [ ] 5.1 Install `@expo/ui`
- [ ] 5.2 Replace `src/components/Button.js` with `@expo/ui` button
- [ ] 5.3 Replace `src/components/Input.js` with `@expo/ui` input
- [ ] 5.4 Replace `src/components/SafeContainer.js` with `@expo/ui` Host
- [ ] 5.5 Refactor `src/services/ws.js` → `src/hooks/useWebSocket.ts` as a React hook
- [ ] 5.6 Update `tsconfig.json` with strict mode (`strict: true`, `noImplicitAny: true`)
- [ ] 5.7 Migrate all `.js` files under `src/` to `.tsx`/`.ts` with proper types
- [ ] 5.8 Replace `react-native-chart-kit` with `expo-svg`-based charts or `@expo/ui` charts
- [ ] 5.9 Run full type-check: `npx tsc --noEmit` — zero errors

## Verification
- [ ] V.1 Run `npx expo-doctor` — all green
- [x] V.2 Run `npm test` — all existing tests pass
- [ ] V.3 Run `npx tsc --noEmit` — zero type errors
- [ ] V.4 Build for Android: `npx expo run:android` — compiles successfully
- [ ] V.5 Build for iOS: `npx expo run:ios` — compiles successfully
- [ ] V.6 Manual smoke test: register, login, browse stores, add to cart, checkout flow
