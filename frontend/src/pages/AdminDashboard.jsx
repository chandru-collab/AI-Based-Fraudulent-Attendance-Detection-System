import React, { useState, useEffect } from 'react';
import { Shield, Users, AlertOctagon, CheckSquare, BarChart3, Search, Play, Trash, Check, X, Download } from 'lucide-react';
import { Line, Doughnut } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler
} from 'chart.js';
import api from '../services/api';

// Register ChartJS modules
ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, ArcElement, Title, Tooltip, Legend, Filler);

const AdminDashboard = () => {
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [fraudLogs, setFraudLogs] = useState([]);
  const [searchUsername, setSearchUsername] = useState("");
  const [filterSeverity, setFilterSeverity] = useState("");
  
  // Entire logs list state
  const [attendanceLogs, setAttendanceLogs] = useState([]);
  const [attendanceSearch, setAttendanceSearch] = useState("");

  // AI Explainability state
  const [activeAnalysis, setActiveAnalysis] = useState(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);

  const handleAnalyzeFraud = async (attendanceId) => {
    if (!attendanceId) return;
    setAnalysisLoading(true);
    setActiveAnalysis(null);
    try {
      const res = await api.get(`/fraud/analyze/${attendanceId}`);
      setActiveAnalysis(res.data);
    } catch (err) {
      console.error("Failed to run AI fraud audit:", err);
      alert("AI analysis failed or no details available.");
    } finally {
      setAnalysisLoading(false);
    }
  };

  const fetchAdminData = async () => {
    try {
      const [analyticsRes, fraudRes, historyRes] = await Promise.all([
        api.get('/analytics/admin'),
        api.get('/fraud/logs', {
          params: {
            severity: filterSeverity || undefined,
            username: searchUsername || undefined
          }
        }),
        api.get('/attendance/history', {
          params: {
            username: attendanceSearch || undefined
          }
        })
      ]);
      setAnalytics(analyticsRes.data);
      setFraudLogs(fraudRes.data);
      setAttendanceLogs(historyRes.data);
    } catch (err) {
      console.error("Failed to load admin telemetry:", err);
    } finally {
      setLoading(false);
    }
  };

  const [exportRange, setExportRange] = useState("all");
  const [exportFormat, setExportFormat] = useState("csv");
  const [isExporting, setIsExporting] = useState(false);

  useEffect(() => {
    fetchAdminData();
    
    // Connect to WebSocket for real-time updates
    const apiUrl = import.meta.env.VITE_API_URL || (window.location.origin + '/api');
    const wsUrl = apiUrl.replace(/^http/, 'ws').replace(/\/api$/, '') + '/ws/admin';
    
    let ws;
    try {
      ws = new WebSocket(wsUrl);
      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'new_attendance') {
          fetchAdminData(); // Refresh all data when new attendance is marked
        }
      };
    } catch (err) {
      console.error("Failed to connect to real-time WebSocket feed:", err);
    }
    
    return () => {
      if (ws) ws.close();
    };
  }, [searchUsername, filterSeverity, attendanceSearch]);

  const handleExport = async () => {
    setIsExporting(true);
    try {
      let start_date = null;
      if (exportRange === '7d') {
        const d = new Date(); d.setDate(d.getDate() - 7);
        start_date = d.toISOString().split('T')[0];
      } else if (exportRange === '30d') {
        const d = new Date(); d.setDate(d.getDate() - 30);
        start_date = d.toISOString().split('T')[0];
      }
      
      const response = await api.get(`/admin/export/${exportFormat}`, {
        params: start_date ? { start_date } : {},
        responseType: 'blob', // Important for file downloads
      });
      
      const blob = new Blob([response.data], { 
        type: exportFormat === 'csv' ? 'text/csv' : 'application/pdf' 
      });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `attendance_export_${exportRange}.${exportFormat}`);
      document.body.appendChild(link);
      link.click();
      link.parentNode.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Export failed", err);
      alert("Failed to export attendance data.");
    } finally {
      setIsExporting(false);
    }
  };

  const handleResolveAlert = async (logId) => {
    try {
      await api.post(`/fraud/logs/${logId}/resolve`);
      fetchAdminData();
    } catch (err) {
      console.error("Failed to resolve alert:", err);
    }
  };

  if (loading || !analytics) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-12 h-12 border-4 border-brand-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  // Set up chart data configurations
  const timelineChartData = {
    labels: analytics.timeline.map(t => t.date),
    datasets: [
      {
        label: 'Present',
        data: analytics.timeline.map(t => t.present),
        borderColor: 'rgba(52, 211, 153, 0.8)',
        backgroundColor: 'rgba(52, 211, 153, 0.05)',
        fill: true,
        tension: 0.2
      },
      {
        label: 'Flagged / Fraudulent',
        data: analytics.timeline.map(t => t.flagged),
        borderColor: 'rgba(244, 63, 94, 0.8)',
        backgroundColor: 'rgba(244, 63, 94, 0.05)',
        fill: true,
        tension: 0.2
      }
    ]
  };

  const riskBreakdownData = {
    labels: ['Low', 'Medium', 'High', 'Critical'],
    datasets: [
      {
        data: [
          analytics.risk_breakdown.Low,
          analytics.risk_breakdown.Medium,
          analytics.risk_breakdown.High,
          analytics.risk_breakdown.Critical
        ],
        backgroundColor: [
          'rgba(52, 211, 153, 0.7)',  // emerald (low)
          'rgba(245, 158, 11, 0.7)',  // amber (medium)
          'rgba(239, 68, 68, 0.7)',   // red (high)
          'rgba(147, 51, 234, 0.7)'   // purple (critical)
        ],
        borderColor: 'rgba(17, 24, 39, 0.8)',
        borderWidth: 2
      }
    ]
  };

  return (
    <div className="min-h-screen pt-24 px-6 pb-12 max-w-7xl mx-auto space-y-8">
      {/* SECTION 1: Telemetry KPI Summary */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-6">
        <div className="glass p-5 rounded-2xl flex items-center space-x-4">
          <div className="bg-brand-500/10 border border-brand-500/20 p-3.5 rounded-xl text-brand-400">
            <Users className="w-6 h-6" />
          </div>
          <div className="flex flex-col">
            <span className="text-[10px] text-dark-500 font-bold uppercase tracking-wider">Total Users</span>
            <span className="text-2xl font-bold text-white mt-0.5">{analytics.stats.total_students}</span>
          </div>
        </div>
        
        <div className="glass p-5 rounded-2xl flex items-center space-x-4">
          <div className="bg-emerald-500/10 border border-emerald-500/20 p-3.5 rounded-xl text-emerald-400">
            <BarChart3 className="w-6 h-6" />
          </div>
          <div className="flex flex-col">
            <span className="text-[10px] text-dark-500 font-bold uppercase tracking-wider">Present Rate</span>
            <span className="text-2xl font-bold text-white mt-0.5">{analytics.stats.attendance_rate}%</span>
          </div>
        </div>

        <div className="glass p-5 rounded-2xl flex items-center space-x-4">
          <div className="bg-amber-500/10 border border-amber-500/20 p-3.5 rounded-xl text-amber-400">
            <Shield className="w-6 h-6" />
          </div>
          <div className="flex flex-col">
            <span className="text-[10px] text-dark-500 font-bold uppercase tracking-wider">Total Check-ins</span>
            <span className="text-2xl font-bold text-white mt-0.5">{analytics.stats.total_records}</span>
          </div>
        </div>

        <div className="glass p-5 rounded-2xl flex items-center space-x-4">
          <div className="bg-rose-500/10 border border-rose-500/20 p-3.5 rounded-xl text-rose-400">
            <AlertOctagon className="w-6 h-6 animate-pulse" />
          </div>
          <div className="flex flex-col">
            <span className="text-[10px] text-dark-500 font-bold uppercase tracking-wider">Flagged Logs</span>
            <span className="text-2xl font-bold text-rose-400 mt-0.5">{analytics.stats.flagged_records}</span>
          </div>
        </div>

        <div className="glass p-5 rounded-2xl flex items-center space-x-4">
          <div className="bg-purple-500/10 border border-purple-500/20 p-3.5 rounded-xl text-purple-400">
            <CheckSquare className="w-6 h-6" />
          </div>
          <div className="flex flex-col">
            <span className="text-[10px] text-dark-500 font-bold uppercase tracking-wider">Critical Risk</span>
            <span className="text-2xl font-bold text-purple-400 mt-0.5">{analytics.stats.critical_risk_count}</span>
          </div>
        </div>
      </div>

      {/* SECTION 2: Analytics Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2 glass p-6 rounded-3xl shadow-xl">
          <h3 className="text-sm font-bold text-white mb-6">Attendance Trends (Present vs Flagged)</h3>
          <div className="h-64">
            <Line 
              data={timelineChartData}
              options={{
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { labels: { color: '#c1c7cd', font: { size: 10 } } } },
                scales: {
                  y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#64707e', font: { size: 9 } } },
                  x: { grid: { display: false }, ticks: { color: '#64707e', font: { size: 9 } } }
                }
              }}
            />
          </div>
        </div>

        <div className="lg:col-span-1 glass p-6 rounded-3xl shadow-xl flex flex-col justify-between">
          <h3 className="text-sm font-bold text-white mb-6">Risk Profile Allocation</h3>
          <div className="h-48 flex items-center justify-center">
            <Doughnut 
              data={riskBreakdownData}
              options={{
                responsive: true,
                maintainAspectRatio: false,
                plugins: { 
                  legend: { 
                    position: 'bottom', 
                    labels: { color: '#c1c7cd', font: { size: 9 }, boxWidth: 12 } 
                  } 
                }
              }}
            />
          </div>
        </div>
      </div>

      {/* SECTION 3: Real-Time Security Alerts Log Feed */}
      <div className="glass p-6 rounded-3xl shadow-xl space-y-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <h3 className="text-base font-bold text-white flex items-center space-x-2">
            <AlertOctagon className="w-5 h-5 text-rose-500 animate-bounce" />
            <span>Fraudulent Alerts Management</span>
          </h3>
          
          {/* Filters */}
          <div className="flex items-center space-x-3">
            <div className="relative">
              <Search className="w-4 h-4 text-dark-500 absolute left-3 top-2.5" />
              <input
                type="text"
                placeholder="Search student..."
                value={searchUsername}
                onChange={(e) => setSearchUsername(e.target.value)}
                className="bg-dark-900 border border-dark-800 text-xs text-white rounded-lg pl-9 pr-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-brand-500 w-44"
              />
            </div>
            
            <select
              value={filterSeverity}
              onChange={(e) => setFilterSeverity(e.target.value)}
              className="bg-dark-900 border border-dark-800 text-xs text-white rounded-lg px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-brand-500 cursor-pointer"
            >
              <option value="">All Severity</option>
              <option value="Low">Low</option>
              <option value="Medium">Medium</option>
              <option value="High">High</option>
              <option value="Critical">Critical</option>
            </select>
          </div>
        </div>

        {/* Alerts Table */}
        <div className="overflow-x-auto rounded-xl border border-dark-900">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="bg-dark-900 text-dark-400 border-b border-dark-800 uppercase text-[10px] tracking-wider">
                <th className="py-3 px-4">Time</th>
                <th className="py-3 px-4">Student</th>
                <th className="py-3 px-4">Triggered Rule</th>
                <th className="py-3 px-4">Severity</th>
                <th className="py-3 px-4">Details</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {fraudLogs.length === 0 ? (
                <tr>
                  <td colSpan="6" className="py-8 text-center text-dark-500 font-medium">
                    Excellent! No unresolved security warnings.
                  </td>
                </tr>
              ) : (
                fraudLogs.map((log) => (
                  <tr key={log.id} className="border-b border-dark-900/60 hover:bg-dark-900/10 transition">
                    <td className="py-3 px-4 font-mono text-dark-400">
                      {new Date(log.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                    </td>
                    <td className="py-3 px-4 font-bold text-white">{log.username}</td>
                    <td className="py-3 px-4 text-rose-400 font-medium">{log.rule_triggered}</td>
                    <td className="py-3 px-4">
                      <span className={`px-2 py-0.5 rounded-full text-[9px] font-extrabold ${
                        log.severity === 'Critical' ? 'bg-purple-500/15 text-purple-400 border border-purple-500/35' :
                        log.severity === 'High' ? 'bg-rose-500/15 text-rose-400 border border-rose-500/35' :
                        log.severity === 'Medium' ? 'bg-amber-500/15 text-amber-400 border border-amber-500/35' :
                        'bg-brand-500/15 text-brand-400 border border-brand-500/35'
                      }`}>
                        {log.severity}
                      </span>
                    </td>
                    <td className="py-3 px-4 max-w-xs truncate text-dark-300" title={log.details}>
                      {log.details}
                    </td>
                    <td className="py-3 px-4 text-right flex items-center justify-end space-x-2">
                      <button
                        onClick={() => handleAnalyzeFraud(log.attendance_id)}
                        disabled={analysisLoading}
                        className="px-2.5 py-1 text-[10px] font-semibold text-brand-400 bg-brand-500/10 border border-brand-500/20 hover:bg-brand-500/20 rounded-md transition active:scale-95 disabled:opacity-50"
                      >
                        {analysisLoading ? "Analyzing..." : "AI Explain"}
                      </button>
                      <button
                        onClick={() => handleResolveAlert(log.id)}
                        className="px-2.5 py-1 text-[10px] font-semibold text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 hover:bg-emerald-500/20 rounded-md transition active:scale-95"
                      >
                        Resolve
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* SECTION 4: Comprehensive Attendance Archives */}
      <div className="glass p-6 rounded-3xl shadow-xl space-y-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <h3 className="text-base font-bold text-white flex items-center space-x-2">
            <Users className="w-5 h-5 text-brand-400" />
            <span>Global Attendance Archives</span>
          </h3>

          <div className="flex flex-col sm:flex-row items-center gap-3">
            <div className="flex items-center space-x-2 bg-dark-900 border border-dark-800 rounded-lg p-1">
              <select
                value={exportRange}
                onChange={(e) => setExportRange(e.target.value)}
                className="bg-transparent text-[10px] text-white focus:outline-none px-2 py-1 cursor-pointer"
              >
                <option value="all">All Time</option>
                <option value="7d">Last 7 Days</option>
                <option value="30d">Last 30 Days</option>
              </select>
              <select
                value={exportFormat}
                onChange={(e) => setExportFormat(e.target.value)}
                className="bg-transparent text-[10px] text-white focus:outline-none px-2 py-1 cursor-pointer border-l border-dark-800"
              >
                <option value="csv">CSV</option>
                <option value="pdf">PDF</option>
              </select>
              <button
                onClick={handleExport}
                disabled={isExporting}
                className="flex items-center space-x-1 bg-brand-600 hover:bg-brand-500 text-white text-[10px] font-bold px-3 py-1 rounded-md transition disabled:opacity-50"
              >
                <Download className="w-3 h-3" />
                <span>{isExporting ? "Exporting..." : "Export"}</span>
              </button>
            </div>
            
            <div className="relative">
              <Search className="w-4 h-4 text-dark-500 absolute left-3 top-2.5" />
              <input
                type="text"
                placeholder="Search user..."
                value={attendanceSearch}
                onChange={(e) => setAttendanceSearch(e.target.value)}
                className="bg-dark-900 border border-dark-800 text-xs text-white rounded-lg pl-9 pr-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-brand-500 w-44"
              />
            </div>
          </div>
        </div>

        <div className="overflow-x-auto rounded-xl border border-dark-900">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="bg-dark-900 text-dark-400 border-b border-dark-800 uppercase text-[10px] tracking-wider">
                <th className="py-3 px-4">Date/Time</th>
                <th className="py-3 px-4">Student</th>
                <th className="py-3 px-4">Face Check</th>
                <th className="py-3 px-4">GPS Check</th>
                <th className="py-3 px-4">Device Check</th>
                <th className="py-3 px-4">Risk Score</th>
                <th className="py-3 px-4">Status</th>
              </tr>
            </thead>
            <tbody>
              {attendanceLogs.length === 0 ? (
                <tr>
                  <td colSpan="7" className="py-8 text-center text-dark-500 font-medium">
                    No attendance records registered.
                  </td>
                </tr>
              ) : (
                attendanceLogs.map((log) => (
                  <tr key={log.id} className="border-b border-dark-900/60 hover:bg-dark-900/10 transition">
                    <td className="py-3 px-4 text-dark-300">
                      {new Date(log.timestamp).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' })}
                    </td>
                    <td className="py-3 px-4 font-bold text-white">{log.username}</td>
                    <td className="py-3 px-4">
                      {log.face_verified ? (
                        <span className="text-emerald-400 font-medium flex items-center space-x-1"><Check className="w-3.5 h-3.5" /> <span>Match</span></span>
                      ) : (
                        <span className="text-rose-400 font-medium flex items-center space-x-1"><X className="w-3.5 h-3.5" /> <span>Mismatch</span></span>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      {log.location_verified ? (
                        <span className="text-emerald-400 font-medium flex items-center space-x-1"><Check className="w-3.5 h-3.5" /> <span>In campus</span></span>
                      ) : (
                        <span className="text-rose-400 font-medium flex items-center space-x-1"><X className="w-3.5 h-3.5" /> <span>Off campus</span></span>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      {log.device_verified ? (
                        <span className="text-emerald-400 font-medium flex items-center space-x-1"><Check className="w-3.5 h-3.5" /> <span>Trusted</span></span>
                      ) : (
                        <span className="text-rose-400 font-medium flex items-center space-x-1"><X className="w-3.5 h-3.5" /> <span>Modified</span></span>
                      )}
                    </td>
                    <td className="py-3 px-4 font-semibold text-white">
                      {log.fraud_risk_score.toFixed(0)}%
                    </td>
                    <td className="py-3 px-4">
                      <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold ${
                        log.status === 'Present' 
                          ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' 
                          : 'bg-rose-500/10 text-rose-400 border border-rose-500/20 animate-glow'
                      }`}>
                        {log.status}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
      {/* AI Explainability Modal */}
      {activeAnalysis && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-dark-955/80 backdrop-blur-sm animate-fadeIn">
          <div className="glass max-w-lg w-full rounded-3xl p-6 border border-brand-500/30 shadow-2xl relative space-y-6">
            <button
              onClick={() => setActiveAnalysis(null)}
              className="absolute top-4 right-4 p-1.5 rounded-full hover:bg-dark-800 text-dark-400 hover:text-white transition"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="flex items-center space-x-3 pb-3 border-b border-dark-800">
              <div className="bg-brand-500/10 p-2.5 rounded-xl text-brand-400">
                <Shield className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-base font-bold text-white">AI Explainability Telemetry</h3>
                <p className="text-[10px] text-dark-400">Decoded anomaly contribution breakdown</p>
              </div>
            </div>

            <div className="space-y-4">
              <div className="p-3.5 bg-brand-500/5 border border-brand-500/10 rounded-2xl text-xs text-brand-300 leading-relaxed font-medium">
                {activeAnalysis.summary}
              </div>

              {activeAnalysis.risk_factors.length > 0 && (
                <div className="space-y-2">
                  <h4 className="text-xs font-bold text-white uppercase tracking-wider">Identified Risk Factors</h4>
                  <ul className="list-disc pl-4 space-y-1 text-[11px] text-dark-300">
                    {activeAnalysis.risk_factors.map((f, i) => (
                      <li key={i}>{f}</li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="space-y-3">
                <h4 className="text-xs font-bold text-white uppercase tracking-wider">Anomaly Feature Influence</h4>
                <div className="space-y-2.5">
                  {Object.entries(activeAnalysis.feature_importance).map(([feature, weight]) => (
                    <div key={feature} className="space-y-1">
                      <div className="flex justify-between text-[10px] font-semibold text-dark-300">
                        <span>{feature}</span>
                        <span>{(weight * 100).toFixed(0)}%</span>
                      </div>
                      <div className="h-1.5 w-full bg-dark-900 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-brand-500 rounded-full"
                          style={{ width: `${weight * 100}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="pt-2 text-right">
              <button
                onClick={() => setActiveAnalysis(null)}
                className="px-4 py-2 text-xs font-bold text-white bg-brand-600 hover:bg-brand-500 rounded-xl transition shadow-md active:scale-95"
              >
                Close Audit
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AdminDashboard;
