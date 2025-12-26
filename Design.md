# AWS ROG Explorer - Architecture & Design

## 1. Core Concept
A handheld, futuristic 3D interface for exploring AWS resources (specifically `us-gov-west-1`) on the ASUS ROG Ally. The application uses a game engine to render resources as 3D objects in a grid, offering different "X-ray" visualization modes (General, Security, Networking, Usage).

## 2. Tech Stack
*   **Language:** Python 3.10+
*   **UI/3D Engine:** [Ursina Engine](https://www.ursinaengine.org/) (Python-powered, easy to prototype, supports controller input).
*   **AWS SDK:** `boto3` (running in background threads/processes to prevent UI freeze).
*   **AI/LLM:** Google Gemini (via `google-generativeai`) for instance summarization.
*   **Database:** SQLite (`cloud_cache.db`) for caching resource state and decoupling rendering from fetching.
*   **Voice/Audio:** `pyttsx3` for offline text-to-speech feedback ("System Analyzing...").

## 3. Architecture

### A. The Data Layer (Backend Service)
*   **Async/Threaded Worker:** A standalone background service (`DataManager`) that continuously polls AWS.
*   **Caching Strategy:**
    *   Resources (EC2, Lambda) are stored in SQLite.
    *   Tables: `resources`, `metrics`, `scans`, `logs`.
    *   The UI *only* reads from SQLite; it never calls AWS directly to ensure high FPS.
*   **Modes Logic (The "X-Ray"):**
    *   **General:** Standard health checks (Status Check Failed).
    *   **Security:** Aggregates Inspector2 findings & Security Hub.
    *   **Networking:** Aggregates CloudWatch metrics (NetworkIn/Out) & VPC Flow Logs (if enabled/accessible).
    *   **Usage:** CPU/Memory utilization metrics.

### B. The Visual Layer (Frontend)
*   **View:** A 3D Grid view.
*   **Objects:**
    *   EC2 Instances = Cubes.
    *   Lambda Functions = Spheres or Pyramids.
*   **Visual Encoding:**
    *   *Size:* Based on metric intensity (e.g., in Networking mode, high traffic = larger cube).
    *   *Color:* Flat futuristic palette (Neon Green, Alert Red, Warning Yellow, Muted Gray).
*   **HUD:** 2D overlay for mode indicators, logs, and popup details.

### C. Input Mapping (ROG Ally / XInput)
*   **Left Stick:** Camera Pan/Tilt.
*   **D-Pad:** Grid Navigation (Snap to nearest object).
*   **Bumpers (LB/RB):** Cycle Modes (General -> Security -> Networking -> Usage).
*   **Triggers (LT/RT):** Scroll content in Popups.
*   **Button A:** Select/Details Popup.
*   **Button X:** Trigger Gemini Analysis.
*   **Button B:** Back/Close.

## 4. Specific Workflows
1.  **Startup:** Application launches, starts Background Worker. Voice says "Initializing Cloud Link".
2.  **Navigation:** User pans over grid. Targeting reticle highlights nearest box.
3.  **Selection:** User presses 'A'. Camera zooms slightly. A 2D semi-transparent glass panel pops up with details from SQLite.
4.  **AI Analysis:** User presses 'X' on a selected instance.
    *   System voice: "Accessing Neural Link..."
    *   App reads `gemini_token.txt`.
    *   Sends instance metadata + recent logs to Gemini.
    *   Returns summary to UI.

## 5. Security & Configuration
*   **Credentials:** Uses standard AWS CLI credentials (profile or env vars).
*   **Region:** Hardcoded default `us-gov-west-1`, configurable.
*   **Logging:** All actions logged to `logs/app.log`.
