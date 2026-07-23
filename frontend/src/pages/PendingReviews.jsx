import React, { useState, useEffect } from 'react';
import { ShieldAlert, CheckCircle2, XCircle, AlertTriangle, Cpu, UserX, Clock, Image as ImageIcon } from 'lucide-react';
import api from '../services/api';

const API_BASE_URL = 'http://localhost:8000'; // Make sure this matches the backend

export default function PendingReviews() {
  const [reviews, setReviews] = useState([]);
  const [loading, setLoading] = useState(true);
  const [processingId, setProcessingId] = useState(null);

  const fetchReviews = async () => {
    setLoading(true);
    try {
      const res = await api.get('/attendance/pending');
      setReviews(res.data);
    } catch (err) {
      console.error("Failed to fetch pending reviews:", err);
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchReviews();
  }, []);

  const handleAction = async (id, action) => {
    setProcessingId(id);
    let reason = null;
    if (action === "Reject") {
      reason = prompt("Optional: Provide a reason for rejection (e.g. 'Invalid Photo')") || "Policy Violation";
    }
    try {
      const res = await api.post(`/attendance/${id}/review`, { action, reason });
      if (res.status === 200) {
        setReviews(reviews.filter(r => r.id !== id));
      }
    } catch (err) {
      console.error(`Failed to ${action} review:`, err);
      alert(`Error: ${err.response?.data?.detail || err.message}`);
    }
    setProcessingId(null);
  };

  return (
    <div className="min-h-screen bg-dark-950 text-white p-6 md:p-10 pt-24">
      <div className="max-w-7xl mx-auto space-y-8">
        
        {/* Header */}
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-amber-400 to-rose-400 flex items-center gap-3">
              <ShieldAlert className="text-amber-400" size={32} />
              Quarantine Dashboard (XAI)
            </h1>
            <p className="text-dark-400 mt-2">Manual review queue for high-risk and anomalous attendance check-ins.</p>
          </div>
          <button 
            onClick={fetchReviews}
            className="btn-secondary px-4 py-2 rounded-xl bg-dark-800 hover:bg-dark-700 transition"
          >
            Refresh Queue
          </button>
        </div>

        {/* Content */}
        {loading ? (
          <div className="flex justify-center py-20">
            <div className="w-12 h-12 border-4 border-amber-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : reviews.length === 0 ? (
          <div className="bg-dark-900 border border-dark-800 rounded-3xl p-16 text-center text-dark-400">
            <CheckCircle2 size={48} className="mx-auto mb-4 text-emerald-500 opacity-50" />
            <h2 className="text-xl font-medium text-white mb-2">No Pending Reviews</h2>
            <p>All check-ins are verified and processed.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            {reviews.map(record => (
              <div key={record.id} className="bg-dark-900 border border-dark-800 rounded-3xl overflow-hidden shadow-xl flex flex-col">
                
                {/* Card Header */}
                <div className="p-5 border-b border-dark-800 bg-dark-900 flex justify-between items-center">
                  <div>
                    <h3 className="text-lg font-bold text-white flex items-center gap-2">
                      <UserX size={18} className="text-rose-400" />
                      {record.username}
                    </h3>
                    <p className="text-xs text-dark-400 flex items-center gap-1 mt-1">
                      <Clock size={12} />
                      {new Date(record.timestamp + 'Z').toLocaleString()}
                    </p>
                  </div>
                  <div className="bg-rose-500/10 border border-rose-500/20 text-rose-400 px-3 py-1 rounded-full text-xs font-bold flex items-center gap-1">
                    <AlertTriangle size={14} />
                    Risk: {record.fraud_risk_score.toFixed(0)}%
                  </div>
                </div>

                {/* Card Body - 2 Columns */}
                <div className="flex flex-col sm:flex-row p-5 gap-6 flex-grow">
                  
                  {/* Photo Column */}
                  <div className="sm:w-1/3 flex flex-col items-center justify-center bg-dark-950 rounded-2xl border border-dark-800 p-2 relative overflow-hidden min-h-[200px]">
                    {record.image_url ? (
                      <img 
                        src={`${API_BASE_URL}${record.image_url}`} 
                        alt={`Check-in snapshot of ${record.username}`}
                        className="w-full h-full object-cover rounded-xl"
                        onError={(e) => {
                          e.target.style.display = 'none';
                          e.target.nextSibling.style.display = 'flex';
                        }}
                      />
                    ) : (
                      <div className="flex flex-col items-center justify-center text-dark-500">
                        <ImageIcon size={32} className="mb-2 opacity-50" />
                        <span className="text-xs font-medium">No Image Saved</span>
                      </div>
                    )}
                    <div className="absolute inset-0 flex flex-col items-center justify-center text-dark-500 bg-dark-950 hidden">
                      <ImageIcon size={32} className="mb-2 opacity-50" />
                      <span className="text-xs font-medium">Image Not Found</span>
                    </div>
                  </div>

                  {/* XAI Column */}
                  <div className="sm:w-2/3 flex flex-col justify-between">
                    <div>
                      <h4 className="text-sm font-bold text-white flex items-center gap-2 mb-3">
                        <Cpu size={16} className="text-brand-400" />
                        XAI Explainer Summary
                      </h4>
                      <p className="text-sm text-dark-300 leading-relaxed mb-4 bg-dark-950 p-3 rounded-xl border border-dark-800">
                        {record.xai_explanation.summary}
                      </p>
                      
                      {record.xai_explanation.risk_factors.length > 0 && (
                        <div className="space-y-2">
                          <span className="text-xs font-bold text-dark-400 uppercase tracking-wider">Triggered Anomalies</span>
                          <ul className="space-y-1.5">
                            {record.xai_explanation.risk_factors.map((factor, idx) => (
                              <li key={idx} className="text-xs text-rose-300 flex items-start gap-2 bg-rose-500/5 px-2 py-1.5 rounded-lg border border-rose-500/10">
                                <span className="mt-0.5">•</span>
                                <span>{factor}</span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                {/* Card Footer Actions */}
                <div className="p-4 bg-dark-950 border-t border-dark-800 flex gap-3">
                  <button 
                    disabled={processingId === record.id}
                    onClick={() => handleAction(record.id, 'Approve')}
                    className="flex-1 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 hover:border-emerald-500 transition py-2.5 rounded-xl font-bold flex items-center justify-center gap-2 disabled:opacity-50"
                  >
                    <CheckCircle2 size={18} />
                    {processingId === record.id ? 'Processing...' : 'Approve Check-in'}
                  </button>
                  <button 
                    disabled={processingId === record.id}
                    onClick={() => handleAction(record.id, 'Reject')}
                    className="flex-1 bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/30 hover:border-rose-500 transition py-2.5 rounded-xl font-bold flex items-center justify-center gap-2 disabled:opacity-50"
                  >
                    <XCircle size={18} />
                    Reject as Fraud
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
