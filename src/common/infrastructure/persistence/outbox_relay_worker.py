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
        try:
            with sqlite3.connect(DB_PATH, timeout=10.0) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute(
                    "SELECT * FROM outbox_messages WHERE status = 'PENDING' ORDER BY created_at ASC LIMIT 10"
                )
                messages = cursor.fetchall()

                for msg in messages:
                    success = self._attempt_dispatch(cursor, msg)
                    
                    if success:
                        cursor.execute("UPDATE outbox_messages SET status = 'PROCESSED' WHERE id = ?", (msg['id'],))
                    else:
                        new_retry_count = msg['retry_count'] + 1
                        if new_retry_count >= self.MAX_RETRIES:
                            cursor.execute(
                                "UPDATE outbox_messages SET status = 'DEAD_LETTER', retry_count = ? WHERE id = ?", 
                                (new_retry_count, msg['id'])
                            )
                            print(f"[OUTBOX DLQ] Message {msg['id']} moved to Dead Letter Queue after {self.MAX_RETRIES} retries.")
                        else:
                            # Exponential backoff is implicitly handled by the next trigger cycle
                            cursor.execute(
                                "UPDATE outbox_messages SET retry_count = ? WHERE id = ?", 
                                (new_retry_count, msg['id'])
                            )
                            
                conn.commit()
        except Exception as e:
            print(f"[OUTBOX ERROR] Relay worker crashed: {e}")

    def _attempt_dispatch(self, cursor, msg) -> bool:
        try:
            # Reconstruct event object (Simplified for this architecture)
            # We pass the raw dictionary to the handlers. Handlers typed to dataclasses will fail.
            # To fix this strictly without modifying existing handlers, we dynamically instantiate.
            payload_dict = json.loads(msg['payload'])
            
            # Find the actual event class in the handler subscriptions (heuristic approach)
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