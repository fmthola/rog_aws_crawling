# Development Plan

## Phase 1: Setup & Core Infrastructure
- [ ] **Environment Setup:** Create `requirements.txt` (Ursina, Boto3, etc.) and install.
- [ ] **Database Setup:** Create `src/database.py` to initialize SQLite schema (Resources, Metrics tables).
- [ ] **Logging:** Setup centralized logging in `src/logger.py`.

## Phase 2: Data Ingestion (The Backend)
- [ ] **AWS Connector:** Create `src/aws_client.py` using `boto3`.
    - [ ] Implement EC2 listing.
    - [ ] Implement Mock mode (for development without gov-cloud access).
- [ ] **Background Worker:** Create `src/data_manager.py`.
    - [ ] Threaded loop to fetch EC2 data and update SQLite.
    - [ ] Implement "Mode" processors (calculate colors/sizes based on mock data first).

## Phase 3: The 3D Engine (Ursina)
- [ ] **Window Setup:** Create `main.py` with Ursina setup (fullscreen, futuristic font).
- [ ] **Grid Renderer:** Create `src/ui/grid_view.py` to instantiate Cubes based on SQLite data.
- [ ] **Update Loop:** mechanism to poll SQLite every 1-2 seconds and update Cube properties (color/size) without destroying/recreating them.

## Phase 4: Controls & Interaction
- [ ] **Input Handler:** Map ROG Ally buttons in `src/input_handler.py`.
- [ ] **Camera Control:** Joystick movement logic.
- [ ] **Mode Switching:** Implement Logic to change visual properties when RB/LB are pressed.
- [ ] **Selection System:** "Raycast" or Grid-snap logic to highlight the focused object.

## Phase 5: Advanced Features
- [ ] **UI Overlays:** Create the "Popup" details panel.
- [ ] **Gemini Integration:** Implement `src/ai_agent.py` to hit Gemini API with instance details.
- [ ] **Audio/TTS:** Add voice feedback for state changes.

## Phase 6: Polish & Verify
- [ ] **Network/Security Logic:** Refine the logic for calculating "size" based on flow logs/metrics.
- [ ] **Optimization:** Ensure 60 FPS on the Ally.
- [ ] **Packaging:** Instructions for running.
