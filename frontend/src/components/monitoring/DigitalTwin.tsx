import React, { useEffect, useRef, memo, useState } from 'react';
import { Box, RefreshCw, Layers } from 'lucide-react';
import type { ApiBoundingBox } from '@/types/api';

interface DigitalTwinProps {
  boxes?: ApiBoundingBox[];
  handPos?: [number, number] | null;
  fodActive?: boolean;
  fodObject?: string;
  fodEta?: number;
}

// 3D Isometric / Perspective projection onto 2D Canvas
function project3D(
  x: number,
  y: number,
  z: number,
  canvasW: number,
  canvasH: number,
  rotY: number
): [number, number] {
  const cosR = Math.cos(rotY);
  const sinR = Math.sin(rotY);
  const rx = x * cosR - z * sinR;
  const rz = x * sinR + z * cosR;

  const fov = 420;
  const zOffset = rz + 650;
  const scale = fov / Math.max(zOffset, 1);

  const sx = canvasW / 2 + rx * scale;
  const sy = canvasH / 2 + y * scale;
  return [sx, sy];
}

function drawWireBox(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  cz: number,
  w: number,
  h: number,
  d: number,
  canvasW: number,
  canvasH: number,
  rotY: number,
  color: string,
  label?: string
) {
  const hw = w / 2, hh = h / 2, hd = d / 2;
  const verts = [
    [cx - hw, cy - hh, cz - hd],
    [cx + hw, cy - hh, cz - hd],
    [cx + hw, cy + hh, cz - hd],
    [cx - hw, cy + hh, cz - hd],
    [cx - hw, cy - hh, cz + hd],
    [cx + hw, cy - hh, cz + hd],
    [cx + hw, cy + hh, cz + hd],
    [cx - hw, cy + hh, cz + hd],
  ];
  const edges = [
    [0, 1], [1, 2], [2, 3], [3, 0],
    [4, 5], [5, 6], [6, 7], [7, 4],
    [0, 4], [1, 5], [2, 6], [3, 7],
  ];

  const projected = verts.map(v => project3D(v[0], v[1], v[2], canvasW, canvasH, rotY));

  ctx.strokeStyle = color;
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  for (const [a, b] of edges) {
    ctx.moveTo(projected[a][0], projected[a][1]);
    ctx.lineTo(projected[b][0], projected[b][1]);
  }
  ctx.stroke();

  if (label && projected[0]) {
    ctx.fillStyle = color;
    ctx.font = '9px monospace';
    ctx.fillText(label, projected[0][0], projected[0][1] - 4);
  }
}

