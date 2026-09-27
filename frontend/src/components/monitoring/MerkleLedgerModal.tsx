import React, { useState, useEffect } from 'react';
import { X, Lock, CheckCircle2, ShieldCheck, Download, RefreshCw, Hash, ArrowDown } from 'lucide-react';

interface MerkleLedgerModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const MerkleLedgerModal: React.FC<MerkleLedgerModalProps> = ({ isOpen, onClose }) => {
  const [ledgerData, setLedgerData] = useState<any>(null);
  const [verifying, setVerifying] = useState(false);
  const [verificationResult, setVerificationResult] = useState<string | null>(null);

  const fetchLedger = () => {
    fetch('/api/v1/aerospace/telemetry')
      .then(res => res.json())
      .then(data => {
        if (data?.merkle) {
          setLedgerData(data.merkle);
        }
      })
      .catch(() => {});
  };

  useEffect(() => {
    if (isOpen) {
      fetchLedger();
      setVerificationResult(null);
    }
  }, [isOpen]);

  const verifyProof = async () => {
    setVerifying(true);
    setVerificationResult(null);
    try {
      const res = await fetch('/api/v1/aerospace/merkle/verify');
      const data = await res.json();
      if (data.valid) {
        setVerificationResult(`CRYPTOGRAPHIC PROOF VERIFIED: All ${data.chain_length} blocks valid. Head: ${data.head_hash.substring(0, 16)}...`);
      } else {
        setVerificationResult('VERIFICATION FAILED: Chain signature mismatch detected.');
      }
    } catch {
      setVerificationResult('Error contacting Merkle verification service.');
    } finally {
      setVerifying(false);
    }
  };

  if (!isOpen) return null;

  const blocks = ledgerData?.recent_blocks || [];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 backdrop-blur-md p-4 animate-in fade-in duration-200">
      <div className="bg-space-950/95 border border-white/[0.1] rounded-2xl max-w-2xl w-full p-6 shadow-glass relative backdrop-blur-2xl max-h-[90vh] flex flex-col">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-space-400 hover:text-white p-1 rounded-lg hover:bg-space-850 transition-colors cursor-pointer"
          title="Close dialog"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Header */}
        <div className="flex items-center gap-3 mb-4 shrink-0">
          <div className="w-9 h-9 rounded-xl bg-violetx-500/15 border border-violetx-500/30 flex items-center justify-center text-violetx-400">
            <Lock className="w-4 h-4" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-white uppercase font-display tracking-wider flex items-center gap-2">
              DO-178C Merkle Flight Ledger Explorer
              <span className="text-[9px] font-mono px-2 py-0.5 rounded-full bg-tealx-500/15 text-tealx-400 border border-tealx-500/30">
                LEVEL A
              </span>
            </h2>
            <p className="text-[11px] text-space-400 font-mono">
              TAMPER-PROOF APPEND-ONLY SHA-256 STATE TRANSITION CHAIN
            </p>
          </div>
        </div>

        {/* Telemetry Summary Bar */}
        <div className="grid grid-cols-3 gap-3 p-3 rounded-xl bg-space-900/60 border border-white/[0.06] mb-4 shrink-0 font-mono text-xs">
          <div>
            <span className="text-[10px] text-space-400 block uppercase">Chain Depth</span>
            <span className="text-sm font-bold text-white">{ledgerData?.chain_length ?? 0} Blocks</span>
          </div>
          <div>
            <span className="text-[10px] text-space-400 block uppercase">Chain Head</span>
            <span className="text-xs font-bold text-accent-400 truncate block">
              {ledgerData?.chain_hash || '0x0000...0000'}
            </span>
          </div>
          <div>
            <span className="text-[10px] text-space-400 block uppercase">Compliance</span>
            <span className="text-xs font-semibold text-tealx-400 flex items-center gap-1">
              <CheckCircle2 className="w-3.5 h-3.5" /> DO-178C / ED-12C
            </span>
          </div>
        </div>

        {/* Verification banner if executed */}
        {verificationResult && (
          <div className="p-3 mb-3 rounded-lg bg-tealx-500/10 border border-tealx-500/30 text-tealx-300 font-mono text-xs flex items-center gap-2 shrink-0 animate-in fade-in">
            <ShieldCheck className="w-4 h-4 shrink-0 text-tealx-400" />
            <span>{verificationResult}</span>
          </div>
        )}

        {/* Chain blocks scroll view */}
        <div className="flex-1 overflow-y-auto space-y-2.5 pr-1 font-mono text-xs">
          <div className="text-[10px] text-space-400 uppercase tracking-widest px-1">
            Recorded Transition Blocks (Newest First)
          </div>

          {blocks.length === 0 ? (
            <div className="p-8 text-center text-space-500 border border-white/[0.04] rounded-xl bg-space-900/30">
              <Hash className="w-8 h-8 mx-auto mb-2 opacity-30" />
              <p>No blocks recorded in current session. Start a monitoring session to log cryptographic transitions.</p>
            </div>
          ) : (
            blocks.map((block: any, idx: number) => (
              <div
                key={block.full_hash || idx}
                className="p-3.5 rounded-xl bg-space-900/50 border border-white/[0.06] hover:border-violetx-400/40 transition-all space-y-2"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="px-1.5 py-0.5 rounded bg-violetx-500/20 text-violetx-300 text-[10px] font-bold">
                      BLOCK #{block.index}
                    </span>
                    <span className="text-white font-semibold text-[11px]">{block.step_id}</span>
                  </div>
                  <span className="text-[10px] text-space-400">{block.timestamp?.substring(11, 19)} UTC</span>
                </div>

                <div className="grid grid-cols-2 gap-2 text-[11px] bg-space-950/60 p-2 rounded border border-white/[0.04]">
                  <div>
                    <span className="text-space-400 text-[10px] block">Action:</span>
                    <span className="text-tealx-300">{block.action}</span>
                  </div>
                  <div>
                    <span className="text-space-400 text-[10px] block">Validation Status:</span>
                    <span className="text-accent-300 font-bold">{block.outcome}</span>
                  </div>
                </div>

                <div className="space-y-1 text-[10px]">
                  <div className="flex items-center gap-2 text-space-400">
                    <span className="w-16 shrink-0">SHA-256:</span>
                    <span className="text-white truncate bg-black/40 px-1.5 py-0.5 rounded font-mono flex-1">
                      {block.full_hash}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-space-400">
                    <span className="w-16 shrink-0">Prev Hash:</span>
                    <span className="text-space-300 truncate bg-black/40 px-1.5 py-0.5 rounded font-mono flex-1">
                      {block.prev_hash}
                    </span>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Footer Actions */}
        <div className="flex items-center justify-between gap-3 pt-4 border-t border-white/[0.06] mt-4 shrink-0">
          <button
            onClick={verifyProof}
            disabled={verifying}
            className="btn-primary py-2.5 text-xs flex items-center gap-2"
          >
            {verifying ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <ShieldCheck className="w-3.5 h-3.5" />}
            Verify Cryptographic Integrity
          </button>

          <button
            onClick={onClose}
            className="btn-ghost py-2.5 px-4 text-xs"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
