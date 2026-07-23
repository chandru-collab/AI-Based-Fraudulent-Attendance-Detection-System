import { initializeApp } from 'firebase/app';
import { 
  getAuth, 
  GoogleAuthProvider, 
  signInWithPopup, 
  signInWithEmailAndPassword, 
  createUserWithEmailAndPassword,
  signOut
} from 'firebase/auth';

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
};

let auth = null;
let googleProvider = null;
let isFirebaseConfigured = false;

if (firebaseConfig.apiKey && firebaseConfig.apiKey !== 'your-firebase-api-key') {
  try {
    const app = initializeApp(firebaseConfig);
    auth = getAuth(app);
    googleProvider = new GoogleAuthProvider();
    // Prompt the user to select an account each time they sign in with Google
    googleProvider.setCustomParameters({
      prompt: 'select_account'
    });
    isFirebaseConfigured = true;
    console.log("Firebase client SDK initialized successfully.");
  } catch (err) {
    console.error("Failed to initialize Firebase SDK:", err);
  }
} else {
  console.warn(
    "Firebase environment variables are missing. Firebase Auth will run in simulated demo mode.\n" +
    "To use real Firebase Auth, please set VITE_FIREBASE_API_KEY and other variables in frontend/.env."
  );
}

export { 
  auth, 
  googleProvider, 
  signInWithPopup, 
  signInWithEmailAndPassword, 
  createUserWithEmailAndPassword,
  signOut,
  isFirebaseConfigured 
};
