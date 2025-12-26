from google import genai
import threading
import os
from src.logger import log

class AIAgent:
    def __init__(self, token_file="gemini_token.txt"):
        self.api_key = self._load_key(token_file)
        if self.api_key:
            try:
                # Using latest google-genai Client
                self.client = genai.Client(api_key=self.api_key)
                self.model_id = 'gemini-2.0-flash-exp'
                self.available = True
                log.info("Gemini AI Agent (google-genai) initialized.")
            except Exception as e:
                log.error(f"Failed to initialize google-genai: {e}")
                self.available = False
        else:
            log.warning("No Gemini token found. AI features disabled.")
            self.available = False

    def _load_key(self, path):
        if os.path.exists(path):
            with open(path, 'r') as f:
                return f.read().strip()
        return None

    def analyze_resource_async(self, resource_data, callback):
        """
        Starts a thread to analyze the resource and calls 'callback(result_text)' when done.
        """
        if not self.available:
            callback("AI Agent Unavailable. Check token.")
            return

        thread = threading.Thread(target=self._run_analysis, args=(resource_data, callback))
        thread.daemon = True
        thread.start()

    def _run_analysis(self, resource_data, callback):
        try:
            # Latest generate_content call
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=resource_data
            )
            
            if response and response.text:
                callback(response.text)
            else:
                callback("Analysis Inconclusive.")
        except Exception as e:
            log.error(f"Gemini (google-genai) Analysis Failed: {e}")
            callback("System Error during Analysis.")