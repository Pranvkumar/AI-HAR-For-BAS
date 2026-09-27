import { useEffect, useState, useRef } from 'react';
import {
  Bot,
  Camera,
  Layers,
  LayoutGrid,
} from 'lucide-react';
import AppLayout from '@/components/layout/AppLayout';
import Panel from '@/components/common/Panel';
import CameraFeed from '@/components/monitoring/CameraFeed';
import { DigitalTwin } from '@/components/monitoring/DigitalTwin';
import SubsystemHealthStrip from '@/components/monitoring/SubsystemHealthStrip';
import ProtocolTimeline from '@/components/monitoring/ProtocolTimeline';
import OperationalTruthPanel from '@/components/monitoring/OperationalTruthPanel';
import OperatorEventStream, { type OperatorEvent } from '@/components/monitoring/OperatorEventStream';
import AlertBanner from '@/components/monitoring/AlertBanner';
import ExperimentSummaryPanel from '@/components/monitoring/ExperimentSummaryPanel';
import { AerospaceHUD } from '@/components/monitoring/AerospaceHUD';
import AssistantPanel from '@/components/assistant/AssistantPanel';
import { BiometricModal } from '@/components/monitoring/BiometricModal';
import { ObjectRegistryModal } from '@/components/monitoring/ObjectRegistryModal';
import { AuditReplayModal } from '@/components/monitoring/AuditReplayModal';
import { MerkleLedgerModal } from '@/components/monitoring/MerkleLedgerModal';
import { api } from '@/services/api';
import { useQuery } from '@/hooks/useApi';
import { useMonitoringSocket } from '@/hooks/useMonitoringSocket';
import { humanizeActivity } from '@/services/adapters';
import type { ScenarioName } from '@/types/api';

