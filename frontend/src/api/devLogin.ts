/**
 * Development-only automatic login.
 *
 * While the accounts are placeholders, typing the same test login after every
 * cleared token is noise. When the dev server runs with both variables below
 * set (put them in frontend/.env.development.local, which git ignores), the
 * app signs in with them by itself whenever there is no valid session.
 *
 *   VITE_DEV_LOGIN_EMAIL=...
 *   VITE_DEV_LOGIN_PASSWORD=...
 *
 * It goes through the real /auth/login, so the backend is unchanged and every
 * request still carries a real token. A production build never does this:
 * import.meta.env.DEV is false there, whatever the variables say.
 */

import type { LoginRequest } from './types';

export function devLoginCredentials(): LoginRequest | null {
  if (!import.meta.env.DEV) {
    return null;
  }
  const email = import.meta.env.VITE_DEV_LOGIN_EMAIL;
  const password = import.meta.env.VITE_DEV_LOGIN_PASSWORD;
  if (!email || !password) {
    return null;
  }
  return { email, password };
}
