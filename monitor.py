import tkinter as tk
import customtkinter as ctk
import subprocess
import winreg
import wmi
import psutil
import keyboard
import json
import os
import sys
import threading
from datetime import datetime
from PIL import Image, ImageDraw
import pystray

import hotcases

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("green")

CONFIG_FILE = "config.json"
REG_AUTORUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME_REG = "LenovoSYSControlCenter"

class LenovoMonitor(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("Lenovo SYSControl - Suite Module")
        self.state("zoomed") 
        self.resizable(True, True)
        
        try:
            self.w = wmi.WMI()
        except Exception:
            self.w = None

        self.create_layout()
        self.load_and_register_hotkeys()
        self.update_dynamic_data()
        
        self.protocol("WM_DELETE_WINDOW", self.hide_to_tray)
        self.setup_tray()

    def get_uefi_bios_info(self):
        info = {"Vendor": "Unknown", "Version": "Unknown", "Model": "Unknown", "SecureBoot": "Unknown"}
        try:
            if self.w:
                bios = self.w.Win32_BIOS()
                comp = self.w.Win32_ComputerSystem()
                info["Vendor"] = bios.Manufacturer.strip()
                info["Version"] = bios.SMBIOSBIOSVersion.strip()
                info["Model"] = comp.Model.strip()
        except Exception:
            pass
        try:
            if info["Version"] == "Unknown" or info["Model"] == "Unknown":
                reg_key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\BIOS")
                info["Vendor"] = winreg.QueryValueEx(reg_key, "BIOSVendor")[0].strip()
                info["Version"] = winreg.QueryValueEx(reg_key, "BIOSVersion")[0].strip()
                info["Model"] = winreg.QueryValueEx(reg_key, "SystemProductName")[0].strip()
        except Exception:
            pass
        info["SecureBoot"] = self.check_secure_boot()
        return info

    def check_secure_boot(self):
        try:
            cmd = "powershell (Confirm-SecureBootUEFI)"
            output = subprocess.check_output(cmd, shell=True).decode().strip()
            return "Enabled" if "True" in output else "Disabled"
        except Exception:
            return "Requires Admin Rights"

    def check_is_autorun_enabled(self):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_AUTORUN_KEY, 0, winreg.KEY_READ)
            winreg.QueryValueEx(key, APP_NAME_REG)
            return True
        except Exception:
            return False

    def toggle_autorun(self):
        is_checked = self.switch_autorun.get()
        script_path = os.path.abspath(sys.argv[0])
        cmd_str = f'"{sys.executable}" "{script_path}"'

        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_AUTORUN_KEY, 0, winreg.KEY_WRITE)
            if is_checked:
                winreg.SetValueEx(key, APP_NAME_REG, 0, winreg.REG_SZ, cmd_str)
                self.log_message("🏎️ Registry Updated: Windows Startup Autorun ENABLED.")
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME_REG)
                    self.log_message("🏎️ Registry Updated: Windows Startup Autorun DISABLED.")
                except FileNotFoundError:
                    pass
        except Exception as e:
            self.log_message(f"❌ Autorun Configuration Error: {str(e)}")

    def create_layout(self):
        self.tabview = ctk.CTkTabview(self, corner_radius=10)
        self.tabview.pack(fill="both", expand=True, padx=20, pady=(15, 5))
        
        self.tab_hardware = self.tabview.add("Hardware Telemetry")
        self.tab_shortcuts = self.tabview.add("Shortcut Manager")
        
        # --- TAB: TELEMETRY ---
        bios_info = self.get_uefi_bios_info()
        frame_uefi = ctk.CTkFrame(self.tab_hardware)
        frame_uefi.pack(fill="x", padx=15, pady=10)
        
        ctk.CTkLabel(frame_uefi, text="[ UEFI / BIOS Firmware Info ]", font=("Consolas", 14, "bold"), text_color="#00ff66").pack(anchor="w", padx=15, pady=5)
        ctk.CTkLabel(frame_uefi, text=f"Device Model:  {bios_info['Model']}", font=("Consolas", 12)).pack(anchor="w", padx=25)
        ctk.CTkLabel(frame_uefi, text=f"BIOS Vendor:   {bios_info['Vendor']}", font=("Consolas", 12)).pack(anchor="w", padx=25)
        ctk.CTkLabel(frame_uefi, text=f"BIOS Version:  {bios_info['Version']}", font=("Consolas", 12)).pack(anchor="w", padx=25)
        ctk.CTkLabel(frame_uefi, text=f"Secure Boot:   {bios_info['SecureBoot']}", font=("Consolas", 12)).pack(anchor="w", padx=25, pady=(0, 10))
        
        frame_hw = ctk.CTkFrame(self.tab_hardware)
        frame_hw.pack(fill="both", expand=True, padx=15, pady=10)
        
        ctk.CTkLabel(frame_hw, text="[ Live Hardware Monitor ]", font=("Consolas", 14, "bold"), text_color="#00ff66").pack(anchor="w", padx=15, pady=5)
        
        self.lbl_cpu = ctk.CTkLabel(frame_hw, text="CPU Load: Calculating...", font=("Consolas", 12))
        self.lbl_cpu.pack(anchor="w", padx=25)
        self.progress_cpu = ctk.CTkProgressBar(frame_hw)
        self.progress_cpu.pack(fill="x", padx=25, pady=(0, 10))

        self.lbl_ram = ctk.CTkLabel(frame_hw, text="RAM Usage: Calculating...", font=("Consolas", 12))
        self.lbl_ram.pack(anchor="w", padx=25)
        self.progress_ram = ctk.CTkProgressBar(frame_hw)
        self.progress_ram.pack(fill="x", padx=25, pady=(0, 10))

        self.lbl_battery = ctk.CTkLabel(frame_hw, text="Battery: Calculating...", font=("Consolas", 12))
        self.lbl_battery.pack(anchor="w", padx=25, pady=(0, 5))

        self.lbl_power = ctk.CTkLabel(frame_hw, text="OS Power Plan: Unknown", font=("Consolas", 12))
        self.lbl_power.pack(anchor="w", padx=25, pady=(0, 10))

        # Autorun switch
        autorun_status = self.check_is_autorun_enabled()
        self.switch_autorun = ctk.CTkSwitch(frame_hw, text="Launch at Windows Startup (Autorun)", font=("Consolas", 12), command=self.toggle_autorun)
        if autorun_status:
            self.switch_autorun.select()
        self.switch_autorun.pack(anchor="w", padx=25, pady=15)

        # --- TAB: SHORTCUT MANAGER ---
        split_frame = ctk.CTkFrame(self.tab_shortcuts, fg_color="transparent")
        split_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        frame_add = ctk.CTkFrame(split_frame, width=350)
        frame_add.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        
        ctk.CTkLabel(frame_add, text="[ Create New Hot Case ]", font=("Consolas", 14, "bold"), text_color="#00ff66").pack(anchor="w", padx=15, pady=10)
        
        ctk.CTkLabel(frame_add, text="Hotkey / Scan Code (e.g., ctrl+alt+z or 183):", font=("Consolas", 12)).pack(anchor="w", padx=25, pady=2)
        self.entry_key = ctk.CTkEntry(frame_add, font=("Consolas", 12))
        self.entry_key.pack(fill="x", padx=25, pady=5)
        
        ctk.CTkLabel(frame_add, text="Event Action String (open, url, cmd, kill, toast, if):", font=("Consolas", 12)).pack(anchor="w", padx=25, pady=2)
        self.entry_command = ctk.CTkEntry(frame_add, font=("Consolas", 12))
        self.entry_command.pack(fill="x", padx=25, pady=5)
        
        btn_save = ctk.CTkButton(frame_add, text="Save & Register Case", font=("Consolas", 12, "bold"), command=self.save_new_hotkey)
        btn_save.pack(fill="x", padx=25, pady=20)

        # Table Wrapper
        self.frame_table_wrapper = ctk.CTkFrame(split_frame)
        self.frame_table_wrapper.pack(side="right", fill="both", expand=True, padx=5, pady=5)
        
        ctk.CTkLabel(self.frame_table_wrapper, text="[ Active JSON Registry Database ]", font=("Consolas", 14, "bold"), text_color="#00ff66").pack(anchor="w", padx=15, pady=10)
        
        self.scrollable_table = ctk.CTkScrollableFrame(self.frame_table_wrapper, fg_color="#141414")
        self.scrollable_table.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        # --- BOTTOM SECTION: LIVE EVENT TRACKER ---
        frame_console = ctk.CTkFrame(self, corner_radius=10)
        frame_console.pack(fill="both", expand=True, padx=20, pady=5)

        ctk.CTkLabel(frame_console, text="[ Live Event & Shortcut Tracker ]", font=("Consolas", 14, "bold"), text_color="#00ff66").pack(anchor="w", padx=15, pady=(5, 2))
        
        self.txt_console = ctk.CTkTextbox(frame_console, font=("Consolas", 11), text_color="#00ff66", fg_color="#0a0a0a")
        self.txt_console.pack(fill="both", expand=True, padx=15, pady=(0, 10))
        
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=(5, 15))
        
        btn_tray = ctk.CTkButton(btn_frame, text="Minimize to Tray", font=("Consolas", 12, "bold"), fg_color="#1f538d", command=self.hide_to_tray)
        btn_tray.pack(side="left", padx=10)
        btn_close = ctk.CTkButton(btn_frame, text="Terminate Suite", font=("Consolas", 12, "bold"), fg_color="#942a2a", command=self.safe_exit)
        btn_close.pack(side="left", padx=10)

    def log_message(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.txt_console.insert(tk.END, f"[{timestamp}] {message}\n")
        self.txt_console.see(tk.END)

    def render_shortcuts_table(self, shortcuts_data):
        """Clears and re-renders the visual active hotkeys table layout"""
        for widget in self.scrollable_table.winfo_children():
            widget.destroy()

        for index, (key, command) in enumerate(shortcuts_data.items()):
            row_frame = ctk.CTkFrame(self.scrollable_table, fg_color="transparent")
            row_frame.pack(fill="x", pady=2, padx=5)

            lbl_key = ctk.CTkLabel(row_frame, text=f"[{key}]", font=("Consolas", 11, "bold"), text_color="#00ff66", width=90, anchor="w")
            lbl_key.pack(side="left", padx=5)

            # Column 2: Command Action Text
            lbl_cmd = ctk.CTkLabel(row_frame, text=command, font=("Consolas", 11), text_color="#ffffff", anchor="w")
            lbl_cmd.pack(side="left", fill="x", expand=True, padx=5)

            # Column 3: Delete Button
            btn_del = ctk.CTkButton(row_frame, text="Delete", font=("Consolas", 10, "bold"), fg_color="#7a1e1e", hover_color="#942a2a", width=70, height=22,
                                    command=lambda k=key: self.delete_hotkey(k))
            btn_del.pack(side="right", padx=5)

    def load_and_register_hotkeys(self):
        """Loads configuration from config.json and registers native hardware hooks"""
        try:
            keyboard.unhook_all()
        except Exception:
            pass

        if not os.path.exists(CONFIG_FILE) or os.path.getsize(CONFIG_FILE) == 0:
            default_config = {
                "ctrl+alt+x": 'open "code"',
                "183": 'if cpu > 80 then toast "Warning! Ryzen load is too high!" else cmd "git status"',
                "ctrl+alt+t": 'if battery < 25 and not charging then toast "Lenovo battery state low!" else open "cmd"'
            }
            with open(CONFIG_FILE, "w") as f:
                json.dump(default_config, f, indent=2)

        self.log_message("Synchronizing event registry from config.json...")

        try:
            with open(CONFIG_FILE, "r") as f:
                shortcuts_data = json.load(f)

            self.render_shortcuts_table(shortcuts_data)

            for key_trigger, command_string in shortcuts_data.items():
                actual_key = int(key_trigger) if key_trigger.isdigit() else key_trigger
                suppress_flag = True if isinstance(actual_key, int) else False

                keyboard.add_hotkey(
                    actual_key,
                    lambda cmd=command_string: hotcases.parse_and_execute(cmd, self.log_message),
                    suppress=suppress_flag
                )
                self.log_message(f"Registered link: [{actual_key}] ➡️ {command_string}")

            self.log_message("✅ Core Event Loop active. UI Table rendered.")
        except Exception as e:
            self.log_message(f"❌ Error during registry injection: {str(e)}")

    def save_new_hotkey(self):
        """Parses custom UI inputs, appends them to JSON database, and hot-reloads listeners"""
        raw_key = self.entry_key.get().strip()
        raw_command = self.entry_command.get().strip()

        if not raw_key or not raw_command:
            self.log_message("⚠️ Error: Both input fields are mandatory.")
            return

        try:
            shortcuts_data = {}
            if os.path.exists(CONFIG_FILE) and os.path.getsize(CONFIG_FILE) > 0:
                try:
                    with open(CONFIG_FILE, "r") as f:
                        shortcuts_data = json.load(f)
                except json.JSONDecodeError:
                    shortcuts_data = {}

            shortcuts_data[raw_key] = raw_command

            with open(CONFIG_FILE, "w") as f:
                json.dump(shortcuts_data, f, indent=2)

            self.log_message(f"💾 Database updated: [{raw_key}] mapped successfully.")
            self.entry_key.delete(0, tk.END)
            self.entry_command.delete(0, tk.END)
            self.load_and_register_hotkeys()
        except Exception as e:
            self.log_message(f"❌ Failed to write layout changes: {str(e)}")

    def delete_hotkey(self, key_to_delete):
        """Drops a hotkey mapping from configuration and updates registry tracking live"""
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, "r") as f:
                    shortcuts_data = json.load(f)
                
                if key_to_delete in shortcuts_data:
                    del shortcuts_data[key_to_delete]
                    
                    with open(CONFIG_FILE, "w") as f:
                        json.dump(shortcuts_data, f, indent=2)
                        
                    self.log_message(f"🗑️ Erased from database: [{key_to_delete}]")
                    self.load_and_register_hotkeys()
        except Exception as e:
            self.log_message(f"❌ Error during shortcut drop execution: {str(e)}")

    def update_dynamic_data(self):
        """Updates main desktop tracking telemetry loops every 1000 milliseconds"""
        cpu_p = psutil.cpu_percent()
        self.lbl_cpu.configure(text=f"CPU Load:       {cpu_p}%")
        self.progress_cpu.set(cpu_p / 100.0)
        
        # FIXED: Re-established mathematical exponential division notation 1024**2
        ram = psutil.virtual_memory()
        self.lbl_ram.configure(text=f"RAM Usage:      {ram.percent}% ({ram.used // (1024**2)}MB / {ram.total // (1024**2)}MB)")
        self.progress_ram.set(ram.percent / 100.0)
        
        battery = psutil.sensors_battery()
        if battery:
            plugged = "Charging" if battery.power_plugged else "Discharging"
            self.lbl_battery.configure(text=f"Battery:        {battery.percent}% [{plugged}]")
        else:
            self.lbl_battery.configure(text="Battery:        Not Detected")
            
        try:
            cmd = "powercfg /getactivescheme"
            out = subprocess.check_output(cmd, shell=True).decode(errors='ignore')
            if "Balanced" in out:
                mode = "Intelligent Cooling (Balanced)"
            elif "High performance" in out:
                mode = "Extreme Performance"
            else:
                mode = "Power Saver / Battery Saving"
            self.lbl_power.configure(text=f"OS Power Plan:  {mode}")
        except Exception:
            self.lbl_power.configure(text="OS Power Plan:  Unable to parse")

        self.after(1000, self.update_dynamic_data)

    def create_tray_image(self):
        """Generates a native 64x64 green dashboard bitmap asset for taskbar visibility"""
        image = Image.new('RGB', (64, 64), color='#0a0a0a')
        dc = ImageDraw.Draw(image)
        dc.rectangle((16, 16, 48, 48), fill='#00ff66')
        return image

    def setup_tray(self):
        """Spawns an asynchronous pystray system tray wrapper context"""
        menu = pystray.Menu(
            pystray.MenuItem("Expand Dashboard", self.show_from_tray),
            pystray.MenuItem("Terminate Session", self.safe_exit)
        )
        self.tray_icon = pystray.Icon("LenovoSYSControl", self.create_tray_image(), "Lenovo SYSControl Center", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def hide_to_tray(self):
        """Drops dashboard visibility into low-level headless background mode"""
        self.withdraw()
        print("[BACKGROUND] Lenovo SYSControl minimized to tray. Shortcuts active.")

    def show_from_tray(self):
        """Forces runtime visualization back into full primary workspace layouts"""
        self.deiconify()
        self.state("zoomed")

    def safe_exit(self):
        """Safely flushes active low-level runtime dependencies on destruction"""
        keyboard.unhook_all()
        if hasattr(self, 'tray_icon'):
            self.tray_icon.stop()
        self.quit()
        self.destroy()

# FIXED: Standard boilerplate execution initialization dunder strings
if __name__ == "__main__":
    app = LenovoMonitor()
    app.mainloop()
