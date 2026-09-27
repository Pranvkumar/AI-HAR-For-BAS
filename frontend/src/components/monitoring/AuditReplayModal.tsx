import React, { useState, useEffect } from 'react';
import { X, Video, Download, Play, Calendar, Film } from 'lucide-react';

interface AuditReplayModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const AuditReplayModal: React.FC<AuditReplayModalProps> = ({ isOpen, onClose }) => {
  const [recordings, setRecordings] = useState<any[]>([]);
  const [selectedVideo, setSelectedVideo] = useState<string | null>(null);

  const fetchRecordings = () => {
    fetch('/api/v1/recordings/list')
      .then(res => res.json())
      .then(data => {
        setRecordings(data.recordings || []);
        if (data.recordings?.length > 0 && !selectedVideo) {
          setSelectedVideo(data.recordings[0].path);
        }
      })
      .catch(() => {});
  };

  useEffect(() => {
    if (isOpen) {
      fetchRecordings();
    }
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4 animate-in fade-in duration-200">
      <div className="bg-space-950/95 border border-white/[0.1] rounded-2xl max-w-2xl w-full p-6 shadow-glass relative backdrop-blur-2xl">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-space-400 hover:text-white p-1 rounded-lg hover:bg-space-800/60 transition-colors cursor-pointer"
          title="Close dialog"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="flex items-center gap-2.5 mb-4">
          <div className="w-8 h-8 rounded-lg bg-amberx-500/15 border border-amberx-500/30 flex items-center justify-center text-amberx-400">
            <Film className="w-4 h-4" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-white uppercase font-display tracking-wider">
              Session Flight Recording & Audit Replay
            </h2>
            <p className="text-[10px] text-space-400 font-mono">DO-178C SESSION MP4 ARCHIVE</p>
          </div>
        </div>

        {/* Video Player */}
        <div className="aspect-video w-full bg-black rounded-xl overflow-hidden border border-white/[0.08] mb-4 flex items-center justify-center shadow-inner relative">
          {selectedVideo ? (
            <video
              key={selectedVideo}
              src={selectedVideo}
              controls
              autoPlay
              className="w-full h-full object-contain"
            />
          ) : (
            <div className="text-center p-6 text-space-400">
              <Film className="w-10 h-10 mx-auto mb-2 opacity-30 text-space-400" />
              <p className="text-xs font-mono">Select a session recording below to replay</p>
            </div>
          )}
        </div>

        {/* Recording List */}
        <div>
          <h3 className="text-xs font-bold text-white uppercase font-display mb-2.5 flex items-center justify-between">
            <span className="flex items-center gap-1.5">
              <Film className="w-3.5 h-3.5 text-accent-400" />
              Archived Flight Sessions
            </span>
            <span className="text-[10px] text-space-400 font-mono px-2 py-0.5 rounded bg-space-900 border border-white/[0.04]">
              {recordings.length} Recordings
            </span>
          </h3>

          <div className="max-h-44 overflow-y-auto space-y-2 pr-1">
            {recordings.length === 0 ? (
              <p className="text-xs text-space-400 italic py-4 text-center font-mono">
                No session recordings found yet. Run an experiment session to record video automatically.
              </p>
            ) : (
              recordings.map(rec => (
                <div
                  key={rec.filename}
                  onClick={() => setSelectedVideo(rec.path)}
                  className={`p-3 rounded-xl border flex items-center justify-between text-xs cursor-pointer transition-all ${
                    selectedVideo === rec.path
                      ? 'bg-accent-500/15 border-accent-400/50 text-white shadow-glow-accent'
                      : 'bg-space-900/50 border-white/[0.04] text-space-300 hover:bg-space-850 hover:border-white/[0.1]'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <div className="w-7 h-7 rounded-lg bg-space-800/80 border border-white/[0.06] flex items-center justify-center text-accent-400">
                      <Play className="w-3 h-3 fill-current" />
                    </div>
                    <div>
                      <p className="font-mono font-semibold text-white tracking-tight">{rec.filename}</p>
                      <p className="text-[10px] text-space-400 font-mono flex items-center gap-2 mt-0.5">
                        <span>{rec.size_mb} MB</span>
                        <span>•</span>
                        <span>{new Date(rec.created_at).toLocaleString()}</span>
                      </p>
                    </div>
                  </div>

                  <a
                    href={rec.path}
                    download
                    onClick={e => e.stopPropagation()}
                    className="p-2 text-space-400 hover:text-white hover:bg-space-800 rounded-lg transition-colors"
                    title="Download MP4"
                  >
                    <Download className="w-3.5 h-3.5" />
                  </a>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
