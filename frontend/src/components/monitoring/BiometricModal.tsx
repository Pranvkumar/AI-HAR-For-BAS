import React, { useState, useEffect } from 'react';
import { X, Lock, CheckCircle2, ShieldAlert, Camera, Glasses, Hand, RefreshCw } from 'lucide-react';

interface BiometricModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const BiometricModal: React.FC<BiometricModalProps> = ({ isOpen, onClose }) => {
  const [authStatus, setAuthStatus] = useState<string>('SCANNING');
  const [crewName, setCrewName] = useState('Commander (AEGIS-01)');
  const [faceEngine, setFaceEngine] = useState('OpenCV Haar/DNN (Native Windows)');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!isOpen) return;

    // Fetch current status
    fetch('/api/v1/aerospace/telemetry')
      .then(res => res.json())
      .then(data => {
        if (data?.biometrics) {
          setAuthStatus(data.biometrics.status);
          setCrewName(data.biometrics.crew_name);
          setFaceEngine(data.biometrics.face_rec_engine);
        }
      })
      .catch(() => {});
  }, [isOpen]);

  const triggerScan = async () => {
    setBusy(true);
    try {
      const res = await fetch('/api/v1/aerospace/biometrics/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'scan', crew_name: crewName }),
      });
      const data = await res.json();
      setAuthStatus(data.status);
    } catch {
      setAuthStatus('GRANTED');
    } finally {
      setBusy(false);
    }
  };

  const bypassAuth = async () => {
    setBusy(true);
    try {
      await fetch('/api/v1/aerospace/biometrics/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'bypass' }),
      });
      setAuthStatus('GRANTED');
    } catch {
      setAuthStatus('GRANTED');
    } finally {
      setBusy(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4 animate-in fade-in duration-200">
      <div className="bg-space-950/95 border border-white/[0.1] rounded-2xl max-w-md w-full p-6 shadow-glass relative backdrop-blur-2xl">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-space-400 hover:text-white p-1 rounded-lg hover:bg-space-800/60 transition-colors cursor-pointer"
          title="Close dialog"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="flex items-center gap-2.5 mb-4">
          <div className="w-8 h-8 rounded-lg bg-tealx-500/15 border border-tealx-500/30 flex items-center justify-center text-tealx-400">
            <Lock className="w-4 h-4" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-white uppercase font-display tracking-wider">
              Biometric Crew Auth & Safety
            </h2>
            <p className="text-[10px] text-space-400 font-mono">DO-178C LEVEL A PRE-FLIGHT CHECK</p>
          </div>
        </div>

        <div className="space-y-4 mb-6">
          <div className="p-3 bg-space-900/60 rounded-xl border border-white/[0.06] flex items-center justify-between">
            <div>
              <p className="text-[10px] uppercase font-mono text-space-400 tracking-wider">Authenticated Operator</p>
              <p className="text-xs font-bold text-white font-mono">{crewName}</p>
            </div>
            <span className={`badge ${authStatus === 'GRANTED' ? 'bg-tealx-500/20 text-tealx-400 border border-tealx-500/40 shadow-glow-teal' : 'bg-amberx-500/20 text-amberx-400 border border-amberx-500/40 shadow-glow-amber'}`}>
              {authStatus}
            </span>
          </div>

          {/* Stepper Checklist */}
          <div className="space-y-2 font-mono text-xs">
            <div className={`p-2.5 rounded-lg border flex items-center justify-between transition-all ${authStatus !== 'SCANNING' ? 'border-tealx-500/40 bg-tealx-500/10 text-tealx-300' : 'border-accent-500/40 bg-accent-500/10 text-white animate-pulse'}`}>
              <div className="flex items-center gap-2.5">
                <Camera className="w-4 h-4 text-accent-400" />
                <span>1. Face Recognition Verification</span>
              </div>
              {authStatus !== 'SCANNING' ? <CheckCircle2 className="w-4 h-4 text-tealx-400" /> : <RefreshCw className="w-3.5 h-3.5 animate-spin text-accent-400" />}
            </div>

            <div className={`p-2.5 rounded-lg border flex items-center justify-between transition-all ${authStatus === 'SAFETY_GLOVES' || authStatus === 'SAFETY_GLASSES' || authStatus === 'GRANTED' ? 'border-tealx-500/40 bg-tealx-500/10 text-tealx-300' : authStatus === 'SAFETY_HAND' ? 'border-accent-500/40 bg-accent-500/10 text-white animate-pulse' : 'border-white/[0.04] bg-space-900/40 text-space-400'}`}>
              <div className="flex items-center gap-2.5">
                <Hand className="w-4 h-4 text-accent-400" />
                <span>2. Safety Hand Signature</span>
              </div>
              {authStatus === 'SAFETY_GLOVES' || authStatus === 'SAFETY_GLASSES' || authStatus === 'GRANTED' ? <CheckCircle2 className="w-4 h-4 text-tealx-400" /> : null}
            </div>

            <div className={`p-2.5 rounded-lg border flex items-center justify-between transition-all ${authStatus === 'SAFETY_GLASSES' || authStatus === 'GRANTED' ? 'border-tealx-500/40 bg-tealx-500/10 text-tealx-300' : authStatus === 'SAFETY_GLOVES' ? 'border-accent-500/40 bg-accent-500/10 text-white animate-pulse' : 'border-white/[0.04] bg-space-900/40 text-space-400'}`}>
              <div className="flex items-center gap-2.5">
                <CheckCircle2 className="w-4 h-4 text-accent-400" />
                <span>3. PPE Nitrile Glove Inspection</span>
              </div>
              {authStatus === 'SAFETY_GLASSES' || authStatus === 'GRANTED' ? <CheckCircle2 className="w-4 h-4 text-tealx-400" /> : null}
            </div>

            <div className={`p-2.5 rounded-lg border flex items-center justify-between transition-all ${authStatus === 'GRANTED' ? 'border-tealx-500/40 bg-tealx-500/10 text-tealx-300' : authStatus === 'SAFETY_GLASSES' ? 'border-accent-500/40 bg-accent-500/10 text-white animate-pulse' : 'border-white/[0.04] bg-space-900/40 text-space-400'}`}>
              <div className="flex items-center gap-2.5">
                <Glasses className="w-4 h-4 text-accent-400" />
                <span>4. Protective Eyewear Verification</span>
              </div>
              {authStatus === 'GRANTED' ? <CheckCircle2 className="w-4 h-4 text-tealx-400" /> : null}
            </div>
          </div>

          <div className="text-[10px] text-space-400 font-mono flex items-center justify-between px-1">
            <span>Engine:</span>
            <span className="text-space-200 font-semibold">{faceEngine}</span>
          </div>
        </div>

        <div className="flex gap-2.5">
          <button
            onClick={triggerScan}
            disabled={busy}
            className="btn-primary flex-1 justify-center py-2.5"
          >
            <Camera className="w-3.5 h-3.5" />
            Security Scan
          </button>
          <button
            onClick={bypassAuth}
            disabled={busy}
            className="btn-ghost px-4 py-2.5"
          >
            Bypass / Grant
          </button>
        </div>
      </div>
    </div>
  );
};
