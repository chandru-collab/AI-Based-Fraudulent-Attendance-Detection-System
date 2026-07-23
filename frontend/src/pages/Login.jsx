import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Shield, Lock, Mail, User as UserIcon, AlertCircle } from 'lucide-react';
import api from '../services/api';
import { 
  auth, 
  googleProvider, 
  signInWithPopup, 
  signInWithEmailAndPassword,
  isFirebaseConfigured 
} from '../services/firebase';

const Login = ({ onLoginSuccess }) => {
  const navigate = useNavigate();
  const [usernameOrEmail, setUsernameOrEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [role, setRole] = useState('Student');

  const handleGoogleSignIn = async () => {
    setError('');
    
    if (!isFirebaseConfigured) {
      setError("Firebase Authentication is not configured. Please set up your environment variables in frontend/.env.");
      return;
    }

    setLoading(true);
    try {
      const result = await signInWithPopup(auth, googleProvider);
      const idToken = await result.user.getIdToken();
      
      const res = await api.post('/auth/firebase', {
        id_token: idToken,
        role: 'Student'
      });

      const { access_token, username: finalUsername, role: finalRole } = res.data;
      
      localStorage.setItem('token', access_token);
      const loggedUser = { username: finalUsername, role: finalRole, realRole: finalRole };
      localStorage.setItem('user', JSON.stringify(loggedUser));
      
      onLoginSuccess(loggedUser);
      
      if (['Admin', 'Faculty', 'Super Admin'].includes(finalRole)) {
        navigate('/admin');
      } else {
        navigate('/student');
      }
    } catch (err) {
      console.error("Firebase Google Sign-In failed:", err);
      let friendlyMsg = err.response?.data?.detail || err.message || "Google Sign-In failed. Please try again.";
      if (err.code === 'auth/popup-closed-by-user' || (err.message && err.message.includes('popup-closed-by-user'))) {
        friendlyMsg = "Google Sign-In popup was closed or blocked by your browser. Please try again and make sure popup windows are allowed, or register and log in using your Username/Email and Password below.";
      }
      setError(friendlyMsg);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      let finalUsername = usernameOrEmail;
      let finalRole = role;
      let access_token = '';

      // Check if user entered an email address
      if (usernameOrEmail.includes('@')) {
        if (!isFirebaseConfigured) {
          throw new Error("Firebase Authentication is not configured. To log in with an email account, please set up your environment variables or use a local username.");
        }
        
        // 1. Sign in with Firebase Auth Client
        const userCredential = await signInWithEmailAndPassword(auth, usernameOrEmail, password);
        const idToken = await userCredential.user.getIdToken();
        
        // 2. Authenticate against FastAPI backend with the Firebase ID Token
        const res = await api.post('/auth/firebase', {
          id_token: idToken,
          role: 'Student'
        });
        
        access_token = res.data.access_token;
        finalUsername = res.data.username;
        finalRole = res.data.role;
      } else {
        // Standard Username Login (FastAPI backend authentication)
        const res = await api.post('/auth/login/json', {
          username: usernameOrEmail,
          password
        });
        
        access_token = res.data.access_token;
        finalUsername = res.data.username;
        finalRole = res.data.role;
      }

      localStorage.setItem('token', access_token);
      const loggedUser = { username: finalUsername, role: finalRole, realRole: finalRole };
      localStorage.setItem('user', JSON.stringify(loggedUser));
      
      onLoginSuccess(loggedUser);
      
      if (['Admin', 'Faculty', 'Super Admin'].includes(finalRole)) {
        navigate('/admin');
      } else {
        navigate('/student');
      }
    } catch (err) {
      console.error("Authentication failed:", err);
      setError(err.response?.data?.detail || err.message || "Authentication failed. Double check your credentials.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-12 relative overflow-hidden">
      {/* Decorative Glow */}
      <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-brand-500/10 rounded-full blur-[100px] pointer-events-none" />
      <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-rose-500/5 rounded-full blur-[100px] pointer-events-none" />

      <div className="glass w-full max-w-md p-8 rounded-3xl shadow-2xl relative z-10">
        <div className="flex flex-col items-center space-y-2 mb-8">
          <div className="bg-brand-600 p-3 rounded-2xl text-white shadow-glow mb-2">
            <Shield className="w-8 h-8" />
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Welcome Back</h1>
          <p className="text-sm text-dark-400">Sign in to ShieldAuth AI platform</p>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-rose-500/10 border border-rose-500/20 rounded-xl text-rose-400 text-sm flex items-start space-x-2">
            <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5">

          <div className="flex flex-col space-y-1">
            <label className="text-xs font-semibold text-dark-300 uppercase tracking-wider pl-1">Username or Email</label>
            <div className="relative">
              {usernameOrEmail.includes('@') ? (
                <Mail className="absolute left-4 top-3.5 w-5 h-5 text-dark-500" />
              ) : (
                <UserIcon className="absolute left-4 top-3.5 w-5 h-5 text-dark-500" />
              )}
              <input
                type="text"
                required
                value={usernameOrEmail}
                onChange={(e) => setUsernameOrEmail(e.target.value)}
                placeholder="Enter username or email"
                className="w-full input-primary !pl-12"
              />
            </div>
          </div>

          <div className="flex flex-col space-y-1">
            <label className="text-xs font-semibold text-dark-300 uppercase tracking-wider pl-1">Password</label>
            <div className="relative">
              <Lock className="absolute left-4 top-3.5 w-5 h-5 text-dark-500" />
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full input-primary !pl-12"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full btn-primary py-3 mt-2 font-semibold tracking-wide flex items-center justify-center"
          >
            {loading ? "Authenticating..." : "Sign In"}
          </button>
        </form>

        <div className="relative my-6 text-center">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-dark-800"></div>
          </div>
          <span className="relative px-3 bg-dark-950 text-xs text-dark-500 font-semibold uppercase tracking-wider">or continue with</span>
        </div>

        <button
          type="button"
          onClick={handleGoogleSignIn}
          className="w-full py-2.5 bg-white hover:bg-gray-100 text-gray-900 font-semibold rounded-2xl transition flex items-center justify-center space-x-3 active:scale-98 shadow-md"
        >
          <svg className="w-5 h-5 shrink-0" viewBox="0 0 24 24">
            <path
              fill="#4285F4"
              d="M23.745 12.27c0-.7-.06-1.4-.19-2.07H12v3.9h6.69c-.29 1.5-.14 2.68-2.04 3.95v3.28h3.29c1.92-1.77 3.03-4.38 3.03-7.06z"
            />
            <path
              fill="#34A853"
              d="M12 24c3.24 0 5.97-1.08 7.96-2.91l-3.29-2.54c-.9.6-2.07.97-3.38.97-3.22 0-5.95-2.17-6.93-5.09H3.04v2.6C5.02 21.02 8.24 24 12 24z"
            />
            <path
              fill="#FBBC05"
              d="M5.07 14.43c-.25-.7-.39-1.4-.39-2.18s.14-1.48.39-2.18V7.47H3.04C2.18 9.18 1.69 11.08 1.69 13s.49 3.82 1.35 5.53l3.03-2.6-1-1.5z"
            />
            <path
              fill="#EA4335"
              d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.96 1.19 15.24 0 12 0 8.24 0 5.02 2.98 3.04 6.9L6.07 9.5c.98-2.92 3.71-4.75 6.93-4.75z"
            />
          </svg>
          <span className="text-xs">Sign In with Google</span>
        </button>

        <div className="mt-8 text-center text-sm text-dark-400">
          Don't have an account?{" "}
          <Link to="/register" className="text-brand-400 hover:text-brand-300 font-semibold transition">
            Create an Account
          </Link>
        </div>
      </div>
    </div>
  );
};

export default Login;