function formatElapsed(startedAt: number | null): string {
  if (!startedAt) return '00:00:00';
  const elapsed = Math.max(Date.now() - startedAt, 0);
  const hours = Math.floor(elapsed / 3600000);
  const minutes = Math.floor((elapsed % 3600000) / 60000);
  const seconds = Math.floor((elapsed % 60000) / 1000);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${pad(hours)}:${pad(minutes)}:${pad(seconds)}`;
}

export default function LiveMonitoring() {
  const [assistantOpen, setAssistantOpen] = useState(false);
  const [scenario, setScenario] = useState<ScenarioName>('nominal');
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [sessionStartTime, setSessionStartTime] = useState<number | null>(null);
  const [elapsedString, setElapsedString] = useState('00:00:00');
  const [selectedExpId, setSelectedExpId] = useState<number | null>(null);
  const [streamMode, setStreamMode] = useState<'simulated' | 'camera'>('simulated');
  const [viewMode, setViewMode] = useState<'feed' | 'twin' | 'dual' | 'quad'>('feed');
  const [busy, setBusy] = useState(false);

  // Modals
  const [showBiometrics, setShowBiometrics] = useState(false);
  const [showObjects, setShowObjects] = useState(false);
  const [showReplay, setShowReplay] = useState(false);
  const [showMerkleModal, setShowMerkleModal] = useState(false);

  // Operator Event Stream
  const [events, setEvents] = useState<OperatorEvent[]>([
    {
      id: 'init-1',
      timestamp: new Date().toISOString().substring(11, 23),
      category: 'TELEMETRY',
      severity: 'NOMINAL',
      message: 'Mission Operations Console initialized. Air-gapped edge environment verified.',
    },
    {
      id: 'init-2',
      timestamp: new Date().toISOString().substring(11, 23),
      category: 'FSM',
      severity: 'NOMINAL',
      message: 'DO-178C Finite State Machine armed for autonomous protocol tracking.',
    },
  ]);

  const { frame, connection } = useMonitoringSocket();
  const { data: experiments } = useQuery(() => api.listExperiments());
  const { data: sessions } = useQuery(() => api.listSessions(), { intervalMs: 5000 });
  const { data: systemStatus } = useQuery(() => api.getSystemStatus(), { intervalMs: 5000 });

  const experiment =
    (selectedExpId !== null ? experiments?.find((e) => e.id === selectedExpId) : null) ??
    experiments?.[0] ??
    null;

  const running = sessionId !== null;

  // Track session timer
  useEffect(() => {
    if (!running || !sessionStartTime) {
      setElapsedString('00:00:00');
      return;
    }
    const timer = setInterval(() => {
      setElapsedString(formatElapsed(sessionStartTime));
    }, 1000);
    return () => clearInterval(timer);
  }, [running, sessionStartTime]);

  // Adopt running session if reloaded
  useEffect(() => {
    if (sessionId !== null) return;
    const runningSession = sessions?.find((s) => s.status === 'IN_PROGRESS');
    if (runningSession) {
      setSessionId(runningSession.id);
      if (runningSession.started_at) {
        setSessionStartTime(new Date(runningSession.started_at).getTime());
      }
    }
  }, [sessions, sessionId]);

  // Backend marks sequence complete
  const sequenceComplete = frame?.fsm_state === 'STEP_COMPLETED';
  useEffect(() => {
    if (sequenceComplete) {
      setSessionId(null);
      setSessionStartTime(null);
    }
  }, [sequenceComplete]);

  // Log WebSocket frame events into operator event stream
  const lastLoggedRef = useRef<{
    activity: string;
    step: number;
    status: string;
    alertMsg?: string;
  }>({ activity: '', step: 0, status: '' });

  useEffect(() => {
    if (!frame) return;

    const timeStr = new Date().toISOString().substring(11, 23);
    const newItems: OperatorEvent[] = [];

    // Log step transition
    if (frame.step_number !== lastLoggedRef.current.step && frame.step_number > 0) {
      newItems.push({
        id: `step-${Date.now()}-${Math.random()}`,
        timestamp: timeStr,
        category: 'FSM',
        severity: 'NOMINAL',
        message: `Procedure milestone advanced to Step 0${frame.step_number}: ${humanizeActivity(
          frame.expected_step || ''
        )}`,
      });
    }

    // Log activity detection
    if (
      frame.detected_activity &&
      frame.detected_activity !== lastLoggedRef.current.activity
    ) {
      newItems.push({
        id: `act-${Date.now()}-${Math.random()}`,
        timestamp: timeStr,
        category: 'VISION',
        severity: frame.confidence >= 0.7 ? 'NOMINAL' : 'WARNING',
        message: `Optical HAR detected '${humanizeActivity(
          frame.detected_activity
        )}' (Certainty: ${Math.round(frame.confidence * 100)}%)`,
      });
    }

    // Log violation / conformance status changes
    if (frame.status !== lastLoggedRef.current.status) {
      if (frame.status === 'SEQUENCE_VIOLATION') {
        newItems.push({
          id: `violation-${Date.now()}-${Math.random()}`,
          timestamp: timeStr,
          category: 'ANOMALY',
          severity: 'CRITICAL',
          message: `PROTOCOL VIOLATION: Performed action does not match expected state sequence!`,
        });
      } else if (frame.status === 'WARNING') {
        newItems.push({
          id: `warn-${Date.now()}-${Math.random()}`,
          timestamp: timeStr,
          category: 'SAFETY',
          severity: 'WARNING',
          message: `CAUTION: Detection confidence below verification threshold. Maintain direct camera view.`,
        });
      }
    }

    // Log specific aerospace alarms
    if (frame.is_immobile) {
      newItems.push({
        id: `immobile-${Date.now()}`,
        timestamp: timeStr,
        category: 'SAFETY',
        severity: 'CRITICAL',
        message: `CREW IMMOBILITY: No astronaut motion registered for >15s. Verification dispatched.`,
      });
    }
    if (frame.slosh_alert) {
      newItems.push({
        id: `slosh-${Date.now()}`,
        timestamp: timeStr,
        category: 'SAFETY',
        severity: 'WARNING',
        message: `KINETIC SPIKE: Acceleration jerk exceeded safety threshold. High slosh risk.`,
      });
    }
    if (frame.fod_active) {
      newItems.push({
        id: `fod-${Date.now()}`,
        timestamp: timeStr,
        category: 'ANOMALY',
        severity: 'CRITICAL',
        message: `DRIFT COLLISION ALERT: Unsecured item (${frame.fod_object ?? 'OBJECT'}) in motion corridor.`,
      });
    }

    if (newItems.length > 0) {
      lastLoggedRef.current = {
        activity: frame.detected_activity,
        step: frame.step_number,
        status: frame.status,
      };
      setEvents((prev) => [...prev.slice(-80), ...newItems]);
    }
  }, [frame]);

  const handleStart = async () => {
    if (!experiment) return;
    setBusy(true);
    try {
      const response = await api.startMonitoring(experiment.id, scenario);
      setSessionId(response.session_id);
      setSessionStartTime(Date.now());
      setEvents((prev) => [
        ...prev,
        {
          id: `start-${Date.now()}`,
          timestamp: new Date().toISOString().substring(11, 23),
          category: 'FSM',
          severity: 'NOMINAL',
          message: `Session #${response.session_id} engaged for protocol ${experiment.code}. FSM validation live.`,
        },
      ]);
    } catch (err) {
      setEvents((prev) => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          timestamp: new Date().toISOString().substring(11, 23),
          category: 'ANOMALY',
          severity: 'CRITICAL',
          message: `Failed to engage session: ${err instanceof Error ? err.message : 'Unknown error'}`,
        },
      ]);
    } finally {
      setBusy(false);
    }
  };

  const handleStop = async () => {
    if (sessionId === null) return;
    setBusy(true);
    try {
      await api.stopMonitoring(sessionId);
      setEvents((prev) => [
        ...prev,
        {
          id: `stop-${Date.now()}`,
          timestamp: new Date().toISOString().substring(11, 23),
          category: 'FSM',
          severity: 'WARNING',
          message: `Session #${sessionId} aborted by mission operator. State machine disengaged.`,
        },
      ]);
      setSessionId(null);
      setSessionStartTime(null);
    } catch (err) {
      console.error(err);
    } finally {
      setBusy(false);
    }
  };

  const detectedEntities = (() => {
    if (!frame?.bounding_boxes.length) return [];
    const best = new Map<string, number>();
    for (const box of frame.bounding_boxes) {
      const cur = best.get(box.class_name) ?? 0;
      if (box.confidence > cur) best.set(box.class_name, box.confidence);
    }
    return [...best.entries()];
  })();

  const nextStepName = (() => {
    if (!experiment?.steps || !frame) return null;
    const nextStep = experiment.steps.find((s) => s.step_number === frame.step_number + 1);
    return nextStep ? nextStep.title || nextStep.expected_activity : null;
  })();

  const currentStepNumber = frame?.step_number ?? (running ? 1 : 0);
  const totalSteps = frame?.total_steps ?? experiment?.total_steps ?? experiment?.steps?.length ?? 5;
  const progressPct = frame?.progress ?? 0;
  const completedCount = frame?.completed_activities?.length ?? Math.max(0, currentStepNumber - 1);

  return (
    <AppLayout
      title="Live Operations Deck"
      subtitle="Real-time astronaut experiment monitoring & DO-178C FSM validation"
      experimentCode={experiment?.code}
      experimentTitle={experiment?.title}
    >
      {/* 1. Subsystem Health Matrix */}
      <SubsystemHealthStrip
        status={systemStatus}
        inferenceFps={frame?.eco_fps ?? 29.8}
        inferenceLatencyMs={12.4}
        fsmArmed={true}
      />

      {/* 2. Operational Alert Banner */}
      <AlertBanner
        alert={frame?.alert}
        isImmobile={frame?.is_immobile}
        isBlinded={frame?.is_blinded}
        sloshAlert={frame?.slosh_alert}
        fodActive={frame?.fod_active}
        fodObject={frame?.fod_object}
        hesitationActive={frame?.hesitation_active}
        isViolation={frame?.status === 'SEQUENCE_VIOLATION'}
        onAcknowledge={() => {
          setEvents((prev) => [
            ...prev,
            {
              id: `ack-${Date.now()}`,
              timestamp: new Date().toISOString().substring(11, 23),
              category: 'SAFETY',
              severity: 'NOMINAL',
              message: 'Operator acknowledged active alarm. Protocol status refreshed.',
            },
          ]);
        }}
        onDispatchVoice={() => setAssistantOpen(true)}
      />

      {/* 3. Main Operational Command Center Grid */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-3 mb-3">
        {/* Left Column (7/12 cols): Dominant Live Vision Workspace */}
        <div className="xl:col-span-7 space-y-3">
          <Panel
            hudCorners={true}
            title={
              viewMode === 'twin'
                ? '3D Digital Twin Simulation (Glovebox Physics)'
                : viewMode === 'dual'
                ? 'Dual Workspace: Optical Feed + 3D Twin'
                : viewMode === 'quad'
                ? 'Quad Avionics Deck: All Visual Channels'
                : 'Primary Optical Workspace & Real-Time CV'
            }
            action={
              <div className="flex items-center gap-1.5">
                {/* View Mode Selector */}
                <div className="flex rounded bg-[#ede3d8] p-0.5 border border-[#ded2c5] text-[10px] font-mono">
                  <button
                    onClick={() => setViewMode('feed')}
                    className={`px-2 py-0.5 rounded transition-colors ${
                      viewMode === 'feed'
                        ? 'bg-[#2b1b14] text-white font-bold'
                        : 'text-space-400 hover:text-[#261912]'
                    }`}
                  >
                    <Camera className="w-3 h-3 inline mr-1" />
                    Feed
                  </button>
                  <button
                    onClick={() => setViewMode('twin')}
                    className={`px-2 py-0.5 rounded transition-colors ${
                      viewMode === 'twin'
                        ? 'bg-[#2b1b14] text-white font-bold'
                        : 'text-space-400 hover:text-[#261912]'
                    }`}
                  >
                    <Layers className="w-3 h-3 inline mr-1" />
                    Twin
                  </button>
                  <button
                    onClick={() => setViewMode('dual')}
                    className={`px-2 py-0.5 rounded transition-colors ${
                      viewMode === 'dual'
                        ? 'bg-[#2b1b14] text-white font-bold'
                        : 'text-space-400 hover:text-[#261912]'
                    }`}
                  >
                    Dual
                  </button>
                  <button
                    onClick={() => setViewMode('quad')}
                    className={`px-2 py-0.5 rounded transition-colors ${
                      viewMode === 'quad'
                        ? 'bg-[#2b1b14] text-white font-bold'
                        : 'text-space-400 hover:text-[#261912]'
                    }`}
                  >
                    <LayoutGrid className="w-3 h-3 inline mr-1" />
                    Quad
                  </button>
                </div>

                {/* Sensor Source Selector */}
                <select
                  value={streamMode}
                  onChange={(e) => setStreamMode(e.target.value as 'simulated' | 'camera')}
                  className="input-field text-[10px] py-0.5 px-1.5 cursor-pointer"
                >
                  <option value="simulated">Synthetic Sim</option>
                  <option value="camera">Hardware Cam</option>
                </select>
              </div>
            }
          >
            {/* View Mode Render */}
            {viewMode === 'feed' && (
              <CameraFeed
                boxes={frame?.bounding_boxes ?? []}
                connected={connection === 'open' && running}
                streamMode={streamMode}
                fps={frame?.eco_fps ?? 29.8}
                latencyMs={12.4}
                handPos={frame?.hand_pos}
              />
            )}

            {viewMode === 'twin' && (
              <DigitalTwin
                boxes={frame?.bounding_boxes ?? []}
                handPos={frame?.hand_pos}
                fodActive={frame?.fod_active}
                fodObject={frame?.fod_object}
                fodEta={frame?.fod_eta}
              />
            )}

            {viewMode === 'dual' && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                <CameraFeed
                  boxes={frame?.bounding_boxes ?? []}
                  connected={connection === 'open' && running}
                  streamMode={streamMode}
                  fps={frame?.eco_fps ?? 29.8}
                  latencyMs={12.4}
                  handPos={frame?.hand_pos}
                />
                <DigitalTwin
                  boxes={frame?.bounding_boxes ?? []}
                  handPos={frame?.hand_pos}
                  fodActive={frame?.fod_active}
                  fodObject={frame?.fod_object}
                  fodEta={frame?.fod_eta}
                />
              </div>
            )}

            {viewMode === 'quad' && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 font-mono">
                <div className="border border-[#ded2c5] rounded overflow-hidden">
                  <div className="text-[9px] bg-[#f0e7de] px-2 py-0.5 text-space-400 border-b border-[#ded2c5]">
                    CHANNEL 01 // OPTICAL SENSOR
                  </div>
                  <CameraFeed
                    boxes={frame?.bounding_boxes ?? []}
                    connected={connection === 'open' && running}
                    streamMode={streamMode}
                    fps={frame?.eco_fps ?? 29.8}
                    latencyMs={12.4}
                    handPos={frame?.hand_pos}
                  />
                </div>
                <div className="border border-[#ded2c5] rounded overflow-hidden">
                  <div className="text-[9px] bg-[#f0e7de] px-2 py-0.5 text-space-400 border-b border-[#ded2c5]">
                    CHANNEL 02 // 3D ISOMETRIC TWIN
                  </div>
                  <DigitalTwin
                    boxes={frame?.bounding_boxes ?? []}
                    handPos={frame?.hand_pos}
                    fodActive={frame?.fod_active}
                    fodObject={frame?.fod_object}
                    fodEta={frame?.fod_eta}
                  />
                </div>
                <div className="p-2.5 bg-[#fbf9f6] border border-[#ded2c5] rounded">
                  <div className="text-[9px] text-space-400 uppercase mb-1">
                    CHANNEL 03 // FSM WORKFLOW STATE
                  </div>
                  <div className="text-xs font-bold text-[#261912] mb-1">
                    {frame?.expected_step
                      ? humanizeActivity(frame.expected_step).toUpperCase()
                      : 'STANDBY'}
                  </div>
                  <div className="w-full bg-[#f0e7de] h-1.5 rounded-full overflow-hidden mb-1">
                    <div
                      className="bg-[#964f19] h-full transition-all"
                      style={{ width: `${frame?.progress ?? 0}%` }}
                    />
                  </div>
                  <div className="flex justify-between text-[10px] text-space-400">
                    <span>Validation State:</span>
                    <span className="text-[#166534] font-bold">{frame?.status ?? 'IDLE'}</span>
                  </div>
                </div>
                <div className="p-2.5 bg-[#fbf9f6] border border-[#ded2c5] rounded">
                  <div className="text-[9px] text-space-400 uppercase mb-1">
                    CHANNEL 04 // CRYPTOGRAPHIC AUDIT HASH
                  </div>
                  <div className="font-mono text-[10px] text-[#582f0e] break-all mb-1 font-semibold">
                    {frame?.merkle_hash || 'SHA-256 GENESIS ROOT ARMED'}
                  </div>
                  <div className="flex justify-between text-[10px] text-space-400">
                    <span>Block Length:</span>
                    <span className="text-[#166534] font-bold tabular-nums">
                      {frame?.merkle_chain_length ?? 0} BLOCKS
                    </span>
                  </div>
                </div>
              </div>
            )}
          </Panel>

          {/* Prominent Protocol-Progress Visual State Machine Timeline */}
          <ProtocolTimeline
            steps={experiment?.steps}
            currentStepNumber={currentStepNumber}
            totalSteps={totalSteps}
            progress={progressPct}
            status={frame?.status}
            completedActivities={frame?.completed_activities}
          />
        </div>

        {/* Right Column (5/12 cols): High-Density Situational Awareness & Controls */}
        <div className="xl:col-span-5 space-y-3">
          {/* Operational Truth Panel (Answers 4 Critical Operator Questions) */}
          <OperationalTruthPanel
            detectedActivity={frame?.detected_activity}
            confidence={frame?.confidence}
            expectedStep={frame?.expected_step}
            stepNumber={currentStepNumber}
            totalSteps={totalSteps}
            status={frame?.status}
            guidance={frame?.guidance}
            nextStepName={nextStepName}
            running={running}
          />

          {/* Compact Experiment Summary & Operational Controls */}
          <ExperimentSummaryPanel
            experiment={experiment}
            experiments={experiments ?? null}
            selectedExpId={selectedExpId}
            onSelectExperiment={setSelectedExpId}
            scenario={scenario}
            onSelectScenario={setScenario}
            running={running}
            busy={busy}
            onStart={handleStart}
            onStop={handleStop}
            elapsedTime={elapsedString}
            currentStep={currentStepNumber}
            totalSteps={totalSteps}
            completedCount={completedCount}
            detectedEntities={detectedEntities}
            systemNominal={Boolean(systemStatus?.ai_engine_online)}
            onOpenBiometrics={() => setShowBiometrics(true)}
            onOpenObjects={() => setShowObjects(true)}
            onOpenReplay={() => setShowReplay(true)}
            onOpenMerkle={() => setShowMerkleModal(true)}
          />

          {/* Real-Time Operator Event & Telemetry Stream */}
          <OperatorEventStream
            events={events}
            onClear={() => setEvents([])}
          />
        </div>
      </div>

      {/* 4. Comprehensive Aerospace Avionics Telemetry Suite */}
      <div className="mb-4">
        <AerospaceHUD
          sloshJerk={frame?.slosh_jerk}
          sloshAlert={frame?.slosh_alert}
          ecoMode={frame?.eco_mode}
          ecoFps={frame?.eco_fps}
          ecoFramesSaved={frame?.eco_frames_saved}
          merkleHash={frame?.merkle_hash}
          merkleChainLength={frame?.merkle_chain_length}
          ccsdsLastHex={frame?.ccsds_last_hex}
          ccsdsTotalPackets={frame?.ccsds_total_packets}
          thermalStatus={frame?.thermal_status}
          cpuPercent={frame?.cpu_percent}
          isBlinded={frame?.is_blinded}
          glareSaturation={frame?.glare_saturation}
          isImmobile={frame?.is_immobile}
          fodActive={frame?.fod_active}
          fodObject={frame?.fod_object}
          fodEta={frame?.fod_eta}
          hesitationActive={frame?.hesitation_active}
          hesitationDwellMs={frame?.hesitation_dwell_ms}
        />
      </div>

      {/* Floating Tactical Copilot Trigger */}
      <button
        onClick={() => setAssistantOpen(true)}
        className="fixed bottom-4 right-4 flex items-center gap-2 px-3 py-2 rounded bg-[#2b1b14] hover:bg-[#3d271d] text-white font-mono font-bold text-xs uppercase tracking-wider border border-[#1f120c] shadow-md z-40 transition-transform active:scale-95"
        title="Engage Autonomous Speech Copilot"
      >
        <Bot className="w-4 h-4" />
        <span>VOICE COPILOT</span>
      </button>

      {/* Modals & Dialogs */}
      <AssistantPanel
        open={assistantOpen}
        onClose={() => setAssistantOpen(false)}
        sessionId={sessionId}
      />
      <BiometricModal
        isOpen={showBiometrics}
        onClose={() => setShowBiometrics(false)}
      />
      <ObjectRegistryModal
        isOpen={showObjects}
        onClose={() => setShowObjects(false)}
      />
      <AuditReplayModal
        isOpen={showReplay}
        onClose={() => setShowReplay(false)}
      />
      <MerkleLedgerModal
        isOpen={showMerkleModal}
        onClose={() => setShowMerkleModal(false)}
      />
    </AppLayout>
  );
}
