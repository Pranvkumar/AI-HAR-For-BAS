import React, { useState, useEffect } from 'react';
import { X, Box, Camera, Check, Trash2, Plus, AlertCircle } from 'lucide-react';

interface ObjectRegistryModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const ObjectRegistryModal: React.FC<ObjectRegistryModalProps> = ({ isOpen, onClose }) => {
  const [objects, setObjects] = useState<any[]>([]);
  const [slug, setSlug] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [capturing, setCapturing] = useState(false);
  const [captureCount, setCaptureCount] = useState(0);
  const [message, setMessage] = useState<string | null>(null);

  const fetchObjects = () => {
    fetch('/api/v1/objects/list')
      .then(res => res.json())
      .then(data => setObjects(data.objects || []))
      .catch(() => {});
  };

  useEffect(() => {
    if (isOpen) {
      fetchObjects();
      setMessage(null);
      setCaptureCount(0);
    }
  }, [isOpen]);

  const handleCapture = async () => {
    if (!slug) {
      setMessage('Please enter an object slug or code first (e.g. sample_vial_a)');
      return;
    }
    setCapturing(true);
    setMessage(null);
    try {
      const res = await fetch('/api/v1/objects/capture', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ object_slug: slug }),
      });
      const data = await res.json();
      setCaptureCount(data.count || 0);
      setMessage(`Captured reference frame #${data.count} from camera.`);
      fetchObjects();
    } catch (err: any) {
      setMessage(err.message || 'Capture failed');
    } finally {
      setCapturing(false);
    }
  };

  const handleRegister = async () => {
    if (!slug || !displayName) {
      setMessage('Please enter both slug and display name');
      return;
    }
    try {
      const res = await fetch('/api/v1/objects/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ object_slug: slug, display_name: displayName }),
      });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || 'Registration failed');
      }
      setMessage(`Successfully registered '${displayName}' via ORB descriptors!`);
      setSlug('');
      setDisplayName('');
      setCaptureCount(0);
      fetchObjects();
    } catch (err: any) {
      setMessage(err.message || 'Registration failed');
    }
  };

  const handleDelete = async (targetSlug: string) => {
    try {
      await fetch(`/api/v1/objects/delete/${targetSlug}`, { method: 'DELETE' });
      fetchObjects();
    } catch {}
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4 animate-in fade-in duration-200">
      <div className="bg-space-950/95 border border-white/[0.1] rounded-2xl max-w-lg w-full p-6 shadow-glass relative backdrop-blur-2xl">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-space-400 hover:text-white p-1 rounded-lg hover:bg-space-800/60 transition-colors cursor-pointer"
          title="Close dialog"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="flex items-center gap-2.5 mb-3">
          <div className="w-8 h-8 rounded-lg bg-accent-500/15 border border-accent-500/30 flex items-center justify-center text-accent-400">
            <Box className="w-4 h-4" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-white uppercase font-display tracking-wider">
              Dynamic Object Registry
            </h2>
            <p className="text-[10px] text-space-400 font-mono">ORB DESCRIPTOR EXTRACTION // RUNTIME CATALOG</p>
          </div>
        </div>

        <p className="text-xs text-space-300 mb-4 font-sans leading-relaxed">
          Register novel experiment tools, containers, or fluid vials in real time. ORB extracts feature descriptors from live snapshots with zero neural network retraining needed.
        </p>

        {/* Capture Form */}
        <div className="p-4 bg-space-900/60 rounded-xl border border-white/[0.06] mb-4 space-y-3">
          <h3 className="text-xs font-bold text-white uppercase font-display flex items-center gap-1.5">
            <Plus className="w-3.5 h-3.5 text-accent-400" />
            Register New Payload
          </h3>

          <div className="grid grid-cols-2 gap-2.5">
            <div>
              <label className="text-[10px] text-space-400 font-mono block mb-1">Object ID (Slug)</label>
              <input
                type="text"
                placeholder="e.g. sample_vial_01"
                value={slug}
                onChange={e => setSlug(e.target.value)}
                className="input-field text-xs py-2 w-full"
              />
            </div>
            <div>
              <label className="text-[10px] text-space-400 font-mono block mb-1">Display Label</label>
              <input
                type="text"
                placeholder="e.g. Sample Fluid Vial A"
                value={displayName}
                onChange={e => setDisplayName(e.target.value)}
                className="input-field text-xs py-2 w-full font-sans"
              />
            </div>
          </div>

          <div className="flex gap-2.5 pt-1.5">
            <button
              onClick={handleCapture}
              disabled={capturing || !slug}
              className="btn-ghost text-xs px-3.5 py-2 flex items-center gap-1.5 flex-1 justify-center disabled:opacity-50"
            >
              <Camera className="w-3.5 h-3.5" />
              Capture Snapshot {captureCount > 0 ? `(${captureCount}/3)` : ''}
            </button>
            <button
              onClick={handleRegister}
              disabled={!slug || !displayName || captureCount < 3}
              className="btn-primary text-xs px-3.5 py-2 flex items-center gap-1.5 flex-1 justify-center disabled:opacity-50"
            >
              <Check className="w-3.5 h-3.5" />
              Finalize ORB
            </button>
          </div>

          {message && (
            <p className="text-[11px] text-accent-300 font-mono flex items-center gap-1.5 p-2 rounded bg-accent-500/10 border border-accent-500/20">
              <AlertCircle className="w-3.5 h-3.5 shrink-0" />
              <span>{message}</span>
            </p>
          )}
        </div>

        {/* Object List */}
        <div>
          <h3 className="text-xs font-semibold text-white uppercase mb-2">Registered Onboard Registry</h3>
          <div className="max-h-48 overflow-y-auto space-y-1.5 pr-1">
            {objects.length === 0 ? (
              <p className="text-xs text-space-400 italic py-2 text-center">No dynamic objects registered yet.</p>
            ) : (
              objects.map(obj => (
                <div
                  key={obj.slug}
                  className="p-2 bg-space-950/70 border border-space-800 rounded flex items-center justify-between text-xs"
                >
                  <div>
                    <span className="font-semibold text-white">{obj.name || obj.slug}</span>
                    <span className="text-[10px] font-mono text-space-400 ml-2">[{obj.slug}]</span>
                    <p className="text-[10px] text-space-400">
                      Snapshots: {obj.image_count} | ORB Descriptors: {obj.orb_refs_loaded || 'Loaded'}
                    </p>
                  </div>
                  <button
                    onClick={() => handleDelete(obj.slug)}
                    className="text-space-400 hover:text-redx-400 p-1 transition-colors"
                    title="Delete object"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
