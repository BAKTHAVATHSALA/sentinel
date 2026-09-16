import { initializeApp } from "firebase/app";
import { getAuth } from "firebase/auth";

/**
 * Real Firebase project config for sentinel-ai-builder-cup (V1 Authoritative
 * Ruling Part 1: Firebase email/password authentication). A Firebase web
 * apiKey is not a secret -- it identifies the project to Firebase's client
 * SDK; access is governed by Firebase Auth + Firestore Security Rules, not
 * by hiding this value (see README's Authentication section). Overridable
 * via VITE_FIREBASE_* for a different Firebase project without a code change.
 */
const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY ?? "AIzaSyCb2GMJ-WPkC7NXnM2ZDrn6bRRwkH7nBWA",
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN ?? "sentinel-ai-builder-cup.firebaseapp.com",
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID ?? "sentinel-ai-builder-cup",
  appId: import.meta.env.VITE_FIREBASE_APP_ID ?? "1:209692631228:web:023bf145aca61a0f3bf0b9",
};

export const firebaseApp = initializeApp(firebaseConfig);
export const firebaseAuth = getAuth(firebaseApp);
