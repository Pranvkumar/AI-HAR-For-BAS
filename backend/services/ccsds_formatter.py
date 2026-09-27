"""
CCSDS Space Packet Protocol Formatter
Standard: CCSDS 133.0-B-2 (Space Packet Protocol)

Packs telemetry payloads into strictly-formatted binary CCSDS space packets
suitable for onboard avionics and deep-space ground station downlink.
"""
import struct
import time
from enum import IntEnum
from typing import List, Tuple, Dict, Any


class APID(IntEnum):
    """Application Process Identifiers for BAS experiment subsystems."""
    SYSTEM_HEARTBEAT   = 0x001
    AUTH_STATUS        = 0x002
    
    YOLO_DETECTIONS    = 0x010
    HAND_TRACKING      = 0x011
    HOI_GRASP          = 0x012
    SPATIAL_BOUNDARY   = 0x013
    GLARE_MONITOR      = 0x014
    
    FSM_STATE          = 0x020
    FSM_TRANSITION     = 0x021
    
    CONTAINMENT_BREACH = 0x030
    UNSECURED_DRIFT    = 0x031
    CREW_IMMOBILITY    = 0x032
    
    SLOSH_GUARD        = 0x040
    ECO_GOVERNOR       = 0x041
    MERKLE_LEDGER      = 0x042
    HESITATION_DETECT  = 0x043
    FOD_PROJECTION     = 0x044


class SequenceFlags(IntEnum):
    CONTINUATION = 0b00
    FIRST        = 0b01
    LAST         = 0b10
    STANDALONE   = 0b11


class CCSDSPacketFormatter:
    """Formats telemetry into CCSDS 133.0-B-2 compliant space packets."""

    PACKET_VERSION = 0b000
    PACKET_TYPE_TM = 0
    PACKET_TYPE_TC = 1
    SEC_HEADER_FLAG = 1

    def __init__(self):
        self._sequence_counters: Dict[int, int] = {}
        self._total_packets_sent = 0
        self._total_bytes_sent = 0
        self._last_packet: bytes = b""
        self._last_apid: APID = APID.SYSTEM_HEARTBEAT

    def _next_sequence_count(self, apid: int) -> int:
        count = self._sequence_counters.get(apid, 0)
        self._sequence_counters[apid] = (count + 1) % 16384
        return count

    def pack_primary_header(self, apid: int, data_length: int, seq_flags: SequenceFlags = SequenceFlags.STANDALONE) -> bytes:
        seq_count = self._next_sequence_count(apid)
        word1 = ((self.PACKET_VERSION & 0x07) << 13) | ((self.PACKET_TYPE_TM & 0x01) << 12) | ((self.SEC_HEADER_FLAG & 0x01) << 11) | (apid & 0x07FF)
        word2 = ((int(seq_flags) & 0x03) << 14) | (seq_count & 0x3FFF)
        total_data_octets = (10 + data_length) - 1
        word3 = total_data_octets & 0xFFFF
        return struct.pack(">HHH", word1, word2, word3)

    def pack_secondary_header(self, subsystem_id: int = 1, quality_flag: int = 0) -> bytes:
        now = time.time()
        coarse_time = int(now)
        fine_time = int((now - coarse_time) * 65536) & 0xFFFF
        return struct.pack(">IHBBxx", coarse_time, fine_time, subsystem_id & 0xFF, quality_flag & 0xFF)

    def pack_telemetry(self, apid: APID, user_data: bytes, subsystem_id: int = 1) -> bytes:
        sec_header = self.pack_secondary_header(subsystem_id)
        prim_header = self.pack_primary_header(int(apid), len(user_data))
        packet = prim_header + sec_header + user_data
        self._total_packets_sent += 1
        self._total_bytes_sent += len(packet)
        self._last_packet = packet
        self._last_apid = apid
        return packet

    def pack_heartbeat(self, fps: float, cpu_temp: float, uptime: int) -> bytes:
        data = struct.pack(">ffI", fps, cpu_temp, uptime)
        return self.pack_telemetry(APID.SYSTEM_HEARTBEAT, data)

    def pack_slosh_guard(self, jerk_magnitude: float, alert_active: bool) -> bytes:
        data = struct.pack(">fB", jerk_magnitude, 1 if alert_active else 0)
        return self.pack_telemetry(APID.SLOSH_GUARD, data)

    def pack_eco_governor(self, mode_code: int, target_fps: float, skipped_frames: int) -> bytes:
        data = struct.pack(">BfI", mode_code, target_fps, skipped_frames)
        return self.pack_telemetry(APID.ECO_GOVERNOR, data)

    def pack_merkle_ledger(self, chain_length: int, hash_prefix: bytes) -> bytes:
        if len(hash_prefix) < 8:
            hash_prefix = hash_prefix.ljust(8, b'\x00')
        data = struct.pack(">I8s", chain_length, hash_prefix[:8])
        return self.pack_telemetry(APID.MERKLE_LEDGER, data)

    def pack_fod_projection(self, active: bool, eta_s: float, obj_code: int) -> bytes:
        data = struct.pack(">BfH", 1 if active else 0, eta_s, obj_code)
        return self.pack_telemetry(APID.FOD_PROJECTION, data)

    @staticmethod
    def hex_dump(packet: bytes, max_bytes: int = 32) -> str:
        truncated = packet[:max_bytes]
        hex_str = " ".join(f"{b:02X}" for b in truncated)
        if len(packet) > max_bytes:
            hex_str += f" ... (+{len(packet) - max_bytes} B)"
        return hex_str

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_packets": self._total_packets_sent,
            "total_bytes": self._total_bytes_sent,
            "last_hex": self.hex_dump(self._last_packet, max_bytes=24) if self._last_packet else "",
            "last_apid_hex": f"0x{int(self._last_apid):03X}",
            "last_apid_name": self._last_apid.name if isinstance(self._last_apid, APID) else str(self._last_apid),
            "active_apids": len(self._sequence_counters),
        }


ccsds_formatter = CCSDSPacketFormatter()
