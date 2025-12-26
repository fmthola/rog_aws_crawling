from ursina import *
from src.logger import log

class PlayerController(Entity):
    def __init__(self, grid_view, **kwargs):
        super().__init__(**kwargs)
        self.grid_view = grid_view
        
        # Settings
        self.rotation_speed = 50 
        self.joystick_sensitivity = 10 
        
        # State
        self.state = "MENU" # MENU, EXPLORE, DETAILS
        self.menu_options = ["ALL", "EC2", "RDS", "LAMBDA", "ECR", "ECS", "EKS", "SECRET"]
        self.menu_index = 0
        self.last_mode_cycle = 0
        
        # UI Elements for Menu
        self.menu_bg = Entity(parent=camera.ui, model='quad', scale=(0.8, 0.6), color=color.black90, enabled=True)
        self.menu_title = Text(text="SELECT MODULE", parent=self.menu_bg, y=0.35, scale=2.5, origin=(0,0), color=color.cyan)
        self.menu_items = []
        self._refresh_menu_ui()
        
        camera.position = (0, 0, -35)
        camera.rotation = (0, 0, 0)
        
        self.reticle = Entity(parent=camera.ui, model='quad', scale=0.015, color=color.green)
        self.hovered_entity = None
        
    def _refresh_menu_ui(self):
        for item in self.menu_items: destroy(item)
        self.menu_items = []
        for i, opt in enumerate(self.menu_options):
            c = color.green if i == self.menu_index else color.gray
            t = Text(text=opt, parent=camera.ui, position=(0, 0.2 - (i*0.08)), scale=1.5, origin=(0,0), color=c, enabled=self.menu_bg.enabled)
            self.menu_items.append(t)

    def update(self):
        # Update menu visibility
        for item in self.menu_items: item.enabled = self.state == "MENU"
            
        hit_info = raycast(camera.world_position, camera.forward, distance=100)
        if hit_info.hit and hasattr(hit_info.entity, 'resource_id'):
            self.grid_view.hover_target = hit_info.entity
            model_name = "NODE"
            if hasattr(hit_info.entity, 'model') and hit_info.entity.model: model_name = hit_info.entity.model.name.upper()
            self.grid_view.hover_label.text = f"{hit_info.entity.resource_id}\n< {model_name} >"
            if self.hovered_entity != hit_info.entity:
                if self.hovered_entity and hasattr(self.hovered_entity, 'label'):
                    self.hovered_entity.label.color = color.white; self.hovered_entity.label.scale = 15
                self.hovered_entity = hit_info.entity
                self.reticle.color = color.red; self.reticle.scale = 0.025
                if hasattr(self.hovered_entity, 'label'):
                    self.hovered_entity.label.color = color.cyan; self.hovered_entity.label.scale = 25
        else:
            if self.hovered_entity:
                if hasattr(self.hovered_entity, 'label'): self.hovered_entity.label.color = color.white; self.hovered_entity.label.scale = 15
                self.hovered_entity = None
            self.grid_view.hover_target = None
            self.reticle.color = color.green; self.reticle.scale = 0.015

        if self.state == "MENU": self.update_menu()
        elif self.state == "EXPLORE": self.update_explore()
            
        if self.state == "DETAILS" and not self.grid_view.ui_root.enabled: self.state = "EXPLORE"

    def update_menu(self):
        up = held_keys['gamepad dpad up'] or held_keys['w'] or held_keys['up arrow']
        down = held_keys['gamepad dpad down'] or held_keys['s'] or held_keys['down arrow']
        y_axis = held_keys.get('gamepad left stick y', 0)
        if y_axis > 0.5: up = True
        elif y_axis < -0.5: down = True
        if not hasattr(self, 'last_input'): self.last_input = 0
        if time.time() - self.last_input > 0.2:
            if up:
                self.menu_index = (self.menu_index - 1) % len(self.menu_options); self._refresh_menu_ui(); self.last_input = time.time()
            if down:
                self.menu_index = (self.menu_index + 1) % len(self.menu_options); self._refresh_menu_ui(); self.last_input = time.time()

    def update_explore(self):
        rot_x = held_keys.get('gamepad left stick y', 0) * self.rotation_speed * time.dt
        rot_y = held_keys.get('gamepad left stick x', 0) * self.rotation_speed * time.dt
        if held_keys['w']: rot_x += self.rotation_speed * time.dt
        if held_keys['s']: rot_x -= self.rotation_speed * time.dt
        if held_keys['a']: rot_y -= self.rotation_speed * time.dt
        if held_keys['d']: rot_y += self.rotation_speed * time.dt
        self.grid_view.globe_anchor.rotation_x += rot_x
        self.grid_view.globe_anchor.rotation_y -= rot_y

        # Analog Triggers (Scrolling)
        if self.grid_view.ui_root.enabled:
            lt = held_keys.get('gamepad left trigger', 0)
            if lt > 0.1: self.grid_view.scroll_details(-1)
            rt = held_keys.get('gamepad right trigger', 0)
            if rt > 0.1: self.grid_view.scroll_details(1)
        else:
            rsy = held_keys.get('gamepad right stick y', 0)
            if abs(rsy) > 0.1:
                if not hasattr(self, 'target_fov'): self.target_fov = camera.fov
                self.target_fov -= rsy * 50 * time.dt; self.target_fov = clamp(self.target_fov, 20, 100); camera.fov = lerp(camera.fov, self.target_fov, 4 * time.dt)

    def input(self, key):
        if ' up' in key: return
        ui_open = self.grid_view.ui_root.enabled
        
        # LOG ALL INPUTS for diagnosis
        if 'gamepad' in key or 'shoulder' in key:
            log.info(f"PLAYER_INPUT: {key} | UI_OPEN: {ui_open} | STATE: {self.state}")

        # 1. MENU STATE
        if self.state == "MENU":
            if key in ['a', 'gamepad a', 'enter']:
                selection = self.menu_options[self.menu_index]
                self.grid_view.set_filter(selection); self.state = "EXPLORE"; self.menu_bg.enabled = False
        
        # 2. DETAILS STATE (UI IS OPEN)
        elif ui_open:
            if self.state != "DETAILS": self.state = "DETAILS" # Sync
            
            if key in ['b', 'gamepad b', 'escape']:
                log.info("Closing Details Panel")
                self.grid_view.close_details(); self.state = "EXPLORE"
            elif key in ['x', 'gamepad x']:
                if self.grid_view.selected_id: self.grid_view.trigger_ai_analysis(self.grid_view.selected_id)
            elif key in ['y', 'gamepad y']:
                self.grid_view.trigger_decrypt()
            elif key == 'gamepad right shoulder':
                log.info("PAGING DOWN (Details focus)")
                self.grid_view.scroll_details(5)
            elif key == 'gamepad left shoulder':
                log.info("PAGING UP (Details focus)")
                self.grid_view.scroll_details(-5)

        # 3. EXPLORE STATE (UI IS CLOSED)
        else:
            if self.state != "EXPLORE": self.state = "EXPLORE" # Sync
            
            if key in ['a', 'gamepad a']:
                if self.hovered_entity:
                    log.info(f"Selecting: {self.hovered_entity.resource_id}")
                    self.grid_view.select_resource(self.hovered_entity.resource_id)
                    self.state = "DETAILS"
            elif key in ['b', 'gamepad b']:
                self.state = "MENU"; self.menu_bg.enabled = True; self.grid_view.globe_anchor.rotation = (0,0,0)
            elif key in ['y', 'gamepad y']:
                self.grid_view.cycle_status_filter()
            elif key in ['gamepad right shoulder', 'gamepad left shoulder']:
                # STRICT DEBOUNCE and UI CHECK
                delta = time.time() - self.last_mode_cycle
                if delta > 1.2: # Even longer debounce
                    log.info(f"MODE CYCLE TRIGGERED (Delta: {delta:.2f}s)")
                    self.grid_view.cycle_mode()
                    self.last_mode_cycle = time.time()
                else:
                    log.info(f"MODE CYCLE IGNORED (Debounce: {delta:.2f}s)")
