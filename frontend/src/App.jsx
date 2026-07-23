import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Navbar from './components/Navbar';
import Login from './pages/Login';
import Register from './pages/Register';
import StudentDashboard from './pages/StudentDashboard';
import AdminDashboard from './pages/AdminDashboard';
import GeofenceManagement from './pages/GeofenceManagement';
import PendingReviews from './pages/PendingReviews';
import api from './services/api';
import { auth, signOut } from './services/firebase';

const App = () => {
  const [user, setUser] = useState(() => {
    const cached = localStorage.getItem('user');
    if (cached) {
      try {
        return JSON.parse(cached);
      } catch (e) {
        // ignore
      }
    }
    return null;
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const checkAuthAndRun = async () => {
      const token = localStorage.getItem('token');
      if (token) {
        try {
          const res = await api.get('/auth/me');
          const { username, role } = res.data;
          const cachedUser = localStorage.getItem('user') ? JSON.parse(localStorage.getItem('user')) : null;
          const currentRole = cachedUser && cachedUser.username === username ? cachedUser.role : role;
          const freshUser = { username, role: currentRole, realRole: role };
          localStorage.setItem('user', JSON.stringify(freshUser));
          setUser(freshUser);
        } catch (err) {
          console.log("Current token invalid/expired, clearing auth...");
          localStorage.removeItem('token');
          localStorage.removeItem('user');
          setUser(null);
        }
      } else {
        setUser(null);
      }
      setLoading(false);
    };
    
    checkAuthAndRun();
  }, []);

  const handleToggleRole = () => {
    if (!user || !['Admin', 'Faculty', 'Super Admin'].includes(user.realRole)) {
      console.warn("Attempted to toggle role without administrative credentials!");
      return;
    }
    const newRole = user.role === 'Student' ? user.realRole : 'Student';
    const updatedUser = { ...user, role: newRole };
    setUser(updatedUser);
    localStorage.setItem('user', JSON.stringify(updatedUser));
  };

  const handleLogout = async () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    if (auth) {
      try {
        await signOut(auth);
      } catch (err) {
        console.error("Firebase sign out failed:", err);
      }
    }
    setUser(null);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-dark-950 flex items-center justify-center">
        <div className="w-10 h-10 border-4 border-brand-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <Router>
      <div className="min-h-screen bg-dark-950 text-dark-100 selection:bg-brand-500 selection:text-white">
        {/* Render Navbar only if logged in */}
        {user && <Navbar user={user} onLogout={handleLogout} onToggleRole={handleToggleRole} />}
        
        <Routes>
          {/* Public Routes */}
          <Route 
            path="/login" 
            element={
              user ? (
                ['Admin', 'Faculty', 'Super Admin'].includes(user.role) ? (
                  <Navigate to="/admin" replace />
                ) : (
                  <Navigate to="/student" replace />
                )
              ) : (
                <Login onLoginSuccess={(u) => setUser(u)} />
              )
            } 
          />
          <Route 
            path="/register" 
            element={
              user ? (
                ['Admin', 'Faculty', 'Super Admin'].includes(user.role) ? (
                  <Navigate to="/admin" replace />
                ) : (
                  <Navigate to="/student" replace />
                )
              ) : (
                <Register />
              )
            } 
          />

          {/* Protected Portal Routes */}
          <Route 
            path="/student" 
            element={
              user ? (
                user.role === 'Student' ? (
                  <StudentDashboard />
                ) : (
                  <Navigate to="/admin" replace />
                )
              ) : (
                <Navigate to="/login" replace />
              )
            } 
          />
          
          <Route 
            path="/admin" 
            element={
              user ? (
                ['Admin', 'Faculty', 'Super Admin'].includes(user.role) ? (
                  <AdminDashboard />
                ) : (
                  <Navigate to="/student" replace />
                )
              ) : (
                <Navigate to="/login" replace />
              )
            } 
          />
          
          <Route 
            path="/admin/geofences" 
            element={
              user ? (
                ['Admin', 'Super Admin'].includes(user.role) ? (
                  <GeofenceManagement />
                ) : (
                  <Navigate to="/admin" replace />
                )
              ) : (
                <Navigate to="/login" replace />
              )
            } 
          />

          <Route 
            path="/admin/reviews" 
            element={
              user ? (
                ['Admin', 'Faculty', 'Super Admin'].includes(user.role) ? (
                  <PendingReviews />
                ) : (
                  <Navigate to="/admin" replace />
                )
              ) : (
                <Navigate to="/login" replace />
              )
            } 
          />

          {/* Redirect Root Route */}
          <Route 
            path="/" 
            element={
              user ? (
                ['Admin', 'Faculty', 'Super Admin'].includes(user.role) ? (
                  <Navigate to="/admin" replace />
                ) : (
                  <Navigate to="/student" replace />
                )
              ) : (
                <Navigate to="/login" replace />
              )
            } 
          />

          {/* Fallback Catch */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    </Router>
  );
};

export default App;
