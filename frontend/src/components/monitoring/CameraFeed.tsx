import { useEffect, useRef, useState } from 'react';
import {
  Maximize2,
  Minimize2,
  Camera,
  AlertTriangle,
  RefreshCw,
  Radio,
  Crosshair,
  Layers,
  Activity,
  Sliders,
} from 'lucide-react';
import type { ApiBoundingBox } from '@/types/api';

interface CameraFeedProps {
  boxes?: ApiBoundingBox[];
  connected?: boolean;
  streamMode?: 'simulated' | 'camera';
  fps?: number;
  latencyMs?: number;
  handPos?: [number, number] | null;
}

const CLASS_LABELS: Record<string, string> = {
  hand: 'ASTRONAUT HAND',
  astronaut_hand: 'ASTRONAUT HAND',
  container: 'SAMPLE CONTAINER',
  outer_container: 'OUTER AIRTIGHT ENCLOSURE',
  red_box: 'REAGENT KIT [RED]',
  second_colored_box: 'BUFFER VIAL CASING',
  sample_bag: 'STERILE SAMPLE BAG',
  tool: 'MANIPULATION TOOL',
  liquid: 'CRYSTAL BUFFER FLUID',
  mixing_stirrer: 'MAGNETIC STIRRING TOOL',
  cylinder: 'PRESSURIZED BUFFER CYLINDER',
};

function toPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

