import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import os
import threading
import time
import webbrowser
import signal

class HealthProServerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("HealthPro Server Suite - v1.1")
        self.root.geometry("850x650")
        self.root.configure(bg="#0f172a") 
        
        # Base paths derived from XAMPP structure
        # Portable Suite Paths
        self.suite_dir = os.path.dirname(os.path.abspath(__file__))
        self.project_root = os.path.dirname(self.suite_dir)
        
        self.php_bin = os.path.join(self.suite_dir, "php", "php-cgi.exe")
        self.php_exe = os.path.join(self.suite_dir, "php", "php.exe")
        self.mysql_bin = os.path.join(self.suite_dir, "mysql", "bin", "mysqld.exe")
        self.php_ini = os.path.join(self.suite_dir, "php", "php.ini")
        
        self.php_process = None
        self.mysql_process = None
        self.is_running = False

        self.setup_ui()
        self.log("System Initialized. XAMPP binaries detected.")

    def setup_ui(self):
        main_frame = tk.Frame(self.root, bg="#0f172a")
        main_frame.pack(fill="both", expand=True, padx=30, pady=30)

        header = tk.Frame(main_frame, bg="#1e293b", height=100)
        header.pack(fill="x", pady=(0, 20))
        
        title = tk.Label(header, text="HEALTHPRO", font=("Inter", 28, "bold"), fg="#38bdf8", bg="#1e293b")
        title.pack(side="left", padx=20, pady=20)
        
        subtitle = tk.Label(header, text="SERVER SUITE", font=("Inter", 12), fg="#94a3b8", bg="#1e293b")
        subtitle.pack(side="left", pady=(35, 0))

        status_panel = tk.Frame(main_frame, bg="#0f172a")
        status_panel.pack(fill="x", pady=10)

        self.status_indicator = tk.Label(status_panel, text="●", font=("Arial", 20), fg="#ef4444", bg="#0f172a")
        self.status_indicator.pack(side="left")
        
        self.status_text = tk.Label(status_panel, text="SYSTEM OFFLINE", font=("Inter", 12, "bold"), fg="#f8fafc", bg="#0f172a")
        self.status_text.pack(side="left", padx=10)

        btn_frame = tk.Frame(main_frame, bg="#0f172a")
        btn_frame.pack(pady=30)

        self.start_btn = tk.Button(btn_frame, text="START SERVICES", font=("Inter", 14, "bold"), 
                                  bg="#10b981", fg="white", width=20, height=2, bd=0, 
                                  activebackground="#059669", command=self.toggle_services)
        self.start_btn.grid(row=0, column=0, padx=10)

        self.web_btn = tk.Button(btn_frame, text="LAUNCH APP", font=("Inter", 14, "bold"), 
                                bg="#3b82f6", fg="white", width=20, height=2, bd=0, 
                                activebackground="#2563eb", command=self.open_browser)
        self.web_btn.grid(row=0, column=1, padx=10)

        tk.Label(main_frame, text="ACTIVITY LOG", font=("Inter", 10, "bold"), fg="#64748b", bg="#0f172a").pack(anchor="w")
        
        log_container = tk.Frame(main_frame, bg="#1e293b", bd=1, relief="flat")
        log_container.pack(fill="both", expand=True)

        self.log_widget = tk.Text(log_container, bg="#1e293b", fg="#e2e8f0", font=("Consolas", 10), 
                                 padx=10, pady=10, borderwidth=0, state="disabled")
        self.log_widget.pack(fill="both", expand=True)

    def log(self, msg):
        timestamp = time.strftime("%H:%M:%S")
        self.log_widget.config(state="normal")
        self.log_widget.insert("end", f"[{timestamp}] {msg}\n")
        self.log_widget.see("end")
        self.log_widget.config(state="disabled")

    def toggle_services(self):
        if not self.is_running:
            threading.Thread(target=self.start_logic, daemon=True).start()
        else:
            self.stop_logic()

    def start_logic(self):
        self.log("Attempting to start services...")
        self.start_btn.config(state="disabled")
        
        try:
            # Start MySQL
            if os.path.exists(self.mysql_bin):
                self.log("Launching MariaDB...")
                try:
                    # Note: --defaults-file must be first
                    # Using relative path for my.ini, assuming we are running from correct cwd context or just passing full path
                    my_ini_path = os.path.join(self.suite_dir, "mysql", "bin", "my.ini")
                    # FIX: Explicitly set datadir to absolute path to avoid "ibdata1 must be writable" errors
                    data_dir = os.path.join(self.suite_dir, "mysql", "data")
                    
                    self.mysql_process = subprocess.Popen([
                        self.mysql_bin, 
                        f"--defaults-file={my_ini_path}", 
                        f"--datadir={data_dir}",
                        "--console"
                    ], 
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    cwd=os.path.join(self.suite_dir, "mysql"))
                except Exception as e:
                    self.log(f"MySQL Error: {str(e)}")
            else:
                self.log("WARNING: Database engine (MySQL) not found. Dynamic features will not work.")

            # Start PHP Built-in Server
            self.log("Launching PHP Engine...")
            
            # Check if PHP exists
            if not os.path.exists(self.php_exe):
                 self.log(f"CRITICAL: PHP not found at {self.php_exe}")
                 self.stop_logic()
                 return

            # Document Root is the Project Root (HealthPro folder)
            doc_root = self.project_root
            
            cmd = [self.php_exe, "-S", "localhost:80", "-t", doc_root]
            self.php_process = subprocess.Popen(cmd, creationflags=subprocess.CREATE_NO_WINDOW)
            
            time.sleep(2) # Give it a moment to bind ports
            
            if self.php_process.poll() is None:
                self.is_running = True
                self.root.after(0, self.update_ui_state, True)
                self.log("SUCCESS: HealthPro Suite is now LIVE on http://localhost")
            else:
                self.log("ERROR: PHP failed to start. Port 80 might be in use.")
                self.stop_logic()
                
        except Exception as e:
            self.log(f"CRITICAL ERROR: {str(e)}")
            self.stop_logic()

    def stop_logic(self):
        self.log("Shutting down...")
        if self.php_process:
            self.php_process.terminate()
        if self.mysql_process:
            self.mysql_process.terminate()
        
        self.is_running = False
        self.root.after(0, self.update_ui_state, False)
        self.log("All services stopped.")

    def update_ui_state(self, running):
        if running:
            self.status_indicator.config(fg="#10b981")
            self.status_text.config(text="SYSTEM ACTIVE", fg="#10b981")
            self.start_btn.config(text="STOP SERVICES", bg="#ef4444", state="normal")
        else:
            self.status_indicator.config(fg="#ef4444")
            self.status_text.config(text="SYSTEM OFFLINE", fg="#ef4444")
            self.start_btn.config(text="START SERVICES", bg="#10b981", state="normal")

    def open_browser(self):
        webbrowser.open("http://localhost")

if __name__ == "__main__":
    root = tk.Tk()
    app = HealthProServerApp(root)
    root.mainloop()
