import json, threading, math, datetime, textwrap, re
from ursina import *
from src.database import get_connection
from src.logger import log
from src.ai_agent import AIAgent
from src.tts_manager import TTSManager

class GridView(Entity):
    def __init__(self):
        super().__init__()
        self.cubes = {}; self.selected_id = None; self.mode = "general"; self.current_filter = "ALL"; self.status_filter = "ALL"
        self.globe_anchor = Entity(parent=self) 
        self.ui_root = Entity(parent=camera.ui, enabled=False)
        self.ui_bg = Entity(parent=self.ui_root, model='quad', scale=(0.9, 0.7), color=color.hex("#001122ee"), z=1)
        self.ui_border = Entity(parent=self.ui_root, model='quad', scale=(0.92, 0.72), color=color.cyan, z=1.1)
        self.ui_title = Text(text="RESOURCE UPLINK", parent=self.ui_root, y=0.3, scale=2, origin=(0,0), color=color.cyan, z=0)
        self.ui_content = Text(text="Initializing...", parent=self.ui_root, position=(-0.4, 0.25), scale=1.0, color=color.white, line_height=1.2, z=0)
        self.ui_footer = Text(text="[X] ANALYZE   [RT/LT] SCROLL   [B] CLOSE", parent=self.ui_root, y=-0.3, scale=1, origin=(0,0), color=color.yellow, z=0)
        self.full_details_text = []; self.scroll_offset = 0; self.max_visible_lines = 15
        self.hover_label = Text(text="", parent=camera.ui, scale=1.5, color=color.cyan, enabled=False); self.hover_target = None
        self.internet_gateway = Entity(parent=self.globe_anchor, model='sphere', scale=2, color=color.azure, position=(0, 15, 0), enabled=False)
        self.packets = []
        self.ai_agent = AIAgent(); self.tts = TTSManager(); self.last_refresh = 0; self.refresh_rate = 2.0 
        self.music_manager = None # Injected by main.py
        self.scan_effect = Entity(model='sphere', scale=0, color=color.cyan, alpha=0.1, enabled=False)
        self.scan_effect_wire = Entity(parent=self.scan_effect, model='sphere', scale=1.01, color=color.cyan, alpha=0.3, mode='wireframe')
        self.deep_dive_log = "" # Persistent storage

    def trigger_scan_visual(self, pos):
        self.scan_effect.position = pos; self.scan_effect.scale = 0; self.scan_effect.enabled = True
        self.scan_effect.animate_scale(10, duration=1.5, curve=curve.out_expo)
        self.scan_effect.fade_out(duration=1.5); invoke(setattr, self.scan_effect, 'enabled', False, delay=1.6)

    def create_ec2_node(self, pos, scale, hc):
        p = Entity(parent=self.globe_anchor, position=pos, scale=scale)
        Entity(parent=p, model='cube', scale=0.6, color=color.hex(hc).tint(-0.2), collider=None)
        ic = Entity(parent=p, model='cube', scale=0.3, color=color.white, alpha=0.8, collider=None); p.inner_core = ic
        Entity(parent=p, model='wireframe_cube', scale=1.0, color=color.hex(hc), collider=None)
        return p

    def create_lambda_node(self, pos, scale, hc):
        p = Entity(parent=self.globe_anchor, position=pos, scale=scale)
        Entity(parent=p, model='sphere', scale=0.6, color=color.hex(hc), collider=None)
        r1 = Entity(parent=p, model='sphere', scale=(1.5, 0.05, 1.5), color=color.hex(hc), alpha=0.5, collider=None); r1.rotation = (45, 45, 0); p.rings = [r1]
        return p

    def create_rds_node(self, pos, scale, hc):
        p = Entity(parent=self.globe_anchor, position=pos, scale=scale)
        for yo, t in [(0.3, 0), (0, -0.2), (-0.3, -0.4)]: Entity(parent=p, model='cube', scale=(1, 0.2, 1), y=yo, color=color.hex(hc).tint(t), collider=None)
        return p

    def create_secret_node(self, pos, scale, hc):
        p = Entity(parent=self.globe_anchor, position=pos, scale=scale); Entity(parent=p, model='diamond', scale=0.8, color=color.hex(hc), collider=None)
        Entity(parent=p, model='wireframe_cube', scale=1.2, color=color.hex(hc).tint(0.2), rotation=(45,45,45), collider=None)
        return p

    def update(self):
        if self.hover_target and self.hover_target.enabled and not self.ui_root.enabled:
            sp = world_position_to_screen_position(self.hover_target.world_position); self.hover_label.position = (sp.x, sp.y + 0.05); self.hover_label.enabled = True
        else: self.hover_label.enabled = False
        
        # HIDE LABELS if Details Panel is OPEN
        show_labels = not self.ui_root.enabled
        
        if time.time() % 0.1 < 0.02: 
            for e in self.cubes.values():
                if hasattr(e, 'label'): 
                    e.label.look_at(camera)
                    e.label.enabled = show_labels
                    e.label.scale = 15 
                if hasattr(e, 'rings'): [setattr(r, 'rotation_y', r.rotation_y + 100 * time.dt) for r in e.rings]
                if hasattr(e, 'inner_core'): e.inner_core.rotation_x += 200 * time.dt; e.inner_core.rotation_z += 100 * time.dt
        if time.time() - self.last_refresh > self.refresh_rate:
            self.refresh_data(); self.last_refresh = time.time()
            # DO NOT auto-update details panel here to prevent overwriting AI results
            # if self.ui_root.enabled and self.selected_id: self.update_details_panel()
            
        if self.mode == "networking": self.internet_gateway.enabled = True; self.update_network_traffic()
        else:
            self.internet_gateway.enabled = False; [destroy(p) for p in self.packets]; self.packets = []

    def set_details_content(self, txt): 
        self.full_details_text = []
        for line in txt.split('\n'):
            self.full_details_text.extend(textwrap.wrap(line, width=50))
        self.scroll_offset = 0; self.refresh_details_view()

    def append_to_details(self, txt):
        if txt.strip() not in "\n".join(self.full_details_text):
            new_lines = []
            for line in txt.split('\n'):
                new_lines.extend(textwrap.wrap(line, width=50))
            self.full_details_text.extend(new_lines)
            self.refresh_details_view()

    def refresh_details_view(self):
        v = self.full_details_text[self.scroll_offset : self.scroll_offset + self.max_visible_lines]; self.ui_content.text = "\n".join(v)
        ind = (" [ ^ MORE ABOVE ]" if self.scroll_offset > 0 else "") + (" [ v MORE BELOW ]" if len(self.full_details_text) > self.scroll_offset + self.max_visible_lines else "")
        self.ui_title.text = f"RESOURCE UPLINK{ind}"

    def scroll_details(self, d):
        no = self.scroll_offset + d
        if 0 <= no <= max(0, len(self.full_details_text) - self.max_visible_lines): self.scroll_offset = no; self.refresh_details_view()

    def cycle_status_filter(self):
        f = ["ALL", "GREEN", "YELLOW", "RED"]; self.status_filter = f[(f.index(self.status_filter) + 1) % 4]
        nm = {"ALL": "All Systems","GREEN": "Operational Only","YELLOW": "Warnings Only","RED": "Critical Alerts Only"}
        self.tts.speak_category(f"Filter: {nm[self.status_filter]}"); self.refresh_data()

    def set_filter(self, rt): self.current_filter = rt; [destroy(c) for c in self.cubes.values()]; self.cubes = {}; self.refresh_data(); self.globe_anchor.rotation = (0,0,0)

    def refresh_data(self):
        try:
            conn = get_connection(); cursor = conn.cursor()
            q = 'SELECT r.id, r.type, r.state, m.cpu_usage, m.security_issues_count, m.network_in_bytes, r.details FROM resources r LEFT JOIN metrics m ON r.id = m.resource_id'
            if self.current_filter != "ALL": q += f" WHERE r.type = '{self.current_filter.lower()}'"
            cursor.execute(q); rows = cursor.fetchall(); conn.close(); current_ids = set(); total = len(rows)
            if total == 0:
                if not hasattr(self, 'empty_msg'): self.empty_msg = Text(text="NO DATA FOUND", scale=2, color=color.red, origin=(0,0), position=(0,0))
                self.empty_msg.enabled = True; self.empty_msg.text = f"NO RESOURCES FOUND IN '{self.current_filter}'"
            else: (hasattr(self, 'empty_msg') and setattr(self.empty_msg, 'enabled', False))
            phi = math.pi * (3. - math.sqrt(5.))
            for i, row in enumerate(rows):
                rid, rtype, state, cpu, sec, net_in, dblo = row; current_ids.add(rid); ltxt = rid[-8:]
                if dblo:
                    try:
                        d = json.loads(dblo)
                        if 'tags' in d and isinstance(d['tags'], dict) and 'Name' in d['tags']: ltxt = d['tags']['Name']
                        elif 'name' in d: ltxt = d['name']
                        if len(ltxt) > 15: ltxt = ltxt[:12] + "..."
                    except: pass
                y = 1 - (i / float(total - 1 + 1e-9)) * 2; rad = math.sqrt(1 - y * y); th = phi * i 
                pos = Vec3(math.cos(th) * rad * 12, y * 12, math.sin(th) * rad * 12); bs = 0.4; ts = Vec3(bs, bs, bs); vis = True; scat = "GREEN"
                
                # COLOR LOGIC
                if self.mode == "general":
                    if state in ['running', 'Active', 'available']: tcol = color.hex("#00ff99").tint(-0.2); scat = "GREEN"
                    else: tcol = color.hex("#ffaa00"); scat = "YELLOW"
                elif self.mode == "security":
                    # Priority Check for Security Mode Only
                    if sec and sec > 0: scat = "RED"
                    
                    if rtype == 'ecr' and dblo:
                        try:
                            d = json.loads(dblo)
                            if not d.get('scan_on_push', False): scat = "RED"
                        except: pass
                    
                    if scat == "RED": tcol = color.hex("#ff0033"); ts = Vec3(bs * 1.5, bs * 1.5, bs * 1.5)
                    else: tcol = color.azure; scat = "GREEN"
                elif self.mode == "usage":
                    scat = "GREEN"; s = bs
                    if rtype == 'lambda': s = bs * (1 + (cpu / 100.0))
                    elif rtype == 'ecr':
                        is_active = net_in > 0; s = bs * 1.5 if is_active else bs; ts = Vec3(s,s,s); tcol = color.cyan if is_active else color.gray
                    else:
                        s = bs * (1 + (cpu / 30.0))
                        if cpu > 80: scat = "RED"
                        elif cpu > 50: scat = "YELLOW"
                    if rtype != 'ecr': ts = Vec3(bs, s, bs); tcol = color.hsv(240 - (cpu * 2.4), 1, 1)
                elif self.mode == "networking":
                    scat = "GREEN"; s = bs * (1 + (net_in / 1000.0)); (scat := "RED") if net_in > 1000000 else (scat := "YELLOW") if net_in > 1000 else (scat := "GREEN")
                    ts = Vec3(s, s, s); tcol = color.cyan
                
                if self.status_filter != "ALL" and self.status_filter != scat: vis = False; ts = Vec3(0,0,0)
                lbd = f"[ {ltxt.upper()} ]"
                if rid not in self.cubes:
                    hc = "#aaaaaa"; (hc := "#ff0033") if scat == "RED" else (hc := "#ffaa00") if scat == "YELLOW" else (hc := "#00ff99")
                    if self.mode == 'networking': hc = "#00ffff"
                    e = self.create_lambda_node(pos, ts, hc) if rtype == 'lambda' else self.create_rds_node(pos, ts, hc) if rtype == 'rds' else self.create_secret_node(pos, ts, hc) if rtype == 'secret' else self.create_ec2_node(pos, ts, hc)
                    e.resource_id = rid; e.look_at(Vec3(0,0,0)); self.cubes[rid] = e
                    t = Text(text=lbd, parent=e, y=4.5, scale=25, color=color.cyan, enabled=vis, billboard=True, background=True); t.background.color = color.black66; e.label = t 
                    Entity(parent=e, model='line', scale_y=4.5, y=2.25, color=color.cyan, alpha=0.4)
                else:
                    e = self.cubes[rid]; e.animate_scale(ts, duration=0.5)
                    # Update Colors if changed
                    if scat == "RED": tcol = color.hex("#ff0033")
                    elif scat == "YELLOW": tcol = color.hex("#ffaa00")
                    for c in e.children:
                        if isinstance(c, Entity) and not isinstance(c, Text) and c.model and c.model.name != 'line':
                            c.color = tcol

                    if hasattr(e, 'label'):
                        e.label.enabled = vis
                        if e.label.text != lbd: e.label.text = lbd
                    e.collider = None if not vis else 'box'
            [destroy(self.cubes[r]) or self.cubes.pop(r) for r in list(self.cubes.keys()) if r not in current_ids]
        except Exception as ex: log.error(f"Error refreshing grid: {ex}")

    def update_network_traffic(self):
        try:
            conn = get_connection(); c = conn.cursor(); rt = time.time() - 600 
            c.execute("SELECT src_addr, dst_addr, bytes FROM vpc_flow_logs WHERE timestamp > ? AND action='ACCEPT' ORDER BY bytes DESC LIMIT 15", (rt,))
            flows = c.fetchall()
            if not hasattr(self, 'ip_map') or not self.ip_map:
                self.ip_map = {}
                c.execute("SELECT id, details FROM resources WHERE type='ec2'")
                for rid, dblo in c.fetchall():
                    if dblo and rid in self.cubes:
                        try:
                            d = json.loads(dblo)
                            if 'private_ip' in d: self.ip_map[d['private_ip']] = self.cubes[rid]
                            if 'public_ip' in d: self.ip_map[d['public_ip']] = self.cubes[rid]
                        except: pass
            conn.close()
            for s, d, v in flows:
                se = self.ip_map.get(s); te = self.ip_map.get(d)
                sp = se.position if se else self.internet_gateway.position if te else None
                ep = te.position if te else self.internet_gateway.position if se else None
                if sp and ep and random.random() < 0.1:
                    for i in range(3):
                        pk = Entity(parent=self.globe_anchor, model='sphere', scale=0.12, color=color.cyan, position=sp); pk.target = ep; pk.speed = 10; pk.delay = i * 0.1; pk.start_time = time.time() + pk.delay; pk.visible = False; self.packets.append(pk)
        except: pass
        if len(self.packets) < 5 and len(self.cubes) > 0 and random.random() < 0.1:
            si = random.choice(list(self.cubes.keys())); se = self.cubes[si]
            tp = self.internet_gateway.position if random.random() < 0.7 else self.cubes[random.choice(list(self.cubes.keys()))].position
            for i in range(5): 
                pk = Entity(parent=self.globe_anchor, model='sphere', scale=0.1, color=color.hex("#ffff00"), position=se.position); pk.target = tp; pk.speed = random.uniform(8, 12); pk.delay = i * 0.1; pk.start_time = time.time() + pk.delay; pk.visible = False; self.packets.append(pk)
        now = time.time()
        for p in [x for x in self.packets if distance(x.position, x.target) < 0.5 or now > x.start_time + 10]:
            if p in self.packets: destroy(p); self.packets.remove(p)
        for p in [x for x in self.packets if now >= x.start_time]: p.visible = True; p.position = lerp(p.position, p.target, p.speed * time.dt * 0.15)

    def select_resource(self, rid):
        self.selected_id = rid; log.info(f"Selected: {rid}"); self.tts.speak_category("selection")
        self.deep_dive_log = ""
        self.set_details_content(f"ACCESSING {rid}...\n\nESTABLISHING UPLINK..."); self.ui_root.scale = 0.1; self.ui_root.enabled = True; self.ui_root.animate_scale((1,1,1), duration=0.2, curve=curve.out_back); self.update_details_panel()
        if rid in self.cubes: self.trigger_scan_visual(self.cubes[rid].world_position)

    def active_scan_resource(self, rid):
        try:
            from src.aws_client import AWSClient; aws = AWSClient(region="us-gov-west-1", mock_mode=False)
            conn = get_connection(); c = conn.cursor(); c.execute("SELECT type FROM resources WHERE id=?", (rid,)); res = c.fetchone()
            
            if res and res[0] == 'ecr':
                fnd = aws.get_ecr_findings(rid); text = f"\n[ LIVE SECURITY SCAN ]\n"
                cr = fnd.get('CRITICAL', 0); hi = fnd.get('HIGH', 0); md = fnd.get('MEDIUM', 0)
                
                if 'error' in fnd: text += f"Scan Error: {fnd['error']}"
                elif 'status' in fnd: text += f"Status: {fnd['status']}"
                else: 
                    text += f"CRITICAL: {cr}\nHIGH:     {hi}\nMEDIUM:   {md}\n"
                    # Force update metrics if issues found
                    total_vuln = cr + hi
                    if total_vuln > 0:
                        c.execute("UPDATE metrics SET security_issues_count = ? WHERE resource_id = ?", (total_vuln, rid))
                        conn.commit()
                        self.last_refresh = 0 # Force immediate UI update
                
                self.deep_dive_log += text + "\n"
                self.append_to_details(text)
            
            conn.close()
        except Exception as e: log.error(f"Active Scan Error: {e}")

    def update_details_panel(self):
        try:
            cn = get_connection(); c = cn.cursor(); c.execute("SELECT r.details, r.type, r.state, r.region, m.security_issues_count, r.name FROM resources r LEFT JOIN metrics m ON r.id = m.resource_id WHERE r.id=?", (self.selected_id,))
            rs = c.fetchone(); c.execute("SELECT username, event_name, event_time FROM cloudtrail_logs WHERE resource_id LIKE ? OR raw_data LIKE ? ORDER BY event_time DESC LIMIT 3", (f"%{self.selected_id}%", f"%{self.selected_id}%"))
            als = c.fetchall(); cn.close()
            if rs:
                dblo, rt, st, reg, sec, nm = rs; f = "[X] ANALYZE   [RT/LT] SCROLL   [B] CLOSE"; (f := "[Y] DECRYPT   " + f) if rt == 'secret' else None; self.ui_footer.text = f
                h = f"RESOURCE: {nm} ({self.selected_id})" if nm != self.selected_id else f"RESOURCE: {self.selected_id}"
                
                # --- CONTENT FILTERING ---
                dt = ""
                if self.mode == "security":
                    # Security Mode: Show Audit Log + Findings ONLY
                    dt = f"{h} [SECURITY VIEW]\n" + "-" * 30 + "\n"
                    dt += "<color=red>[ SECURITY AUDIT LOG ]</color>\n" + (f"RISK LEVEL: HIGH ({sec} Issues)\n" if sec and sec > 0 else "STATUS: SECURE\n")
                    if dblo:
                        try:
                            d = json.loads(dblo)
                            if 'security_groups' in d: dt += f"SECURITY GROUPS: {d['security_groups']}\n"
                        except: pass
                else:
                    # General Mode: Show Everything
                    dt = f"{h}\n" + "-" * 30 + "\n"
                    if sec and sec > 0: dt += f"RISK LEVEL: HIGH ({sec} Issues)\n" + "-" * 30 + "\n"
                    
                    if als:
                        dt += "<color=magenta>[ RECENT ACTIVITY ]</color>\n"
                        for u, e, t in als: ts = datetime.datetime.fromtimestamp(t).strftime('%Y-%m-%d %H:%M'); dt += f"{('*' if '@' in u else ' ')} {ts} | {u}\n    -> {e}\n"
                        dt += "-" * 30 + "\n"
                    dt += f"TYPE: {rt.upper()}\nSTATE: {st.upper()}\n"
                    if rt == 'ec2': dt += "NETWORK FLOW: ENABLED (S3/Firehose)\n"
                    if dblo:
                        try:
                            d = json.loads(dblo); sk = ['id', 'type', 'state', 'region', 'details', 'name', 'security_groups']
                            for k, v in d.items():
                                if k in sk: continue
                                ks = k.replace('_', ' ').upper(); vs = f"{v}" if isinstance(v, list) else "{{...}}" if isinstance(v, dict) else str(v)
                                if len(vs) > 55: vs = vs[:55] + "\n    " + vs[55:]
                                if k == 'tags' and isinstance(v, dict):
                                    dt += f"{ks}:\n"
                                    for tk, tv in v.items(): dt += f"  > {tk}: {tv}\n"
                                else: dt += f"{ks}: {vs}\n"
                            if rt == 'secret': dt += f"LAST ACCESSED: {d.get('last_accessed', 'Never')}\n"
                        except Exception as pe: dt += f"\n[Metadata Parse Error: {pe}]\n"
                    else: dt += "\n[Fetching Deep Metadata...]\n(Check UPLINK status)"
            else: dt = "Object not found in Cache.\nWaiting for Sync..."
            if self.deep_dive_log: dt += "\n" + "-"*30 + "\n" + self.deep_dive_log
            self.set_details_content(dt)
        except Exception as ex: log.error(f"Panel Update Error: {ex}")

    def trigger_decrypt(self):
        cn = get_connection(); c = cn.cursor(); c.execute("SELECT type FROM resources WHERE id=?", (self.selected_id,)); rs = c.fetchone(); cn.close()
        if rs and rs[0] == 'secret': self.set_details_content(self.ui_content.text + "\n\n[SYSTEM] DECRYPTING SECURE PAYLOAD...\n"); self.tts.speak_async("Decrypting secure payload."); t = threading.Thread(target=self._perform_decrypt, args=(self.selected_id,)); t.daemon = True; t.start()
        else: self.tts.speak_async("Target is not a secure container.")

    def _perform_decrypt(self, rid):
        try:
            from src.aws_client import AWSClient; aws = AWSClient(region="us-gov-west-1", mock_mode=False); sv = aws.get_secret_value(rid)
            self.append_to_details(f"\n<color=lime>[ DECRYPTED PAYLOAD ]</color>\n{sv}\n" + "-"*30); self.tts.speak_async("Decryption complete. Value displayed.")
        except Exception as e: self.append_to_details(f"\n[DECRYPTION FAILED]: {e}")

    def trigger_ai_analysis(self, rid):
        self.set_details_content("\n".join(self.full_details_text) + "\n\n[SYSTEM] INITIATING DEEP DIVE...")
        
        # Audio Cue for Start
        self.tts.speak_category("scan_start") 
        
        t = threading.Thread(target=self._perform_deep_dive, args=(rid,)); t.daemon = True; t.start()

    def _perform_deep_dive(self, rid):
        try:
            conn = get_connection(); c = conn.cursor(); c.execute("SELECT type FROM resources WHERE id=?", (rid,)); res = c.fetchone(); conn.close()
            if not res: return
            rtype = res[0]
            self.tts.speak_category("scan_start"); from src.aws_client import AWSClient; aws = AWSClient(region="us-gov-west-1", mock_mode=False)
            
            # STRONGER PROMPT FOR REMEDIATION INSTRUCTIONS
            context = f"RESOURCE: {rid}\nTYPE: {rtype.upper()}\n"
            context += "ROLE: You are a Senior Security Consultant advising a human engineer.\n"
            context += "TASK: Do not remediate automatically. Instead, provide clear, step-by-step INSTRUCTIONS on how a person should manually resolve these specific CVEs.\n"
            context += "FORMAT REQUIREMENTS:\n"
            context += "AUDIO_SUMMARY: [A very concise verbal briefing (MAX 4 SENTENCES) telling the engineer what the high-level fix involves.]\n"
            context += "DETAILS: [A detailed, numbered guide for the engineer to follow, explaining the 'Why' and 'How' for each step]\n\n"

            if rtype == 'ec2':
                self.tts.speak_category("data_fetch"); ssm = aws.fetch_ssm_history(rid); self.append_to_details(f"> SSM Records: {len(ssm)} found.")
                logs = aws.fetch_instance_logs(rid); self.append_to_details(f"> System Logs: {len(logs)} lines retrieved.")
                context += f"SSM COMMANDS:\n{str(ssm)}\n\nLOGS:\n{str(logs)}\n\n"
            elif rtype == 'ecr':
                self.tts.speak_category("data_fetch"); fnd = aws.get_ecr_findings(rid); self.append_to_details(f"> Image Scan: {fnd.get('status', 'Complete')}")
                
                # Build list of CVEs
                cves = ""
                count = 0
                if 'top_findings' in fnd:
                    for f in fnd['top_findings']: 
                        cves += f"VULNERABILITY: {f['name']} ({f['severity']})\nDESCRIPTION: {f['description']}\n---\n"
                        count += 1
                
                if count == 0:
                    self.append_to_details("[SYSTEM] No Critical/High CVEs found. Deep analysis may be limited.")
                else:
                    log.info(f"Deep Dive Context: Found {count} CVEs for {rid}")
                    # SHOW RAW FINDINGS IMMEDIATELY
                    self.append_to_details(f"\n[ RAW FINDINGS ]\n{cves}")

                context += f"ECR SCAN FINDINGS:\n{cves}\n\n"
                
            conn = get_connection(); c = conn.cursor(); c.execute("SELECT username, event_name, event_time FROM cloudtrail_logs WHERE resource_id LIKE ? OR raw_data LIKE ? ORDER BY event_time DESC LIMIT 10", (f"%{rid}%", f"%{rid}%")); trs = c.fetchall(); conn.close()
            self.append_to_details(f"> CloudTrail Events: {len(trs)} found."); self.append_to_details("[TRANSMITTING TO NEURAL CORE...]"); 
            
            # Note: We skipped the "ai_transmission" speech here to avoid overlap with "scan_start" or music ducking
            
            self.ai_agent.analyze_resource_async(context + f"ACTIVITY:\n{str(trs)}", self.ai_callback)
        except Exception as e: log.error(f"Deep Dive Error: {e}"); self.append_to_details(f"Deep Dive Failed: {e}")

    def ai_callback(self, result):
        log.info(f"AI Response Payload:\n{result}")
        
        # --- DEFINITIVE EXTRACTION ---
        audio_text = ""
        display_text = result
        
        # 1. Look for AUDIO_SUMMARY (Case Insensitive)
        pattern = r'["\\]?AUDIO_SUMMARY["\\]?\s*:\s*["\\]([^"]+)["\\]'
        match = re.search(pattern, result, re.IGNORECASE | re.DOTALL)
        if match:
            audio_text = match.group(1).strip()
            log.info(f"Regex Matched Audio: {audio_text[:50]}...")
        
        # 2. Extract DETAILS for display
        det_pattern = r'["\\]?DETAILS["\\]?\s*:\s*(.*)'
        det_match = re.search(det_pattern, result, re.IGNORECASE | re.DOTALL)
        if det_match:
            raw_details = det_match.group(1).strip()
            # Clean up trailing JSON/Markdown garbage
            raw_details = raw_details.rstrip('}` \n')
            
            # Try to format if it's a list
            try:
                # Basic cleanup to try JSON load on the snippet
                if raw_details.startswith('['):
                    steps = json.loads(raw_details)
                    formatted_steps = "<color=orange>REMEDIATION PLAN:</color>\n"
                    for item in steps:
                        step_num = item.get('STEP', '?')
                        instr = item.get('INSTRUCTION', item.get('INSTRUCTIONS', 'N/A'))
                        formatted_steps += f"STEP {step_num}: {instr}\n\n"
                    display_text = formatted_steps
                else:
                    display_text = f"<color=orange>REMEDIATION PLAN:</color>\n{raw_details}"
            except:
                display_text = f"<color=orange>REMEDIATION PLAN:</color>\n{raw_details}"

        # 3. Final Fallback for Audio
        if not audio_text:
            # Strip markdown and take first sentence
            clean = re.sub(r'[`{}\"]', '', result)
            audio_text = clean.split('.')[0]
            
        # Skip Conversational Fillers
        fillers = ["Okay, I understand.", "Okay, I'm ready.", "Certainly!", "I have analyzed"]
        for f in fillers:
            if audio_text.startswith(f): audio_text = audio_text.replace(f, "").strip()
        
        # Update UI
        formatted_ai_text = f"\n\n[AI ANALYSIS SUMMARY]\n{display_text}"
        self.deep_dive_log += formatted_ai_text
        self.append_to_details(formatted_ai_text)
        self.ui_footer.text = "[X] ANALYZE   [RT/LT] SCROLL   [B] CLOSE"
        
        # Play Audio with priority
        if audio_text:
            log.info(f"TTS Queueing ({len(audio_text)} chars): '{audio_text}'")
            if hasattr(self, 'music_manager') and self.music_manager: self.music_manager.set_volume(0.2)
            self.tts.speak_async(audio_text, priority=True)
            if hasattr(self, 'music_manager') and self.music_manager: invoke(self.music_manager.set_volume, 0.5, delay=15.0)


    def close_details(self): self.ui_root.enabled = False
    def cycle_mode(self):
        modes = ["general", "security", "networking", "usage"]
        old_mode = self.mode
        self.mode = modes[(modes.index(self.mode) + 1) % 4]
        log.info(f"GRID_VIEW: Mode changed from {old_mode} to {self.mode}")
        self.tts.speak_category("mode_change")
        self.refresh_data()
