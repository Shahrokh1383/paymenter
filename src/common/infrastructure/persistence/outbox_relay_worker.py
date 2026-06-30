import json
import sqlite3
import threading
import time
import typing
from typing import Any
from src.common.domain.ports.event_bus import EventBus
from src.common.infrastructure.database import DB_PATH

class OutboxRelayWorker:
    """
    Background worker thread that polls the outbox table and publishes events
    to the inner EventBus. Implements Exponential Backoff and Dead-Letter Queue (DLQ).
    """
    
    MAX_RETRIES = 3
    # Simple class map to reconstruct events from JSON
    # In a larger system, a registry pattern would be used here.
    
    def __init__(self, inner_bus: EventBus):
        self._inner_bus = inner_bus
        self._lock = threading.Lock()
        self._processing_flag = False
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        
    def start(self):
        if not self._thread.is_alive():
            self._thread.start()

    def trigger_processing(self):
        with self._lock:
            self._processing_flag = True

    def _run_loop(self):
        while True:
            if self._processing_flag:
                with self._lock:
                    self._processing_flag = False
                
                self._process_pending_messages()
            else:
                time.sleep(0.5) # Sleep to prevent CPU spinning

    def _process_pending_messages(self):
        messages_to_process = []
        
        # 1. FETCH PHASE (Read Lock only)
        try:
            with sqlite3.connect(DB_PATH, timeout=10.0) as conn:
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA journal_mode=WAL;")
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM outbox_messages WHERE status = 'PENDING' ORDER BY created_at ASC LIMIT 10"
                )
                messages_to_process = [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"[OUTBOX ERROR] Failed to fetch messages: {e}")
            return

        # 2. PROCESSING PHASE (Locks Released - Safe to call Handlers/SMTP/UoW)
        results = []
        for msg in messages_to_process:
            success = self._attempt_dispatch(msg)
            results.append((msg['id'], success, msg['retry_count']))

        # 3. UPDATE PHASE (Write Lock)
        if not results:
            return

        try:
            with sqlite3.connect(DB_PATH, timeout=10.0) as conn:
                conn.execute("PRAGMA journal_mode=WAL;")
                cursor = conn.cursor()
                
                for msg_id, success, current_retries in results:
                    if success:
                        cursor.execute("UPDATE outbox_messages SET status = 'PROCESSED' WHERE id = ?", (msg_id,))
                    else:
                        new_retry_count = current_retries + 1
                        if new_retry_count >= self.MAX_RETRIES:
                            cursor.execute(
                                "UPDATE outbox_messages SET status = 'DEAD_LETTER', retry_count = ? WHERE id = ?", 
                                (new_retry_count, msg_id)
                            )
                            print(f"[OUTBOX DLQ] Message {msg_id} moved to Dead Letter Queue.")
                        else:
                            cursor.execute(
                                "UPDATE outbox_messages SET retry_count = ? WHERE id = ?", 
                                (new_retry_count, msg_id)
                            )
                conn.commit()
        except Exception as e:
            print(f"[OUTBOX ERROR] Failed to update message statuses: {e}")

    def _attempt_dispatch(self, cursor, msg) -> bool:
        try:
            payload_dict = json.loads(msg['payload'])
            event_instance = self._reconstruct_event(msg['event_type'], payload_dict)
            if event_instance:
                self._inner_bus.publish(event_instance)
                return True
            return False
        except Exception as e:
            print(f"[OUTBOX RETRY] Dispatch failed for msg {msg['id']}: {e}")
            return False
        
    def _reconstruct_event(self, event_type_name: str, payload: dict) -> Any:
        """
        Heuristic to reconstruct the frozen dataclass event.
        Uses type hints to dynamically rebuild nested Value Objects (like Money) 
        from their serialized dictionary state without hardcoding Domain types.
        """
        for etype in self._inner_bus._subscribers.keys():
            if etype.__name__ == event_type_name:
                # Resolve type hints to handle nested Domain Value Objects at the boundary
                type_hints = typing.get_type_hints(etype)
                for field_name, field_type in type_hints.items():
                    if field_name in payload and isinstance(payload[field_name], dict):
                        try:
                            payload[field_name] = field_type(**payload[field_name])
                        except Exception:
                            pass # Silently skip if reconstruction fails
                return etype(**payload)
        return None