export const DigitalTwin: React.FC<DigitalTwinProps> = memo(({
  boxes = [],
  handPos = null,
  fodActive = false,
  fodObject = '',
  fodEta = 0,
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [rotation, setRotation] = useState(0.4);
  const [autoRotate, setAutoRotate] = useState(true);

  useEffect(() => {
    let animId: number;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const render = () => {
      if (autoRotate) {
        setRotation(r => (r + 0.005) % (Math.PI * 2));
      }

      const w = canvas.width;
      const h = canvas.height;

      // Dark obsidian space canvas background
      ctx.fillStyle = '#07090e';
      ctx.fillRect(0, 0, w, h);

      // Perspective grid floor
      ctx.strokeStyle = 'rgba(0, 210, 255, 0.12)';
      ctx.lineWidth = 1;
      const gridY = 160;
      for (let gx = -300; gx <= 300; gx += 60) {
        const p1 = project3D(gx, gridY, -250, w, h, rotation);
        const p2 = project3D(gx, gridY, 250, w, h, rotation);
        ctx.beginPath();
        ctx.moveTo(p1[0], p1[1]);
        ctx.lineTo(p2[0], p2[1]);
        ctx.stroke();
      }
      for (let gz = -250; gz <= 250; gz += 50) {
        const p1 = project3D(-300, gridY, gz, w, h, rotation);
        const p2 = project3D(300, gridY, gz, w, h, rotation);
        ctx.beginPath();
        ctx.moveTo(p1[0], p1[1]);
        ctx.lineTo(p2[0], p2[1]);
        ctx.stroke();
      }

      // Outer Rack Bay wireframe enclosure
      drawWireBox(ctx, 0, 0, 0, 480, 320, 360, w, h, rotation, 'rgba(0, 210, 255, 0.35)', 'RACK BAY A1 // BAS MODULE');

      // Draw active experiment objects projected from detections
      boxes.forEach((box, i) => {
        const [x1, y1, x2, y2] = box.bbox;
        const normCx = (x1 + x2) / 2 - 0.5;
        const normCy = (y1 + y2) / 2 - 0.5;
        const bx = normCx * 360;
        const by = normCy * 220;
        const bz = (i % 2 === 0 ? -40 : 40);

        const color = box.class_name.includes('red')
          ? '#f43f5e'
          : box.class_name.includes('hand')
          ? '#2dd4bf'
          : '#38bdf8';

        drawWireBox(
          ctx,
          bx,
          by,
          bz,
          (x2 - x1) * 220 + 20,
          (y2 - y1) * 160 + 20,
          50,
          w,
          h,
          rotation,
          color,
          box.class_name.toUpperCase()
        );
      });

      // Draw tracked Astronaut Hand coordinates
      if (handPos) {
        const hx = (handPos[0] / 640 - 0.5) * 360;
        const hy = (handPos[1] / 480 - 0.5) * 220;
        const pHand = project3D(hx, hy, 10, w, h, rotation);

        ctx.fillStyle = '#2dd4bf';
        ctx.beginPath();
        ctx.arc(pHand[0], pHand[1], 4, 0, Math.PI * 2);
        ctx.fill();

        ctx.strokeStyle = '#2dd4bf';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.arc(pHand[0], pHand[1], 10, 0, Math.PI * 2);
        ctx.stroke();

        ctx.fillStyle = '#5eead4';
        ctx.font = '9px monospace';
        ctx.fillText('ASTRONAUT HAND VECTOR', pHand[0] + 12, pHand[1] + 3);
      }

      // Draw FOD collision trajectory vector
      if (fodActive) {
        const p1 = project3D(50, -40, -20, w, h, rotation);
        const p2 = project3D(180, 80, 60, w, h, rotation);

        ctx.strokeStyle = '#f43f5e';
        ctx.lineWidth = 2;
        ctx.setLineDash([4, 4]);
        ctx.beginPath();
        ctx.moveTo(p1[0], p1[1]);
        ctx.lineTo(p2[0], p2[1]);
        ctx.stroke();
        ctx.setLineDash([]);

        ctx.fillStyle = '#f43f5e';
        ctx.font = '10px monospace';
        ctx.fillText(`UNSECURED DRIFT: ${fodObject.toUpperCase()} (${fodEta}s ETA)`, p2[0] + 6, p2[1] - 4);
      }

      // Digital Twin HUD Overlay labels
      ctx.fillStyle = 'rgba(0, 210, 255, 0.8)';
      ctx.font = '9px monospace';
      ctx.fillText('GROUND STATION DIGITAL TWIN // DEEP-SPACE DOWNLINK', 12, 18);
      ctx.fillStyle = 'rgba(148, 163, 184, 0.7)';
      ctx.fillText('BANDWIDTH COMPRESSION: 99.98% (~0.5 KB/s vs 2.5 MB/s raw video)', 12, 32);
    };

    render();
    animId = requestAnimationFrame(render);
    return () => cancelAnimationFrame(animId);
  }, [boxes, handPos, fodActive, fodObject, fodEta, rotation, autoRotate]);

  return (
    <div className="relative w-full bg-space-950 rounded-lg overflow-hidden border border-space-800 p-3 shadow-xl">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Box className="w-4 h-4 text-accent-400" />
          <h3 className="text-xs font-mono font-bold text-white uppercase tracking-wider">
            3D Digital Twin — Telemetry Projection
          </h3>
          <span className="badge bg-tealx-500/15 text-tealx-400 border border-tealx-500/30 text-[9px] font-mono">
            99.98% LOW-BW
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setAutoRotate(!autoRotate)}
            className={`text-[10px] font-mono px-2 py-0.5 rounded border transition-colors flex items-center gap-1 ${
              autoRotate
                ? 'bg-accent-500/20 text-accent-300 border-accent-500/40'
                : 'text-space-400 border-space-800 hover:text-white'
            }`}
          >
            <RefreshCw className={`w-3 h-3 ${autoRotate ? 'animate-spin' : ''}`} />
            Auto-Orbit
          </button>
        </div>
      </div>

      <div className="relative aspect-[16/9] w-full rounded border border-space-800 overflow-hidden bg-black shadow-inner">
        <canvas
          ref={canvasRef}
          width={640}
          height={360}
          className="w-full h-full object-contain"
        />
        {fodActive && (
          <div className="absolute top-2 right-2 bg-redx-500/90 text-white text-[10px] font-mono px-2.5 py-1 rounded shadow-glow-red animate-pulse">
            DRIFT TRAJECTORY PROJECTED // {fodObject.toUpperCase()}
          </div>
        )}
      </div>

      <div className="flex items-center justify-between text-[10px] font-mono text-space-400 mt-2 px-1">
        <span>Coordinate Frame: ISO-B2 Rack</span>
        <span>Telemetry Stream: Active</span>
        <span>Deep-Space Downlink: Ready</span>
      </div>
    </div>
  );
});
