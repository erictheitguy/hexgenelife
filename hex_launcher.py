import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import sqlite3
import os
import json
import random
import signal
import sys

# Paths
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(ROOT_DIR, "server", "game_state.db")

# Add project root to path for imports
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from server.db_init import DatabaseInitializer
from server.mob_manager import MobManager

class HexLauncher:
    def __init__(self, root):
        self.root = root
        self.root.title("HexGenLife Launcher")
        self.root.geometry("600x700")
        
        # Process tracking { "server": Popen, "viewer": [Popen], "clients": { mob_id: Popen } }
        self.server_proc = None
        self.viewer_procs = []
        self.client_procs = {}
        
        self.setup_ui()
        self.update_loop()
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_exit)

    def setup_ui(self):
        style = ttk.Style()
        style.configure("Header.TLabel", font=("Helvetica", 12, "bold"))
        
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- Server Section ---
        server_frame = ttk.LabelFrame(main_frame, text=" Server Control ", padding=10)
        server_frame.pack(fill=tk.X, pady=5)
        
        self.server_status_var = tk.StringVar(value="Status: Stopped")
        self.server_status_label = ttk.Label(server_frame, textvariable=self.server_status_var)
        self.server_status_label.pack(side=tk.LEFT, padx=5)
        
        self.btn_start_server = ttk.Button(server_frame, text="Start Server", command=self.start_server)
        self.btn_start_server.pack(side=tk.LEFT, padx=5)
        
        self.btn_stop_server = ttk.Button(server_frame, text="Stop Server", command=self.stop_server, state=tk.DISABLED)
        self.btn_stop_server.pack(side=tk.LEFT, padx=5)

        # --- Viewer Section ---
        viewer_frame = ttk.LabelFrame(main_frame, text=" Viewer ", padding=10)
        viewer_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(viewer_frame, text="Launch New Viewer Instance", command=self.launch_viewer).pack(fill=tk.X)

        # --- Client / Mob Creation Section ---
        client_frame = ttk.LabelFrame(main_frame, text=" Clients & Mob Management ", padding=10)
        client_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Tabs for Existing / Create New
        self.tabs = ttk.Notebook(client_frame)
        self.tabs.pack(fill=tk.BOTH, expand=True)
        
        # Tab 1: Existing Mobs
        self.tab_existing = ttk.Frame(self.tabs, padding=10)
        self.tabs.add(self.tab_existing, text="Existing Mobs")
        
        self.mob_listbox = tk.Listbox(self.tab_existing, height=6, selectmode=tk.MULTIPLE)
        self.mob_listbox.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        
        scrollbar = ttk.Scrollbar(self.tab_existing, orient=tk.VERTICAL, command=self.mob_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.mob_listbox.config(yscrollcommand=scrollbar.set)
        
        btn_box = ttk.Frame(self.tab_existing)
        btn_box.pack(fill=tk.X, pady=5)
        ttk.Button(btn_box, text="Refresh List", command=self.refresh_mobs).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_box, text="Launch Client for Selected", command=self.launch_existing_client).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_box, text="Stop All Clients", command=self.stop_all_clients).pack(side=tk.RIGHT, padx=2)

        # Tab 2: Create New Mob
        self.tab_create = ttk.Frame(self.tabs, padding=10)
        self.tabs.add(self.tab_create, text="Create New Mob")
        
        self.setup_create_mob_ui(self.tab_create)

    def setup_create_mob_ui(self, parent):
        fields = [
            ("Mob ID", f"mob_{random.randint(100, 999)}"),
            ("Type", "prey"),
        ]
        
        self.create_entries = {}
        for i, (label, default) in enumerate(fields):
            ttk.Label(parent, text=label).grid(row=i, column=0, sticky=tk.W, pady=2)
            entry = ttk.Entry(parent)
            entry.insert(0, default)
            entry.grid(row=i, column=1, sticky=tk.EW, pady=2)
            self.create_entries[label] = entry
            
        parent.columnconfigure(1, weight=1)
        
        btn_frame = ttk.Frame(parent)
        btn_frame.grid(row=len(fields), column=0, columnspan=2, pady=10)
        
        ttk.Button(btn_frame, text="Randomize", command=self.randomize_create_fields).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Save & Launch Client", command=self.create_and_launch).pack(side=tk.LEFT, padx=5)

    def randomize_create_fields(self):
        self.create_entries["Mob ID"].delete(0, tk.END)
        self.create_entries["Mob ID"].insert(0, f"mob_{random.randint(100, 999)}")
        
        mtype = random.choice(["prey", "predator"])
        self.create_entries["Type"].delete(0, tk.END)
        self.create_entries["Type"].insert(0, mtype)

    # --- Actions ---

    def start_server(self):
        if self.server_proc and self.server_proc.poll() is None:
            messagebox.showwarning("Warning", "Server is already running.")
            return
        
        try:
            env = os.environ.copy()
            env["PYTHONPATH"] = ROOT_DIR
            # Run server as a module to handle relative imports correctly
            self.server_proc = subprocess.Popen([sys.executable, "-m", "server.server"], env=env, cwd=ROOT_DIR)
            self.server_status_var.set("Status: Running")
            self.btn_start_server.config(state=tk.DISABLED)
            self.btn_stop_server.config(state=tk.NORMAL)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start server: {e}")

    def stop_server(self):
        if self.server_proc:
            self.server_proc.terminate()
            self.server_proc = None
            self.server_status_var.set("Status: Stopped")
            self.btn_start_server.config(state=tk.NORMAL)
            self.btn_stop_server.config(state=tk.DISABLED)

    def launch_viewer(self):
        try:
            env = os.environ.copy()
            env["PYTHONPATH"] = ROOT_DIR
            # Run as module to respect package structure
            proc = subprocess.Popen([sys.executable, "-m", "viewer.viewer_main"], env=env, cwd=ROOT_DIR)
            self.viewer_procs.append(proc)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to launch viewer: {e}")

    def refresh_mobs(self):
        self.mob_listbox.delete(0, tk.END)
        if not os.path.exists(DB_PATH):
            return
            
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            # Ensure the table and columns exist before querying
            DatabaseInitializer.initialize_db(conn)
            
            cursor.execute("SELECT mob_id, is_active FROM mobs")
            for row in cursor.fetchall():
                mid = row["mob_id"]
                is_active = row["is_active"]
                status = ""
                if mid in self.client_procs:
                    status += " (Managed)"
                if is_active:
                    status += " (Active)"
                self.mob_listbox.insert(tk.END, f"{mid}{status}")
            conn.close()
        except Exception as e:
            print(f"Error querying DB: {e}")

    def launch_existing_client(self):
        selection = self.mob_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select one or more mob IDs.")
            return
        
        selected_mobs = []
        already_running = []
        
        for idx in selection:
            mob_id_raw = self.mob_listbox.get(idx)
            mob_id = mob_id_raw.split(" (")[0]
            
            if mob_id in self.client_procs:
                already_running.append(mob_id)
            else:
                selected_mobs.append(mob_id)
        
        if already_running:
            messagebox.showwarning("Warning", f"Clients for {', '.join(already_running)} are already running and will be skipped.")
            
        if not selected_mobs:
            return
            
        # websocket_client.py main() handles multiple client_ids as sys.argv[1:]
        client_ids = [mid.replace("mob_", "") for mid in selected_mobs]
        
        self.launch_client_group(client_ids, selected_mobs)

    def launch_client_group(self, client_ids, mob_ids):
        try:
            env = os.environ.copy()
            env["PYTHONPATH"] = ROOT_DIR
            # Run client as module. websocket_client.py main() handles multiple client_ids as sys.argv[1:]
            proc = subprocess.Popen([sys.executable, "-m", "client.websocket_client"] + client_ids, env=env, cwd=ROOT_DIR)
            
            # Track this process for all mob_ids it handles
            for mid in mob_ids:
                self.client_procs[mid] = proc
                
            self.refresh_mobs()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to launch client group: {e}")

    def launch_client(self, client_id, mob_id):
        # Kept for backward compatibility/single uses like create_and_launch
        self.launch_client_group([client_id], [mob_id])

    def create_and_launch(self):
        mob_id = self.create_entries["Mob ID"].get()
        if not mob_id:
            messagebox.showerror("Error", "Mob ID is required.")
            return
            
        client_id = mob_id.replace("mob_", "")
        mob_type = self.create_entries["Type"].get().lower()

        try:
            conn = sqlite3.connect(DB_PATH)
            # Ensure DB is initialized (tables exist)
            DatabaseInitializer.initialize_db(conn)
            
            manager = MobManager(conn)
            if manager.mob_exists(mob_id):
                messagebox.showerror("Error", f"Mob {mob_id} already exists.")
                conn.close()
                return
            
            # Use MobManager to create entries in all tables:
            # mobs, mob_genes, mob_health, mob_brain, mob_physical, and species/family_tree
            manager.ensure_client_mob(client_id, mob_type=mob_type)
            conn.close()
            
            # Launch the client
            self.launch_client(client_id, mob_id)
            messagebox.showinfo("Success", f"Mob {mob_id} created and client launched.")
            self.tabs.select(0) # Switch to list
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create mob: {e}")

    def stop_all_clients(self):
        for mob_id, proc in list(self.client_procs.items()):
            proc.terminate()
        self.client_procs = {}
        self.refresh_mobs()

    def update_loop(self):
        # Refresh statuses
        if self.server_proc and self.server_proc.poll() is not None:
            self.server_proc = None
            self.server_status_var.set("Status: Stopped (Crashed/Ended)")
            self.btn_start_server.config(state=tk.NORMAL)
            self.btn_stop_server.config(state=tk.DISABLED)
            
        # Cleanup dead client/viewer procs
        self.viewer_procs = [p for p in self.viewer_procs if p.poll() is None]
        
        dead_clients = [mid for mid, p in self.client_procs.items() if p.poll() is not None]
        if dead_clients:
            for mid in dead_clients:
                del self.client_procs[mid]
            self.refresh_mobs()
            
        self.root.after(1000, self.update_loop)

    def on_exit(self):
        self.stop_server()
        self.stop_all_clients()
        for p in self.viewer_procs:
            p.terminate()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = HexLauncher(root)
    root.mainloop()
