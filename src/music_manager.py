from ursina import *
import os
import random
import sqlite3
from src.database import get_connection
from src.logger import log

class MusicManager:
    def __init__(self, music_dir="."):
        self.music_dir = music_dir
        self.current_track = None # Audio Entity
        self.current_filename = None
        self.tracks = self._find_tracks()
        
    def _find_tracks(self):
        tracks = []
        for root, dirs, files in os.walk(self.music_dir):
            for file in files:
                if file.lower().endswith('.mp3'):
                    tracks.append(os.path.join(root, file))
        log.info(f"Found {len(tracks)} music tracks.")
        return tracks

    def start_music(self):
        if not self.tracks:
            log.warning("No MP3s found.")
            return

        # Load state
        saved_track, saved_time = self._load_state()

        if saved_track and saved_track in self.tracks and os.path.exists(saved_track):
            log.info(f"Resuming {saved_track} at {saved_time}s")
            self.play_track(saved_track, start_time=float(saved_time))
        else:
            # Random start
            track = random.choice(self.tracks)
            log.info(f"Starting random track: {track}")
            self.play_track(track)

    def play_track(self, filename, start_time=0):
        if self.current_track:
            try:
                self.current_track.stop()
            except:
                pass
            destroy(self.current_track)

        self.current_filename = filename
        
        # Ursina Audio doesn't natively support 'start_at' in constructor easily for all backends,
        # but accessing the underlying panda3d object works.
        self.current_track = Audio(filename, loop=True, autoplay=False)
        
        # Access Panda3D sound object
        if self.current_track.clip:
            self.current_track.clip.setTime(start_time)
            self.current_track.volume = 0.5 # Default Level
            self.current_track.play()
        else:
            # Fallback if loading failed or not ready
            self.current_track.volume = 0.5 # Default Level
            self.current_track.play()

    def set_volume(self, vol):
        """Sets volume (0.0 to 1.0)."""
        if self.current_track:
            self.current_track.volume = vol

    def save_state(self):
        if self.current_track and self.current_track.clip:
            current_time = self.current_track.clip.getTime()
            try:
                conn = get_connection()
                c = conn.cursor()
                c.execute("INSERT OR REPLACE INTO app_state (key, value) VALUES (?, ?)", ("music_track", self.current_filename))
                c.execute("INSERT OR REPLACE INTO app_state (key, value) VALUES (?, ?)", ("music_time", str(current_time)))
                conn.commit()
                conn.close()
                log.info(f"Music state saved: {self.current_filename} @ {current_time:.2f}s")
            except Exception as e:
                log.error(f"Failed to save music state: {e}")

    def _load_state(self):
        try:
            conn = get_connection()
            c = conn.cursor()
            c.execute("SELECT value FROM app_state WHERE key='music_track'")
            row_track = c.fetchone()
            c.execute("SELECT value FROM app_state WHERE key='music_time'")
            row_time = c.fetchone()
            conn.close()
            
            if row_track and row_time:
                return row_track[0], row_time[0]
        except Exception as e:
            log.error(f"Failed to load music state: {e}")
        return None, 0
