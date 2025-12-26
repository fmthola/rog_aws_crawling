from ursina import *
from src.data_manager import DataManager
from src.ui.grid_view import GridView
from src.logger import log
from src.ui.player_controller import PlayerController
from src.music_manager import MusicManager
from src.database import get_connection
import sys
import time
import subprocess
import PIL.Image
import PIL.ImageDraw

# --- Backend Verification ---
print("--- SYSTEM STARTUP ---")
print("Initializing Data Uplink...")

# Start Backend Data Manager (Resources)
data_manager = DataManager(interval=30)
data_manager.start()

# Start S3 Flow Log Ingester (Subprocess)
# print("Initializing S3 Log Stream...")
# ingester_process = subprocess.Popen([sys.executable, "src/flow_ingester.py"])

def verify_backend(timeout=15):
    """Waits for the backend to populate the database."""
    start_time = time.time()
    print("Verifying AWS Data Stream...")
    while time.time() - start_time < timeout:
        try:
            conn = get_connection()
            c = conn.cursor()
            c.execute("SELECT count(*) FROM resources")
            count = c.fetchone()[0]
            conn.close()
            
            if count > 0:
                print(f"[SUCCESS] Backend Connected. {count} resources synchronized.")
                return True
        except Exception:
            pass
        
        sys.stdout.write(".")
        sys.stdout.flush()
        time.sleep(1)
    
    print("\n[WARNING] Backend timeout. Starting UI with empty/cache data.")
    return False

# Block until data is ready or timeout
verify_backend()

# --- UI Initialization ---
app = Ursina()

# Window Setup
window.title = "AWS ROG Explorer"
window.borderless = True
window.fullscreen = True
window.color = color.hex("#050505") # Almost black for contrast

# --- Futuristic Background ---
# Generate a '+' texture
grid_texture = Texture(
    PIL.Image.new('RGBA', (256, 256), (0, 0, 0, 0)) # High res
)
img = PIL.Image.new('RGBA', (256, 256), (0, 0, 0, 0))
d = PIL.ImageDraw.Draw(img)
# Draw '+'
# Grid color: Deep Neon Blue
grid_color = (0, 200, 255, 80)
d.line((128, 40, 128, 216), fill=grid_color, width=2)
d.line((40, 128, 216, 128), fill=grid_color, width=2)
grid_texture = Texture(img)

# Create infinite-looking background sphere
bg_grid = Entity(
    model='sphere',
    scale=500, # Pushed way back
    texture=grid_texture,
    texture_scale=(100, 100), # Denser repeat
    double_sided=True,
    side='inside',
    color=color.white
)

# Music System
music_manager = MusicManager(music_dir=".") # Search root for music
music_manager.start_music()

# UI Components
grid = GridView()
grid.music_manager = music_manager # Link for audio ducking

# Player / Camera Controller
player = PlayerController(grid_view=grid)

# HUD
mode_text = Text(text="Mode: GENERAL", position=(-0.85, 0.48), scale=1.5, color=color.green)
filter_text = Text(text="Filter: ALL", position=(-0.85, 0.44), scale=1.0, color=color.white)
sync_text = Text(text="System: Offline", position=(0.5, 0.48), scale=1, color=color.yellow)

def update():
    # Animate Background
    bg_grid.rotation_y += 1 * time.dt
    bg_grid.rotation_x += 0.5 * time.dt
    
    # Update HUD
    mode_text.text = f"MODE: {grid.mode.upper()}"
    filter_text.text = f"VIEW: {grid.status_filter}"
    
    # Update Sync Status
    if hasattr(data_manager, 'status'):
        # Use detailed status if available
        status_str = getattr(data_manager, 'detailed_status', data_manager.status)
        sync_text.text = f"UPLINK: {status_str}"
        
        if "SYNCING" in data_manager.status:
            sync_text.color = color.orange
        elif "ERROR" in data_manager.status:
            sync_text.color = color.red
        else:
            sync_text.color = color.cyan

    # Quit & Save
    if held_keys['escape']:
        print("Saving State and Shutting Down...")
        music_manager.save_state()
        data_manager.stop()
        application.quit()

# Run
try:
    app.run()
except Exception as e:
    log.critical(f"App crashed: {e}")
    music_manager.save_state()
    data_manager.stop()
    sys.exit(1)