export default function CameraFeed({
  boxes = [],
  connected = false,
  streamMode = 'simulated',
  fps = 29.8,
  latencyMs = 12.4,
  handPos,
}: CameraFeedProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [cameraSource, setCameraSource] = useState<'stream' | 'webcam'>('stream');
  const [webcamActive, setWebcamActive] = useState(false);
  const [webcamError, setWebcamError] = useState<string | null>(null);
  const [streamError, setStreamError] = useState(false);
  const [streamLoaded, setStreamLoaded] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);

  // Overlay toggles
  const [showReticles, setShowReticles] = useState(true);
  const [showVectors, setShowVectors] = useState(true);
  const [showGrid, setShowGrid] = useState(true);

  // Initialize browser webcam
  const initWebcam = async () => {
    setWebcamError(null);
    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        throw new Error('Webcam capture is not supported in this browser context.');
      }
      const mediaStream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: 1280 },
          height: { ideal: 720 },
          facingMode: 'user',
        },
        audio: false,
      });

      if (videoRef.current) {
        videoRef.current.srcObject = mediaStream;
        videoRef.current.muted = true;
        await videoRef.current.play().catch(() => {});
        setWebcamActive(true);
      }
    } catch (err) {
      console.warn('Browser webcam access error:', err);
      setWebcamActive(false);
      setWebcamError(
        err instanceof Error
          ? err.message
          : 'Could not access browser webcam. Switch to the Sensor Stream mode.'
      );
    }
  };

  useEffect(() => {
    if (streamMode === 'camera' && cameraSource === 'webcam') {
      initWebcam();
    } else {
      setWebcamActive(false);
      setWebcamError(null);
      if (videoRef.current && videoRef.current.srcObject) {
        const stream = videoRef.current.srcObject as MediaStream;
        stream.getTracks().forEach((track) => track.stop());
        videoRef.current.srcObject = null;
      }
    }

    return () => {
      if (videoRef.current && videoRef.current.srcObject) {
        const stream = videoRef.current.srcObject as MediaStream;
        stream.getTracks().forEach((track) => track.stop());
        videoRef.current.srcObject = null;
      }
    };
  }, [streamMode, cameraSource]);

  const toggleFullscreen = () => {
    if (!containerRef.current) return;
    if (!document.fullscreenElement) {
      containerRef.current.requestFullscreen().then(() => setIsFullscreen(true)).catch(() => {});
    } else {
      document.exitFullscreen().then(() => setIsFullscreen(false)).catch(() => {});
    }
  };

  // Find hand box and object box for interaction vector calculation
  const handBox = boxes.find(
    (b) => b.class_name.includes('hand') || b.class_name === 'astronaut_hand'
  );
  const objectBox = boxes.find(
    (b) => !b.class_name.includes('hand') && b.class_name !== 'astronaut_hand'
  );

  return (
    <div
      ref={containerRef}
      className="relative w-full aspect-video bg-[#04060a] rounded overflow-hidden border border-[#ded2c5] select-none shadow-sm"
    >
      {/* Matte black workspace base */}
      <div className="absolute inset-0 bg-[#06080d]" />

      {/* Optical Video Stream or Browser Webcam */}
      {streamMode === 'camera' && (
        <>
          {cameraSource === 'stream' ? (
            <div className="absolute inset-0 w-full h-full z-0 overflow-hidden bg-black flex items-center justify-center">
              <img
                src="/api/v1/monitoring/stream"
                alt="Onboard Optical Sensor Feed"
                className={`w-full h-full object-cover transition-opacity duration-300 ${
                  streamLoaded ? 'opacity-100' : 'opacity-85'
                }`}
                onLoad={() => {
                  setStreamLoaded(true);
                  setStreamError(false);
                }}
                onError={() => {
                  setStreamError(true);
                  setStreamLoaded(false);
                }}
              />
              {streamError && (
                <div className="absolute inset-0 flex flex-col items-center justify-center bg-[#070a11]/90 p-4 text-center z-10 font-mono">
                  <AlertTriangle className="w-8 h-8 text-amberx-400 mb-2" />
                  <p className="text-xs text-white font-bold mb-1 uppercase tracking-wider">
                    Sensor Stream Standby / Offline
                  </p>
                  <p className="text-[11px] text-space-400 mb-3 max-w-sm">
                    Awaiting camera hardware feed. You can toggle browser webcam or test with synthetic simulated inference.
                  </p>
                  <button
                    onClick={() => setCameraSource('webcam')}
                    className="btn-secondary text-[11px] px-3 py-1.5 flex items-center gap-1.5"
                  >
                    <Camera className="w-3.5 h-3.5" />
                    Engage Browser Webcam
                  </button>
                </div>
              )}
            </div>
          ) : (
            <div className="absolute inset-0 w-full h-full z-0 overflow-hidden bg-black">
              <video
                ref={videoRef}
                autoPlay
                playsInline
                muted
                className={`w-full h-full object-cover transition-opacity duration-300 ${
                  webcamActive ? 'opacity-100' : 'opacity-0'
                }`}
              />
              {!webcamActive && (
                <div className="absolute inset-0 flex flex-col items-center justify-center bg-[#070a11]/90 p-4 text-center z-10 font-mono">
                  {webcamError ? (
                    <div className="flex flex-col items-center max-w-sm">
                      <AlertTriangle className="w-8 h-8 text-amberx-400 mb-2" />
                      <p className="text-xs text-white font-bold mb-1">Webcam Inaccessible</p>
                      <p className="text-[11px] text-space-400 mb-3">{webcamError}</p>
                      <div className="flex gap-2">
                        <button
                          onClick={initWebcam}
                          className="btn-primary text-xs px-3 py-1 flex items-center gap-1"
                        >
                          <RefreshCw className="w-3 h-3" />
                          Retry
                        </button>
                        <button
                          onClick={() => setCameraSource('stream')}
                          className="btn-secondary text-xs px-3 py-1 flex items-center gap-1"
                        >
                          <Radio className="w-3 h-3" />
                          Use Sensor Stream
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="flex flex-col items-center">
                      <div className="w-8 h-8 rounded bg-accent-500/10 border border-accent-400/40 flex items-center justify-center mb-2 animate-pulse">
                        <Camera className="w-4 h-4 text-accent-400" />
                      </div>
                      <p className="text-xs font-bold text-white mb-0.5">Initializing Browser Video Sensor...</p>
                      <p className="text-[11px] text-space-400">Grant permission in browser prompt to stream</p>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </>
      )}

      {/* Synthetic Spacecraft Experiment Geometry (Simulated Mode) */}
      {streamMode === 'simulated' && (
        <div className="absolute inset-0 pointer-events-none opacity-80">
          {/* Glovebox work volume safety boundary */}
          <div className="absolute inset-6 border border-[#1b2538] rounded pointer-events-none" />

          {/* Simulated astronaut arm & hand silhouette */}
          <div className="absolute top-[28%] left-[18%] opacity-35">
            <div className="w-20 h-40 rounded-t-full bg-space-600/30 border border-space-500/30 relative">
              <div className="w-16 h-16 rounded-full bg-space-500/30 border border-space-400/20 mx-auto mt-2" />
              <div className="w-12 h-20 bg-space-500/20 border border-space-400/20 mx-auto mt-2 rounded" />
            </div>
          </div>

          {/* Simulated experiment container */}
          <div className="absolute top-[45%] left-[50%] opacity-40">
            <div className="w-32 h-24 bg-space-800/40 border border-[#222f47] rounded flex items-center justify-center">
              <div className="w-24 h-16 bg-accent-500/10 border border-accent-400/20 rounded" />
            </div>
          </div>

          {/* Simulated tool / stirrer */}
          <div className="absolute top-[58%] left-[72%] opacity-35">
            <div className="w-16 h-20 bg-space-800/30 border border-[#222f47] rounded flex flex-col items-center justify-center gap-1.5">
              <div className="w-10 h-1 bg-space-500/40 rounded" />
              <div className="w-10 h-1 bg-space-500/40 rounded" />
              <div className="w-10 h-1 bg-space-500/40 rounded" />
            </div>
          </div>
        </div>
      )}

      {/* Technical Grid Lines */}
      {showGrid && (
        <div
          className="absolute inset-0 opacity-10 pointer-events-none z-10"
          style={{
            backgroundImage:
              'linear-gradient(rgba(180,95,35,0.2) 1px, transparent 1px), linear-gradient(90deg, rgba(180,95,35,0.2) 1px, transparent 1px)',
            backgroundSize: '48px 48px',
          }}
        />
      )}

      {/* Center Tactical Crosshair */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-6 h-6 border border-accent-400/30 rounded-full z-15 pointer-events-none flex items-center justify-center">
        <div className="w-1 h-1 bg-accent-400/60 rounded-full" />
      </div>

      {/* First-Class Computer Vision Overlays */}
      {showReticles && (
        <div className="absolute inset-0 pointer-events-none z-20">
          {boxes.map((box, i) => {
            const [x1, y1, x2, y2] = box.bbox;
            const label = CLASS_LABELS[box.class_name] ?? box.class_name.toUpperCase();
            const trackId = `TRK-0${i + 1}`;
            const conf = Math.round(box.confidence * 100);

            return (
              <div
                key={`${box.class_name}-${i}`}
                className="absolute border border-accent-400/80 transition-all duration-150"
                style={{
                  top: toPercent(y1),
                  left: toPercent(x1),
                  width: toPercent(x2 - x1),
                  height: toPercent(y2 - y1),
                }}
              >
                {/* 4 Precision Corner HUD Brackets */}
                <div className="absolute -top-1 -left-1 w-2.5 h-2.5 border-t-2 border-l-2 border-accent-400" />
                <div className="absolute -top-1 -right-1 w-2.5 h-2.5 border-t-2 border-r-2 border-accent-400" />
                <div className="absolute -bottom-1 -left-1 w-2.5 h-2.5 border-b-2 border-l-2 border-accent-400" />
                <div className="absolute -bottom-1 -right-1 w-2.5 h-2.5 border-b-2 border-r-2 border-accent-400" />

                {/* Integrated Reticle Tag */}
                <div className="absolute -top-5 left-0 bg-[#06090e]/90 border border-accent-400/60 text-white text-[9px] font-mono px-1.5 py-0.5 rounded-sm whitespace-nowrap flex items-center gap-1.5 shadow">
                  <span className="text-accent-400 font-bold">{trackId}</span>
                  <span className="text-space-300 font-semibold">{label}</span>
                  <span className="text-tealx-400 font-bold tabular-nums">{conf}%</span>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Hand-Object Interaction Vector */}
      {showVectors && handBox && objectBox && (
        <svg className="absolute inset-0 w-full h-full pointer-events-none z-25">
          <line
            x1={`${((handBox.bbox[0] + handBox.bbox[2]) / 2) * 100}%`}
            y1={`${((handBox.bbox[1] + handBox.bbox[3]) / 2) * 100}%`}
            x2={`${((objectBox.bbox[0] + objectBox.bbox[2]) / 2) * 100}%`}
            y2={`${((objectBox.bbox[1] + objectBox.bbox[3]) / 2) * 100}%`}
            stroke="#b45f23"
            strokeWidth="1.5"
            strokeDasharray="4 3"
            strokeOpacity="0.8"
          />
          <circle
            cx={`${((handBox.bbox[0] + handBox.bbox[2]) / 2) * 100}%`}
            cy={`${((handBox.bbox[1] + handBox.bbox[3]) / 2) * 100}%`}
            r="3"
            fill="#b45f23"
          />
          <circle
            cx={`${((objectBox.bbox[0] + objectBox.bbox[2]) / 2) * 100}%`}
            cy={`${((objectBox.bbox[1] + objectBox.bbox[3]) / 2) * 100}%`}
            r="3"
            fill="#166534"
          />
        </svg>
      )}

      {/* Scanline Animation */}
      <div className="scanline z-20 pointer-events-none opacity-30" />

      {/* Top Vision Telemetry Bar */}
      <div className="absolute top-0 left-0 right-0 z-30 flex items-center justify-between px-3 py-1.5 bg-[#060a12]/90 border-b border-white/[0.08] text-[10px] font-mono">
        <div className="flex items-center gap-2">
          {streamMode === 'camera' ? (
            <span className="badge bg-tealx-500/20 text-tealx-400 border border-tealx-500/40">
              <span className="status-dot bg-tealx-400" />
              OPTICAL CAM-01
            </span>
          ) : (
            <span className="badge bg-accent-500/20 text-accent-300 border border-accent-400/40">
              <span className="status-dot bg-accent-400" />
              SYNTHETIC SENSOR
            </span>
          )}

          <span className="text-space-400 hidden sm:inline">|</span>
          <span className="text-space-300 hidden sm:inline">BAY-A1 RACK 04</span>
          <span className="text-space-400 hidden sm:inline">|</span>
          <span className="text-space-300 tabular-nums">1920x1080 @ {Math.round(fps)} FPS</span>
          <span className="text-space-400 hidden md:inline">|</span>
          <span className="text-tealx-400 hidden md:inline tabular-nums">LATENCY: {latencyMs.toFixed(1)}ms</span>
        </div>

        {/* Camera Source Selector if in hardware cam mode */}
        <div className="flex items-center gap-2">
          {streamMode === 'camera' && (
            <div className="flex items-center bg-[#070a11] border border-[#1b2436] rounded p-0.5 text-[9px] font-mono">
              <button
                onClick={() => setCameraSource('stream')}
                className={`px-1.5 py-0.5 rounded transition-all ${
                  cameraSource === 'stream'
                    ? 'bg-accent-600 text-white font-bold'
                    : 'text-space-400 hover:text-white'
                }`}
              >
                Sensor Feed
              </button>
              <button
                onClick={() => setCameraSource('webcam')}
                className={`px-1.5 py-0.5 rounded transition-all ${
                  cameraSource === 'webcam'
                    ? 'bg-accent-600 text-white font-bold'
                    : 'text-space-400 hover:text-white'
                }`}
              >
                Browser Cam
              </button>
            </div>
          )}

          {/* Overlay Toggles */}
          <div className="flex items-center gap-1">
            <button
              onClick={() => setShowReticles(!showReticles)}
              className={`p-1 rounded border text-[9px] font-mono transition-colors ${
                showReticles
                  ? 'bg-accent-500/20 text-accent-300 border-accent-400/40'
                  : 'bg-space-850 text-space-500 border-[#222d42]'
              }`}
              title="Toggle Bounding Reticles & IDs"
              aria-label="Toggle computer vision bounding reticles"
            >
              RETICLES
            </button>
            <button
              onClick={() => setShowVectors(!showVectors)}
              className={`p-1 rounded border text-[9px] font-mono transition-colors ${
                showVectors
                  ? 'bg-accent-500/20 text-accent-300 border-accent-400/40'
                  : 'bg-space-850 text-space-500 border-[#222d42]'
              }`}
              title="Toggle Hand-Object Interaction Vectors"
              aria-label="Toggle hand-object interaction vectors"
            >
              VECTORS
            </button>
            <button
              onClick={toggleFullscreen}
              className="p-1 rounded bg-space-850 border border-[#222d42] text-space-300 hover:text-white transition-colors"
              title="Toggle Fullscreen Workspace"
              aria-label="Toggle fullscreen view"
            >
              {isFullscreen ? <Minimize2 className="w-3 h-3" /> : <Maximize2 className="w-3 h-3" />}
            </button>
          </div>
        </div>
      </div>

      {/* Bottom Status Ribbon */}
      <div className="absolute bottom-0 left-0 right-0 z-30 flex items-center justify-between px-3 py-1 bg-[#060a12]/90 border-t border-white/[0.08] text-[10px] font-mono text-space-400">
        <div className="flex items-center gap-2">
          <Activity className="w-3 h-3 text-tealx-400" />
          <span className="text-space-300">
            {boxes.length > 0
              ? `${boxes.length} ENTITIES ACTIVELY TRACKED IN WORKSPACE`
              : 'OPTICAL SENSOR ACTIVE // WORKSPACE CORRIDOR CLEAR'}
          </span>
        </div>
        <div className="text-[9px] text-space-400 tabular-nums">
          CONICAL FOV 94° // APERTURE f/1.8
        </div>
      </div>
    </div>
  );
}
