import React, { useState, useEffect, useCallback } from 'react';
import { Camera, MapPin, Tablet, AlertTriangle, ShieldCheck, CheckCircle2, History, AlertCircle, TrendingUp, Calendar } from 'lucide-react';
import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
} from 'chart.js';
import api from '../services/api';
import FaceCamera from '../components/FaceCamera';

// Register Chart.js components
ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, Filler);

// ─── Helpers ──────────────────────────────────────────────────────────────────
/** Parse a UTC timestamp string from the backend and convert to local time */
const parseUTCTimestamp = (ts) => {
  if (!ts) return null;
  // Backend returns ISO strings without 'Z'; append it so JS treats them as UTC
  const str = ts.endsWith('Z') || ts.includes('+') ? ts : ts + 'Z';
  return new Date(str);
};

/** Format timestamp to a human-friendly local date/time string */
const formatTimestamp = (ts) => {
  const d = parseUTCTimestamp(ts);
  if (!d || isNaN(d)) return '—';
  return d.toLocaleString('en-IN', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit', hour12: true
  });
};

/** Haversine distance in metres between two lat/lon pairs */
const haversineMeters = (lat1, lon1, lat2, lon2) => {
  const R = 6371000;
  const toRad = (x) => (x * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a = Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
};

const API_SIGNING_SECRET = import.meta.env.VITE_API_SIGNING_SECRET || "super_secret_payload_signing_key_2026";

/** Generate HMAC-SHA256 signature using native Web Crypto API */
const generateHMACSignature = async (message, secret) => {
  const encoder = new TextEncoder();
  const keyBuffer = encoder.encode(secret);
  const messageBuffer = encoder.encode(message);
  
  const cryptoKey = await window.crypto.subtle.importKey(
    "raw",
    keyBuffer,
    { name: "HMAC", hash: { name: "SHA-256" } },
    false,
    ["sign"]
  );
  
  const signatureBuffer = await window.crypto.subtle.sign(
    "HMAC",
    cryptoKey,
    messageBuffer
  );
  
  return Array.from(new Uint8Array(signatureBuffer))
    .map(b => b.toString(16).padStart(2, "0"))
    .join("");
};

const StudentDashboard = () => {
  const [isFaceRegistered, setIsFaceRegistered] = useState(true);
  const [faceCheckLoading, setFaceCheckLoading] = useState(true);

  // Campus GPS config fetched from backend
  const [campus, setCampus] = useState(null); // { name, latitude, longitude, radius_meters }
  
  // Checking in state
  const [gpsCoords, setGpsCoords] = useState(null);
  const [gpsError, setGpsError] = useState("");
  const [isInsideCampus, setIsInsideCampus] = useState(null); // true / false / null
  const [checkingIn, setCheckingIn] = useState(false);
  const [checkInResult, setCheckInResult] = useState(null);
  const [checkInError, setCheckInError] = useState("");

  // Active Liveness Action Sequence
  const LIVENESS_SEQUENCE = ["look_straight", "look_left", "look_right", "smile"];
  const [sequenceStep, setSequenceStep] = useState(0);
  const [autoVerifying, setAutoVerifying] = useState(false);
  const [isVirtualCamera, setIsVirtualCamera] = useState(false);
  const [cooldown, setCooldown] = useState(false);
  const [flashColor, setFlashColor] = useState("red");
  const [cameraActive, setCameraActive] = useState(false);
  
  const ACTION_LABELS = {
    "look_straight": "Please Look Straight",
    "smile": "Please Smile",
    "look_left": "Look Slightly Left",
    "look_right": "Look Slightly Right"
  };

  const activeAction = LIVENESS_SEQUENCE[sequenceStep] || "smile";
  const [sequenceFailed, setSequenceFailed] = useState(false);

  // Audio prompt when action changes
  useEffect(() => {
    if (activeAction && !checkInResult && !checkingIn && !sequenceFailed && sequenceStep < LIVENESS_SEQUENCE.length) {
      const text = ACTION_LABELS[activeAction];
      if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.rate = 0.9;
        window.speechSynthesis.speak(utterance);
      }
    }
  }, [activeAction, checkInResult, checkingIn, sequenceFailed, sequenceStep]);

  // Timeout if an action takes too long (> 15 seconds)
  useEffect(() => {
    if (checkingIn || sequenceStep >= LIVENESS_SEQUENCE.length || checkInResult || sequenceFailed || cooldown || !cameraActive) return;
    
    const timer = setTimeout(() => {
      setCheckInError(`Verification timed out. Could not detect: ${ACTION_LABELS[activeAction]}`);
      setSequenceFailed(true);
      if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();
        window.speechSynthesis.speak(new SpeechSynthesisUtterance("Timeout. Please try again."));
      }
    }, 15000);
    
    return () => clearTimeout(timer);
  }, [sequenceStep, checkingIn, checkInResult, activeAction, sequenceFailed, cooldown, cameraActive]);

  // Analytics and logs state
  const [stats, setStats] = useState({ total_records: 0, present_records: 0, flagged_records: 0, attendance_rate: 0 });
  const [history, setHistory] = useState([]);
  const [chartData, setChartData] = useState(null);


  // Load campus config from backend
  const fetchCampusConfig = useCallback(async () => {
    try {
      const res = await api.get('/config/campus');
      setCampus(res.data);
      return res.data;
    } catch {
      // Fallback if endpoint not available
      const fallback = { name: 'College Campus', latitude: 12.8231, longitude: 80.0444, radius_meters: 300 };
      setCampus(fallback);
      return fallback;
    }
  }, []);

  // Recompute inside/outside whenever coords or campus changes
  useEffect(() => {
    if (gpsCoords && campus) {
      const dist = haversineMeters(gpsCoords.lat, gpsCoords.lon, campus.latitude, campus.longitude);
      setIsInsideCampus(dist <= campus.radius_meters);
    } else {
      setIsInsideCampus(null);
    }
  }, [gpsCoords, campus]);

  // Load user data and verification dependencies
  const checkFaceRegistration = async () => {
    setFaceCheckLoading(true);
    try {
      const res = await api.get('/face/status');
      setIsFaceRegistered(res.data.registered);
    } catch (err) {
      console.error("Failed to check face status:", err);
      setIsFaceRegistered(false);
    } finally {
      setFaceCheckLoading(false);
    }
  };

  const fetchDashboardData = async () => {
    try {
      const [statsRes, historyRes] = await Promise.all([
        api.get('/analytics/student'),
        api.get('/attendance/history')
      ]);
      setStats(statsRes.data.stats);
      
      // Chart data setup
      const scores = statsRes.data.scores_trend;
      if (scores && scores.length > 0) {
        setChartData({
          labels: scores.map(s => formatTimestamp(s.timestamp)),
          datasets: [
            {
              label: 'Fraud Risk Score',
              data: scores.map(s => s.score),
              borderColor: 'rgba(115, 117, 255, 0.8)',
              backgroundColor: 'rgba(115, 117, 255, 0.1)',
              tension: 0.3,
              fill: true,
              pointBackgroundColor: 'rgba(244, 63, 94, 0.9)',
            }
          ]
        });
      } else {
        setChartData(null);
      }

      setHistory(historyRes.data);
    } catch (err) {
      console.error("Failed to fetch dashboard data:", err);
    }
  };

  const [locationMode, setLocationMode] = useState('inside'); // 'inside', 'outside', 'real'

  const updateLocation = useCallback((mode, campusData) => {
    const c = campusData || campus;
    setLocationMode(mode);
    setCheckInError("");
    if (mode === 'inside' && c) {
      // Use exact campus coordinates so it registers as inside
      setGpsCoords({ lat: c.latitude, lon: c.longitude });
      setGpsError("");
    } else if (mode === 'outside') {
      // A location clearly outside the campus (offset ~5km)
      setGpsCoords({ lat: (c?.latitude ?? 12.8231) + 0.05, lon: (c?.longitude ?? 80.0444) + 0.05 });
      setGpsError("");
    } else if (mode === 'real') {
      setGpsCoords(null);
      setIsInsideCampus(null);
      if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
          (position) => {
            setGpsCoords({
              lat: position.coords.latitude,
              lon: position.coords.longitude
            });
            setGpsError("");
          },
          (err) => {
            console.error("GPS error:", err);
            setGpsError("Failed to obtain GPS location. Enable browser location access or use simulation.");
          }
        );
      } else {
        setGpsError("Geolocation is not supported by your browser.");
      }
    }
  }, [campus]);

  useEffect(() => {
    const init = async () => {
      // Pre-detect Virtual Camera on load to avoid latency during check-in
      try {
        if (navigator.mediaDevices && navigator.mediaDevices.enumerateDevices) {
          const devices = await navigator.mediaDevices.enumerateDevices();
          const videoDevices = devices.filter(d => d.kind === 'videoinput');
          const virtualKeywords = ['virtual', 'obs', 'manycam', 'splitcam', 'vcam', 'software', 'streamer', 'broadcast'];
          const hasVirtual = videoDevices.some(d => {
            const label = d.label ? d.label.toLowerCase() : '';
            return virtualKeywords.some(keyword => label.includes(keyword));
          });
          setIsVirtualCamera(hasVirtual);
        }
      } catch (e) {
        console.warn("Media device enumeration failed on load:", e);
      }

      const campusData = await fetchCampusConfig();
      checkFaceRegistration();
      fetchDashboardData();
      updateLocation('inside', campusData); // Default to inside campus simulation
    };
    init();
  }, []);

  // Handle Face Registration Submit
  const handleRegisterFace = async (base64Img) => {
    setCheckInError("");
    setCheckingIn(true);
    try {
      await api.post('/face/register', { image: base64Img });
      setIsFaceRegistered(true);
      fetchDashboardData();
    } catch (err) {
      setCheckInError(err.response?.data?.detail || "Face registration failed. Try again.");
    } finally {
      setCheckingIn(false);
    }
  };

  // Compile Fingerprint and browser meta
  const getDeviceMeta = () => {
    const ua = navigator.userAgent;
    let browser = "Unknown Browser";
    let os = "Unknown OS";

    if (ua.indexOf("Chrome") > -1) browser = "Chrome";
    else if (ua.indexOf("Firefox") > -1) browser = "Firefox";
    else if (ua.indexOf("Safari") > -1) browser = "Safari";
    else if (ua.indexOf("Edge") > -1) browser = "Edge";

    if (ua.indexOf("Windows") > -1) os = "Windows";
    else if (ua.indexOf("Mac") > -1) os = "MacOS";
    else if (ua.indexOf("Linux") > -1) os = "Linux";
    else if (ua.indexOf("Android") > -1) os = "Android";
    else if (ua.indexOf("iPhone") > -1 || ua.indexOf("iPad") > -1) os = "iOS";

    // Standard hash key representing browser state
    const fingerprint = btoa(`${ua}-${screen.width}x${screen.height}-${navigator.language}`).slice(0, 16);

    return { browser, os, fingerprint };
  };

  // Handle Check-in Capture
  const handleCheckIn = async (base64Img) => {
    if (!gpsCoords) {
      setCheckInError("Cannot check in without GPS coordinates. Allow location access.");
      return;
    }
    setCheckingIn(true);
    setCheckInError("");
    setCheckInResult(null);

    // 1. Detect Virtual Camera (Pre-fetched on load to avoid high latency)
    // isVirtualCamera is read directly from state

    // 2. Detect DevTools open
    const devtoolsThreshold = 160;
    const isDevToolsOpen = (window.outerWidth - window.innerWidth > devtoolsThreshold) || 
                           (window.outerHeight - window.innerHeight > devtoolsThreshold);

    const device = getDeviceMeta();
    const timestamp = Math.floor(Date.now() / 1000).toString();
    
    const virtualCamVal = isVirtualCamera ? "1" : "0";
    const devtoolsVal = isDevToolsOpen ? "1" : "0";
    const latStr = gpsCoords.lat.toFixed(6);
    const lonStr = gpsCoords.lon.toFixed(6);
    const message = `${latStr}|${lonStr}|${device.fingerprint}|${timestamp}|${virtualCamVal}|${devtoolsVal}`;

    try {
      const signature = await generateHMACSignature(message, API_SIGNING_SECRET);

      const res = await api.post('/attendance/mark', {
        image: base64Img,
        latitude: gpsCoords.lat,
        longitude: gpsCoords.lon,
        device_fingerprint: device.fingerprint,
        browser: device.browser,
        os: device.os,
        ip_address: "127.0.0.1",  // Backend resolves real ip, this is a fallback parameter
        signature: signature,
        client_timestamp: timestamp,
        is_virtual_camera: isVirtualCamera,
        is_devtools_open: isDevToolsOpen,
        action_type: activeAction,
        flash_color: flashColor
      });

      setCheckInResult(res.data);
      fetchDashboardData();
    } catch (err) {
      console.error(err);
      setCheckInError(err.response?.data?.detail || "Attendance check-in failed.");
    } finally {
      setCheckingIn(false);
    }
  };

  const handleAutoCapture = async (base64Img) => {
    if (checkingIn || sequenceStep >= LIVENESS_SEQUENCE.length || autoVerifying || sequenceFailed || cooldown) return;
    
    setAutoVerifying(true);
    try {
      const res = await api.post('/face/verify_liveness_action', {
        image: base64Img,
        action_type: activeAction,
        flash_color: flashColor
      });
      if (res.data.verified) {
        if (sequenceStep === LIVENESS_SEQUENCE.length - 1) {
          // Last action verified, trigger check-in
          setSequenceStep(prev => prev + 1);
          handleCheckIn(base64Img);
        } else {
          // Select next random flash color for the upcoming step
          const colors = ["red", "green", "blue"];
          const nextColor = colors[Math.floor(Math.random() * colors.length)];
          setFlashColor(nextColor);

          // Move to next step with a 2-second cooldown to let the user adjust
          setCooldown(true);
          setSequenceStep(prev => prev + 1);
          setTimeout(() => {
            setCooldown(false);
          }, 2000);
        }
      }
    } catch (err) {
      console.error("Auto capture verification error:", err);
    } finally {
      setAutoVerifying(false);
    }
  };

  if (faceCheckLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-12 h-12 border-4 border-brand-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen pt-24 px-6 pb-12 max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-3 gap-8">
      {/* LEFT COLUMN: Check-in Actions */}
      <div className="lg:col-span-1 space-y-6">
        {!isFaceRegistered ? (
          // 1. Initial Face Registration
          <div className="glass p-6 rounded-3xl border border-brand-500/20 shadow-xl flex flex-col items-center">
            <h2 className="text-lg font-bold text-white mb-2 flex items-center space-x-2">
              <Camera className="w-5 h-5 text-brand-400" />
              <span>Register Your Face</span>
            </h2>
            <p className="text-xs text-dark-400 text-center mb-6">
              You must register a face reference snapshot before you can mark your attendance. Position your face in the center of the camera.
            </p>
            {checkInError && (
              <div className="mb-4 w-full p-3 bg-rose-500/10 border border-rose-500/20 rounded-xl text-rose-400 text-xs flex items-center space-x-2">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{checkInError}</span>
              </div>
            )}
            <FaceCamera onCapture={handleRegisterFace} buttonText="Register Face" onStreamActiveChange={setCameraActive} />
            {checkingIn && <span className="text-xs text-brand-400 mt-2">Uploading reference...</span>}
          </div>
        ) : (
          // 2. Verified Attendance Check-in
          <div className="glass p-6 rounded-3xl shadow-xl flex flex-col items-center">
            <h2 className="text-lg font-bold text-white mb-2 flex items-center space-x-2">
              <ShieldCheck className="w-5 h-5 text-brand-400" />
              <span>AI Verification Check-in</span>
            </h2>
            <p className="text-xs text-dark-400 text-center mb-6">
              Take a snapshot. GPS, device fingerprint, and facial recognition are processed dynamically.
            </p>
            <button
              onClick={() => setIsFaceRegistered(false)}
              className="text-[10px] text-brand-400 hover:text-brand-300 font-bold mb-4 flex items-center space-x-1 transition active:scale-95 bg-brand-500/10 border border-brand-500/20 py-1.5 px-3 rounded-lg"
            >
              <span>Update Registered Face Reference</span>
            </button>

            {/* GPS Simulation Selector */}
            <div className="mb-4 w-full flex flex-col space-y-1">
              <div className="grid grid-cols-3 gap-1 bg-dark-900/60 p-1 rounded-xl border border-dark-800 text-[10px]">
                <button
                  type="button"
                  onClick={() => updateLocation('inside')}
                  className={`py-1.5 px-2 rounded-lg font-semibold transition ${
                    locationMode === 'inside' ? 'bg-brand-600 text-white shadow-sm' : 'text-dark-400 hover:text-white'
                  }`}
                >
                  Inside Campus
                </button>
                <button
                  type="button"
                  onClick={() => updateLocation('outside')}
                  className={`py-1.5 px-2 rounded-lg font-semibold transition ${
                    locationMode === 'outside' ? 'bg-rose-600/80 text-white shadow-sm' : 'text-dark-400 hover:text-white'
                  }`}
                >
                  Outside Campus
                </button>
                <button
                  type="button"
                  onClick={() => updateLocation('real')}
                  className={`py-1.5 px-2 rounded-lg font-semibold transition ${
                    locationMode === 'real' ? 'bg-dark-800 text-white shadow-sm' : 'text-dark-400 hover:text-white'
                  }`}
                >
                  Real GPS
                </button>
              </div>
            </div>

            {/* GPS Status Display */}
            {gpsError ? (
              <div className="mb-4 w-full p-3 bg-rose-500/10 border border-rose-500/20 rounded-xl text-rose-400 text-xs flex items-center space-x-2">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{gpsError}</span>
              </div>
            ) : gpsCoords ? (
              <div className={`mb-4 w-full p-3 rounded-xl text-xs flex items-center justify-between border ${
                isInsideCampus === true
                  ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-300'
                  : isInsideCampus === false
                  ? 'bg-rose-500/10 border-rose-500/20 text-rose-300'
                  : 'bg-brand-500/10 border-brand-500/20 text-brand-300'
              }`}>
                <div className="flex items-center space-x-2">
                  <MapPin className="w-4 h-4" />
                  <div className="flex flex-col">
                    <span className="font-semibold">
                      {isInsideCampus === true ? '✅ Inside Campus' :
                       isInsideCampus === false ? '🚫 Outside Campus' : 'Locating...'}
                    </span>
                    <span className="text-[10px] opacity-70">
                      {locationMode === 'inside' ? `Sim: ${campus?.name ?? 'Campus'}` :
                       locationMode === 'outside' ? 'Sim: Remote location' : 'Real GPS active'}
                    </span>
                  </div>
                </div>
                <span className="text-[10px] font-mono opacity-60">
                  {gpsCoords.lat.toFixed(4)}, {gpsCoords.lon.toFixed(4)}
                </span>
              </div>
            ) : (
              <div className="mb-4 w-full p-3 bg-amber-500/10 border border-amber-500/20 rounded-xl text-amber-400 text-xs flex items-center space-x-2">
                <div className="w-2.5 h-2.5 bg-amber-500 rounded-full animate-ping" />
                <span>Requesting coordinates...</span>
              </div>
            )}

            {checkInError && (
              <div className="mb-4 w-full p-3 bg-rose-500/10 border border-rose-500/20 rounded-xl text-rose-400 text-xs flex items-center space-x-2">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{checkInError}</span>
              </div>
            )}

            <div className={`mb-4 w-full p-3 rounded-xl text-center font-bold flex flex-col items-center transition-all duration-300 border ${
              sequenceFailed || checkInError
                ? 'bg-rose-500/10 border-rose-500/20 text-rose-400'
                : checkInResult
                ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
                : cooldown
                ? 'bg-amber-500/10 border-amber-500/20 text-amber-400 animate-pulse'
                : 'bg-blue-500/10 border-blue-500/20 text-blue-400'
            }`}>
              <span className="text-[10px] uppercase tracking-wider opacity-70 mb-1">
                {sequenceFailed || checkInError
                  ? "Verification Failed"
                  : checkInResult
                  ? "Check-in Complete"
                  : cooldown
                  ? "Prepare Next Action"
                  : (sequenceStep >= LIVENESS_SEQUENCE.length
                      ? "Liveness Verified"
                      : `Liveness Check Sequence (${sequenceStep + 1}/${LIVENESS_SEQUENCE.length})`)}
              </span>
              <span className="text-lg">
                {sequenceFailed
                  ? "Sequence Failed"
                  : checkInError
                  ? "Attendance Failed"
                  : checkInResult
                  ? `Success: ${checkInResult.status}`
                  : cooldown
                  ? `Get ready: ${ACTION_LABELS[activeAction]}`
                  : (sequenceStep >= LIVENESS_SEQUENCE.length
                      ? "Processing Attendance..."
                      : ACTION_LABELS[activeAction])}
              </span>
            </div>

            {(sequenceFailed || checkInError) && (
              <button 
                onClick={() => {
                  setCheckInError("");
                  setSequenceFailed(false);
                  setSequenceStep(0);
                  setCheckInResult(null);
                  setCooldown(false);
                  setCameraActive(false);
                  const colors = ["red", "green", "blue"];
                  setFlashColor(colors[Math.floor(Math.random() * colors.length)]);
                }}
                className="mb-4 w-full py-2 bg-dark-900 border border-dark-800 hover:border-brand-500 rounded-lg text-white font-medium transition active:scale-98"
              >
                Restart Check-in Sequence
              </button>
            )}

            {checkInResult && (
              <div className={`mb-6 w-full p-4 rounded-xl text-xs flex flex-col space-y-2 border ${
                checkInResult.status === 'Present' 
                  ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' 
                  : checkInResult.status === 'Pending Review'
                  ? 'bg-amber-500/10 border-amber-500/20 text-amber-400'
                  : 'bg-rose-500/10 border-rose-500/20 text-rose-400'
              }`}>
                <div className="flex items-center space-x-2">
                  <CheckCircle2 className="w-5 h-5 shrink-0" />
                  <span className="font-bold text-sm">Status: {checkInResult.status}</span>
                </div>
                <div className="grid grid-cols-2 gap-1 pt-2 border-t border-dark-800 text-[10px] text-dark-300">
                  <div>Face: {checkInResult.face_verified ? "Verified" : "Failed"}</div>
                  <div>Location: {checkInResult.location_verified ? "In boundary" : "Outside"}</div>
                  <div>Device: {checkInResult.device_verified ? "Recognized" : "Unrecognized"}</div>
                  <div className="font-bold">Risk: {checkInResult.fraud_risk_score.toFixed(0)}%</div>
                </div>
                {checkInResult.status !== 'Present' && (
                  <button 
                    onClick={() => {
                      setCheckInResult(null);
                      setSequenceFailed(false);
                      setSequenceStep(0);
                      setCooldown(false);
                      setCameraActive(false);
                      const colors = ["red", "green", "blue"];
                      setFlashColor(colors[Math.floor(Math.random() * colors.length)]);
                    }}
                    className="mt-3 w-full py-2 bg-dark-900 border border-dark-800 hover:border-brand-500 rounded-lg text-white font-medium transition"
                  >
                    Retry Check-in Sequence
                  </button>
                )}
              </div>
            )}

            <FaceCamera 
              onCapture={handleCheckIn} 
              buttonText={sequenceStep >= LIVENESS_SEQUENCE.length ? "Check-in Complete" : "Mark Attendance"} 
              autoCaptureMode={sequenceStep < LIVENESS_SEQUENCE.length && !checkInResult && !sequenceFailed && !cooldown} 
              onAutoCapture={handleAutoCapture}
              autoCaptureIntervalMs={400}
              flashColor={flashColor}
              onStreamActiveChange={setCameraActive}
            />
            {checkingIn && <span className="text-xs text-brand-400 mt-2">Analyzing biometric & travel profiles...</span>}
          </div>
        )}
      </div>

      {/* RIGHT COLUMN: Stats, Chart, History */}
      <div className="lg:col-span-2 space-y-6">
        {/* Row 1: KPI Stats */}
        <div className="grid grid-cols-3 gap-4">
          <div className="glass p-5 rounded-2xl flex flex-col">
            <span className="text-xs text-dark-500 font-bold uppercase tracking-wider">Attendance Rate</span>
            <span className="text-2xl font-bold text-white mt-1">{stats.attendance_rate}%</span>
            <span className="text-[10px] text-dark-400 mt-2 flex items-center space-x-1">
              <Calendar className="w-3.5 h-3.5 text-brand-500" />
              <span>Active log cycles</span>
            </span>
          </div>
          <div className="glass p-5 rounded-2xl flex flex-col">
            <span className="text-xs text-dark-500 font-bold uppercase tracking-wider">Present Count</span>
            <span className="text-2xl font-bold text-emerald-400 mt-1">{stats.present_records}</span>
            <span className="text-[10px] text-dark-400 mt-2">Verified successful sessions</span>
          </div>
          <div className="glass p-5 rounded-2xl flex flex-col">
            <span className="text-xs text-dark-500 font-bold uppercase tracking-wider">Flagged Warnings</span>
            <span className="text-2xl font-bold text-rose-400 mt-1">{stats.flagged_records}</span>
            <span className="text-[10px] text-dark-400 mt-2">Failed verification logs</span>
          </div>
        </div>

        {/* Row 2: Behavioral Risk Chart */}
        {chartData && (
          <div className="glass p-6 rounded-3xl shadow-xl">
            <h3 className="text-sm font-bold text-white mb-4 flex items-center space-x-2">
              <TrendingUp className="w-4 h-4 text-brand-400" />
              <span>Behavioral Risk Trend (Last 7 Logs)</span>
            </h3>
            <div className="h-44 flex items-center justify-center">
              <Line 
                data={chartData} 
                options={{
                  responsive: true,
                  maintainAspectRatio: false,
                  plugins: { legend: { display: false } },
                  scales: {
                    y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#64707e', font: { size: 9 } }, min: 0, max: 100 },
                    x: { grid: { display: false }, ticks: { color: '#64707e', font: { size: 9 } } }
                  }
                }} 
              />
            </div>
          </div>
        )}

        {/* Row 3: History log table */}
        <div className="glass p-6 rounded-3xl shadow-xl">
          <h3 className="text-sm font-bold text-white mb-4 flex items-center space-x-2">
            <History className="w-4 h-4 text-brand-400" />
            <span>Attendance Logs</span>
          </h3>

          <div className="overflow-x-auto rounded-xl border border-dark-900">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="bg-dark-900 text-dark-400 border-b border-dark-800 uppercase text-[10px] tracking-wider">
                  <th className="py-3 px-4">Date/Time</th>
                  <th className="py-3 px-4">Verification</th>
                  <th className="py-3 px-4">Risk</th>
                  <th className="py-3 px-4">Status</th>
                </tr>
              </thead>
              <tbody>
                {history.length === 0 ? (
                  <tr>
                    <td colSpan="4" className="py-8 text-center text-dark-500 font-medium">
                      No attendance logged yet. Use verification panel.
                    </td>
                  </tr>
                ) : (
                  history.map((h) => (
                    <tr key={h.id} className="border-b border-dark-900/60 hover:bg-dark-900/20 transition">
                      <td className="py-3.5 px-4 font-medium text-white">
                        {formatTimestamp(h.timestamp)}
                      </td>
                      <td className="py-3.5 px-4">
                        <div className="flex items-center space-x-3 text-[10px] text-dark-400">
                          <span className={h.face_verified ? "text-emerald-400" : "text-rose-400"} title="Face Verification">Face</span>
                          <span className={h.location_verified ? "text-emerald-400" : "text-rose-400"} title="GPS Geofence">GPS</span>
                          <span className={h.device_verified ? "text-emerald-400" : "text-rose-400"} title="Device Fingerprint">Device</span>
                        </div>
                      </td>
                      <td className="py-3.5 px-4 font-semibold text-dark-200">
                        {h.fraud_risk_score.toFixed(0)}%
                      </td>
                      <td className="py-3.5 px-4">
                        <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold ${
                          h.status === 'Present' 
                            ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' 
                            : h.status === 'Pending Review'
                            ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                            : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                        }`}>
                          {h.status}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};

export default StudentDashboard;
