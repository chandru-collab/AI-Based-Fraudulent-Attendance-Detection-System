import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Shield, Lock, User as UserIcon, Mail, Users, AlertCircle, CheckCircle } from 'lucide-react';
import api from '../services/api';
import { 
  auth, 
  createUserWithEmailAndPassword, 
  signInWithEmailAndPassword,
  isFirebaseConfigured 
} from '../services/firebase';

const Register = () => {
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    setLoading(true);

    try {
      if (isFirebaseConfigured) {
        let idToken;
        try {
          // 1. Create User in Firebase
          const userCredential = await createUserWithEmailAndPassword(auth, email, password);
          idToken = await userCredential.user.getIdToken();
        } catch (fbErr) {
          if (fbErr.code === 'auth/email-already-in-use') {
            console.log("Email already exists in Firebase. Verifying password to link account locally...");
            // Verify password using sign-in
            const userCredential = await signInWithEmailAndPassword(auth, email, password);
            idToken = await userCredential.user.getIdToken();
          } else {
            throw fbErr;
          }
        }
        
        // 2. Register/Link in our FastAPI Database
        await api.post('/auth/firebase', {
          id_token: idToken,
          role: 'Student',
          username
        });
      } else {
        // Fallback to local DB registration
        await api.post('/auth/register', {
          username,
          email,
          password,
          role: 'Student'
        });
      }

      setSuccess("Account created successfully! Redirecting to login...");
      setTimeout(() => {
        navigate('/login');
      }, 2000);
    } catch (err) {
      console.error("Registration failed:", err);
      setError(err.response?.data?.detail || err.message || "Registration failed. Please review input fields.");
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
          <h1 className="text-2xl font-bold text-white tracking-tight">Create Account</h1>
          <p className="text-sm text-dark-400">Join ShieldAuth AI smart monitoring system</p>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-rose-500/10 border border-rose-500/20 rounded-xl text-rose-400 text-sm flex items-start space-x-2">
            <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        {success && (
          <div className="mb-6 p-4 bg-emerald-500/10 border border-emerald-500/20 rounded-xl text-emerald-400 text-sm flex items-start space-x-2">
            <CheckCircle className="w-5 h-5 shrink-0 mt-0.5" />
            <span>{success}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="flex flex-col space-y-1">
            <label className="text-xs font-semibold text-dark-300 uppercase tracking-wider pl-1">Username</label>
            <div className="relative">
              <UserIcon className="absolute left-4 top-3.5 w-5 h-5 text-dark-500" />
              <input
                type="text"
                required
                minLength={3}
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="johndoe"
                className="w-full input-primary !pl-12"
              />
            </div>
          </div>

          <div className="flex flex-col space-y-1">
            <label className="text-xs font-semibold text-dark-300 uppercase tracking-wider pl-1">Email Address</label>
            <div className="relative">
              <Mail className="absolute left-4 top-3.5 w-5 h-5 text-dark-500" />
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="john@example.com"
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
                minLength={6}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Min. 6 characters"
                className="w-full input-primary !pl-12"
              />
            </div>
          </div>



          <button
            type="submit"
            disabled={loading}
            className="w-full btn-primary py-3 mt-4 font-semibold tracking-wide flex items-center justify-center"
          >
            {loading ? "Creating Account..." : "Create Account"}
          </button>
        </form>

        <div className="mt-8 text-center text-sm text-dark-400">
          Already have an account?{" "}
          <Link to="/login" className="text-brand-400 hover:text-brand-300 font-semibold transition">
            Sign In
          </Link>
        </div>
      </div>
    </div>
  );
};

export default Register;
