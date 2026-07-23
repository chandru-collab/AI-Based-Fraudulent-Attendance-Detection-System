import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Shield, Bell, LogOut, User as UserIcon, Check } from 'lucide-react';
import api from '../services/api';

const Navbar = ({ user, onLogout, onToggleRole }) => {
  const navigate = useNavigate();
  const [notifications, setNotifications] = useState([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);

  const fetchNotifications = async () => {
    try {
      const res = await api.get('/notifications');
      setNotifications(res.data);
      setUnreadCount(res.data.filter(n => !n.is_read).length);
    } catch (err) {
      console.error("Failed to fetch notifications:", err);
    }
  };

  useEffect(() => {
    if (user) {
      fetchNotifications();
      // Poll every 10 seconds for real-time security alerts
      const interval = setInterval(fetchNotifications, 10000);
      return () => clearInterval(interval);
    }
  }, [user]);

  const handleMarkAsRead = async (id) => {
    try {
      await api.post(`/notifications/${id}/read`);
      fetchNotifications();
    } catch (err) {
      console.error(err);
    }
  };

  const handleMarkAllRead = async () => {
    try {
      await api.post('/notifications/read-all');
      fetchNotifications();
    } catch (err) {
      console.error(err);
    }
  };

  const handleLogoutClick = () => {
    onLogout();
    navigate('/login');
  };

  return (
    <nav className="glass fixed top-0 left-0 w-full z-50 px-6 py-4 flex items-center justify-between shadow-lg">
      <div className="flex items-center space-x-3">
        <div className="bg-brand-600 p-2 rounded-xl text-white flex items-center justify-center animate-pulse">
          <Shield className="w-6 h-6" />
        </div>
        <Link to="/" className="text-xl font-bold tracking-tight text-white flex items-center">
          <span className="text-gradient">ShieldAuth</span>
          <span className="ml-1 text-sm bg-brand-500/20 text-brand-400 px-2 py-0.5 rounded-full border border-brand-500/30">AI</span>
        </Link>
      </div>

      <div className="flex items-center space-x-6">
        {/* Toggle Mode Button */}
        {user && ['Admin', 'Faculty', 'Super Admin'].includes(user.realRole) && (
          <button 
            onClick={onToggleRole}
            className="px-3.5 py-2 rounded-xl border border-brand-500/35 bg-brand-500/10 hover:bg-brand-500/20 text-brand-400 hover:text-brand-300 text-xs font-bold transition-all active:scale-95 shadow-glow"
          >
            {user.role === 'Student' ? 'Switch to Admin Panel' : 'Switch to Student Panel'}
          </button>
        )}

        {/* Notification Bell Widget */}
        <div className="relative">
          <button 
            onClick={() => setShowDropdown(!showDropdown)}
            className="relative p-2.5 rounded-xl hover:bg-dark-900 border border-dark-800 text-dark-300 hover:text-white transition-all"
          >
            <Bell className="w-5 h-5" />
            {unreadCount > 0 && (
              <span className="absolute -top-1 -right-1 bg-rose-500 text-white text-[10px] font-bold w-5 h-5 flex items-center justify-center rounded-full border-2 border-dark-950">
                {unreadCount}
              </span>
            )}
          </button>

          {showDropdown && (
            <div className="absolute right-0 mt-3 w-80 glass rounded-2xl shadow-2xl border border-dark-800 overflow-hidden z-50">
              <div className="px-4 py-3 border-b border-dark-800 flex items-center justify-between">
                <span className="font-semibold text-white text-sm">Security Alerts</span>
                {unreadCount > 0 && (
                  <button 
                    onClick={handleMarkAllRead}
                    className="text-xs text-brand-400 hover:text-brand-300 font-medium transition"
                  >
                    Mark all read
                  </button>
                )}
              </div>
              <div className="max-h-64 overflow-y-auto">
                {notifications.length === 0 ? (
                  <div className="px-4 py-6 text-center text-dark-500 text-sm">
                    No active notifications
                  </div>
                ) : (
                  notifications.map((n) => (
                    <div 
                      key={n.id} 
                      className={`px-4 py-3 border-b border-dark-900 flex flex-col space-y-1 hover:bg-dark-900/40 transition ${!n.is_read ? 'bg-brand-500/5' : ''}`}
                    >
                      <div className="flex items-start justify-between">
                        <span className={`text-xs font-bold uppercase ${
                          n.type === 'alert' ? 'text-rose-400' : n.type === 'warning' ? 'text-amber-400' : 'text-brand-400'
                        }`}>
                          {n.type}
                        </span>
                        {!n.is_read && (
                          <button 
                            onClick={() => handleMarkAsRead(n.id)}
                            className="p-0.5 hover:bg-dark-800 rounded-md text-brand-400"
                            title="Mark as read"
                          >
                            <Check className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>
                      <p className="text-sm text-dark-200">{n.message}</p>
                      <span className="text-[10px] text-dark-500">
                        {new Date(n.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                      </span>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </div>

        {/* User Card */}
        <div className="flex items-center space-x-3 border-l border-dark-800 pl-6">
          <div className="bg-dark-900 border border-dark-800 p-2 rounded-xl text-brand-400">
            <UserIcon className="w-4 h-4" />
          </div>
          <div className="flex flex-col">
            <span className="text-sm font-semibold text-white leading-tight">{user.username}</span>
            <span className="text-[11px] text-dark-500 font-medium">{user.role}</span>
          </div>
        </div>

        {/* Logout */}
        <button 
          onClick={handleLogoutClick}
          className="p-2.5 rounded-xl border border-dark-800 hover:border-rose-500/30 hover:bg-rose-500/10 text-dark-300 hover:text-rose-400 transition-all active:scale-95"
          title="Logout"
        >
          <LogOut className="w-5 h-5" />
        </button>
      </div>
    </nav>
  );
};

export default Navbar;
