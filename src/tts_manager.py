import pyttsx3
import threading
import random
import queue
import time
import os
from src.logger import log

class TTSManager:
    PHRASES = {
        "startup": ["System Online. Cloud Link established.", "Uplink active.", "Welcome back."],
        "scan_start": ["Initiating deep structural scan.", "Deep dive sequence initiated.", "Commencing analysis."],
        "data_fetch": ["Accessing remote log streams.", "Retrieving secure history.", "Aggregating telemetry."],
        "ai_transmission": ["Transmitting data to neural core.", "Synthesizing information stream."],
        "analysis_complete": ["Analysis complete. Report incoming.", "Synthesis finished. Displaying results."],
        "selection": ["Target Locked.", "Resource acquired.", "Targeting system active."],
        "mode_change": ["Recalibrating display mode.", "Tactical overlay changed.", "Switching filter context."]
    }

    def __init__(self):
        self.q = queue.Queue()
        self.stop_event = threading.Event()
        self.interrupt_event = threading.Event()
        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.worker_thread.start()
        log.info("TTS Manager initialized (Priority-Queue mode).")

    def _worker(self):
        """Single persistent worker with interruption capability."""
        engine = None
        try:
            engine = pyttsx3.init()
            engine.setProperty('rate', 180)
            engine.setProperty('volume', 1.0)
        except Exception as e:
            log.error(f"TTS Engine Init Error: {e}")
            return

        while not self.stop_event.is_set():
            try:
                # Wait for text
                text = self.q.get(timeout=0.5)
                if text:
                    log.info(f"TTS EXEC: '{text[:40]}...'")
                    engine.say(text)
                    engine.runAndWait()
                    self.q.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                log.error(f"TTS Worker Loop Error: {e}")
                try: engine = pyttsx3.init(); engine.setProperty('rate', 180); engine.setProperty('volume', 1.0)
                except: pass

    def speak_category(self, category):
        if category in self.PHRASES:
            self.speak_async(random.choice(self.PHRASES[category]))
        else:
            self.speak_async(category)

    def speak_async(self, text, priority=False):
        if not text: return
        
        if priority:
            log.info("TTS PRIORITY: Clearing queue and speaking immediately.")
            # Clear queue
            while not self.q.empty():
                try: self.q.get_nowait(); self.q.task_done()
                except: break
            # Note: pyttsx3 doesn't easily 'stop' mid-sentence in a thread safely, 
            # but clearing the queue ensures this is next.
            
        self.q.put(text)

    def stop_all(self):
        while not self.q.empty():
            try: self.q.get_nowait(); self.q.task_done()
            except: break
        log.info("TTS Queue cleared.")
