import React, { useRef, useState, useEffect } from 'react';
import { Camera, RefreshCw, AlertCircle } from 'lucide-react';

const FaceCamera = ({ onCapture, buttonText = "Capture Face", autoCaptureMode = false, onAutoCapture = null, autoCaptureIntervalMs = 800, flashColor = null, onStreamActiveChange = null }) => {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  
  const setVideoRef = React.useCallback((node) => {
    videoRef.current = node;
    if (node !== null && streamRef.current) {
      node.srcObject = streamRef.current;
      node.play().catch(e => console.error("Error playing video stream:", e));
    }
  }, []);
  
  const [streamActive, setStreamActive] = useState(false);
  const [cameraError, setCameraError] = useState("");
  const [capturedImage, setCapturedImage] = useState(null);
  const [isSimulated, setIsSimulated] = useState(false);

  useEffect(() => {
    if (onStreamActiveChange) {
      onStreamActiveChange(streamActive);
    }
  }, [streamActive, onStreamActiveChange]);

  // Start webcam stream with fallback constraints for compatibility
  const startCamera = async () => {
    setCameraError("");
    setCapturedImage(null);
    
    if (isSimulated) {
      setStreamActive(true);
      return;
    }
    
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      console.warn("Webcam access not supported in this context (HTTPS required unless on localhost).");
      setCameraError("Webcam access not supported. You must use HTTPS or localhost to access the camera.");
      // setIsSimulated(true);
      // setStreamActive(true);
      return;
    }

    const constraintList = [
      { video: { width: { ideal: 480 }, height: { ideal: 480 }, facingMode: "user" } },
      { video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: "user" } },
      { video: { facingMode: "user" } },
      { video: true }
    ];

    let stream = null;
    let lastError = null;

    for (const constraints of constraintList) {
      try {
        stream = await navigator.mediaDevices.getUserMedia(constraints);
        if (stream) break;
      } catch (err) {
        console.warn("Camera constraints failed:", constraints, err);
        lastError = err;
      }
    }

    if (stream) {
      streamRef.current = stream;
      setStreamActive(true);
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.play().catch(e => console.error("Error playing video stream:", e));
      }
    } else {
      console.error("All camera constraints failed:", lastError);
      
      if (lastError?.name === 'NotFoundError') {
        console.warn("No camera device found.");
        setCameraError("No camera device found on this computer.");
        // setIsSimulated(true);
        // setStreamActive(true);
        return;
      }
      
      // Provide specific error message based on error type
      let errorMsg = "Webcam access denied. Please grant permissions and reload.";
      if (lastError?.name === 'NotAllowedError') {
        errorMsg = "Camera access denied. Please allow camera permissions in your browser settings and try again.";
      } else if (lastError?.name === 'NotReadableError') {
        errorMsg = "Camera is in use by another application. Please close other apps using the camera.";
      }
      
      setCameraError(errorMsg);
    }
  };

  // Stop camera stream
  const stopCamera = () => {
    if (isSimulated) {
      setStreamActive(false);
      return;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
      setStreamActive(false);
    }
  };

  useEffect(() => {
    startCamera();
    return () => {
      stopCamera();
    };
  }, [isSimulated]);

  const grabFrame = () => {
    if (isSimulated) {
      return "mock_face_image_data";
    }
    if (videoRef.current && canvasRef.current && streamActive) {
      const video = videoRef.current;
      const canvas = canvasRef.current;
      const context = canvas.getContext('2d');
      
      const size = Math.min(video.videoWidth, video.videoHeight);
      if (size === 0) return null;
      
      const startX = (video.videoWidth - size) / 2;
      const startY = (video.videoHeight - size) / 2;
      
      canvas.width = 320;
      canvas.height = 320;
      
      context.drawImage(
        video, 
        startX, startY, size, size, // source coords
        0, 0, 320, 320             // dest coords
      );
      
      // Inject slight tint of the active flash color onto the captured frame
      if (flashColor) {
        context.fillStyle = 
          flashColor === 'red' ? 'rgba(244, 63, 94, 0.12)' :
          flashColor === 'green' ? 'rgba(16, 185, 129, 0.12)' :
          flashColor === 'blue' ? 'rgba(59, 130, 246, 0.12)' :
          'transparent';
        context.fillRect(0, 0, 320, 320);
      }
      
      return canvas.toDataURL('image/jpeg', 0.9);
    }
    return null;
  };

  // Auto capture interval
  useEffect(() => {
    let intervalId;
    if (autoCaptureMode && streamActive && onAutoCapture) {
      intervalId = setInterval(() => {
        const frame = isSimulated ? "mock_face_image_data" : grabFrame();
        if (frame) {
          onAutoCapture(frame);
        }
      }, autoCaptureIntervalMs);
    }
    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, [autoCaptureMode, streamActive, onAutoCapture, autoCaptureIntervalMs, isSimulated, flashColor]);

  const handleCapture = () => {
    const dataUrl = isSimulated ? "mock_face_image_data" : grabFrame();
    if (dataUrl) {
      setCapturedImage(dataUrl);
      onCapture(dataUrl);
      stopCamera();
    }
  };

  const handleRetake = () => {
    if (isSimulated) {
      setCapturedImage(null);
      setStreamActive(true);
    } else {
      startCamera();
    }
  };

  return (
    <div className="flex flex-col items-center space-y-4 w-full">
      <style>{`
        @keyframes scan {
          0% { top: 0%; }
          50% { top: 100%; }
          100% { top: 0%; }
        }
      `}</style>
      
      {/* Video Canvas Container */}
      <div className={`relative w-64 h-64 rounded-full overflow-hidden border-4 transition-all duration-500 bg-dark-900 flex items-center justify-center ${
        flashColor === 'red' ? 'border-rose-500 shadow-[0_0_25px_rgba(244,63,94,0.7)] bg-rose-950/10' :
        flashColor === 'green' ? 'border-emerald-500 shadow-[0_0_25px_rgba(16,185,129,0.7)] bg-emerald-950/10' :
        flashColor === 'blue' ? 'border-blue-500 shadow-[0_0_25px_rgba(59,130,246,0.7)] bg-blue-950/10' :
        'border-brand-500 shadow-glow'
      }`}>
        {/* Subtle Screen Tint for Active Flash-Liveness */}
        {flashColor && !capturedImage && (
          <div className={`absolute inset-0 pointer-events-none mix-blend-color transition-all duration-500 ${
            flashColor === 'red' ? 'bg-rose-500/15' :
            flashColor === 'green' ? 'bg-emerald-500/15' :
            flashColor === 'blue' ? 'bg-blue-500/15' :
            ''
          }`} />
        )}

        {isSimulated ? (
          capturedImage ? (
            <div className="flex flex-col items-center justify-center space-y-2 text-emerald-400">
              <span className="text-[10px] font-mono tracking-widest uppercase opacity-70">Captured</span>
              <span className="text-xs font-bold font-mono">SIMULATED FEED</span>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center p-6 text-center space-y-4 w-full h-full relative">
              {/* Animated Radar Scanning Grid */}
              <div className="relative w-28 h-28 flex items-center justify-center rounded-full border border-brand-500/30 overflow-hidden bg-brand-950/20">
                <div 
                  className="absolute inset-x-0 h-0.5 bg-brand-400/80 shadow-[0_0_8px_rgba(115,117,255,0.8)] pointer-events-none" 
                  style={{
                    top: '0%',
                    animation: 'scan 2s linear infinite',
                  }}
                />
                <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(115,117,255,0.06)_1px,transparent_1px)] bg-[size:12px_12px]" />
                <svg className="w-16 h-16 text-brand-400/70 animate-pulse" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15.182 15.182a4.5 4.5 0 01-6.364 0M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <div className="flex flex-col space-y-0.5">
                <span className="text-xs font-bold text-brand-400 tracking-wider">MOCK CAMERA</span>
                <span className="text-[9px] text-dark-500 font-medium">Bypassing biometric sensors</span>
              </div>
            </div>
          )
        ) : cameraError ? (
          <div className="p-4 text-center text-rose-400 flex flex-col items-center space-y-3">
            <AlertCircle className="w-8 h-8" />
            <span className="text-xs font-semibold">{cameraError}</span>
            <button
              type="button"
              onClick={() => {
                setIsSimulated(true);
                setCameraError("");
                setStreamActive(true);
              }}
              className="bg-brand-600 hover:bg-brand-700 text-white text-[11px] font-bold px-3 py-1.5 rounded-lg transition active:scale-95 shadow-md"
            >
              Use Simulated Camera (Dev Mode)
            </button>
          </div>
        ) : capturedImage ? (
          <img 
            src={capturedImage} 
            alt="Captured face" 
            className="w-full h-full object-cover transform scale-x-[-1]" 
          />
        ) : (
          <video
            ref={setVideoRef}
            autoPlay
            playsInline
            muted
            className="w-full h-full object-cover transform scale-x-[-1]"
          />
        )}
        
        {/* Alignment Overlay */}
        {!capturedImage && !cameraError && !isSimulated && (
          <div className="absolute inset-0 border-[16px] border-dark-950/40 pointer-events-none rounded-full flex items-center justify-center">
            <div className="w-48 h-48 border border-dashed border-brand-400/40 rounded-full" />
          </div>
        )}
      </div>

      {/* Action Controls */}
      <div className="flex flex-col items-center space-y-2">
        <div className="flex items-center space-x-3 w-full justify-center">
          {capturedImage ? (
            <button
              type="button"
              onClick={handleRetake}
              className="flex items-center space-x-2 bg-dark-900 border border-dark-800 hover:border-brand-500/50 hover:bg-dark-800 text-white py-2 px-4 rounded-xl transition"
            >
              <RefreshCw className="w-4 h-4" />
              <span className="text-sm font-medium">Retake photo</span>
            </button>
          ) : cameraError ? (
            <button
              type="button"
              onClick={startCamera}
              className="flex items-center space-x-2 bg-brand-500 hover:bg-brand-600 text-white py-2 px-4 rounded-xl transition"
            >
              <Camera className="w-4 h-4" />
              <span className="text-sm font-medium">Retry Camera</span>
            </button>
          ) : (
            !autoCaptureMode && (
              <button
                type="button"
                onClick={handleCapture}
                disabled={!streamActive}
                className="btn-primary flex items-center space-x-2 disabled:opacity-50"
              >
                <Camera className="w-4 h-4" />
                <span className="text-sm font-medium">{buttonText}</span>
              </button>
            )
          )}
        </div>
        
        {isSimulated && !capturedImage && (
          <button
            type="button"
            onClick={() => {
              setIsSimulated(false);
              setCapturedImage(null);
              startCamera();
            }}
            className="text-[10px] text-dark-400 hover:text-brand-400 transition underline mt-1"
          >
            Switch to Live Camera
          </button>
        )}
      </div>

      <canvas ref={canvasRef} className="hidden" />
    </div>
  );
};

export default FaceCamera;
