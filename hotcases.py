import subprocess
import webbrowser
import os
import re
import psutil

def is_process_running(process_name):
    """Checks if a specific process is currently active in Windows via tasklist"""
    try:
        output = subprocess.check_output(f'tasklist /FI "IMAGENAME eq {process_name}"', shell=True).decode(errors='ignore')
        return process_name.lower() in output.lower()
    except Exception:
        return False

def check_hardware_condition(condition_str, log_callback):
    """
    Parses and evaluates hardware telemetry conditions:
    - battery < 20
    - cpu > 80
    - battery < 30 and not charging
    """
    condition_str = condition_str.strip()
    
    cpu_now = psutil.cpu_percent()
    bat_stat = psutil.sensors_battery()
    bat_now = bat_stat.percent if bat_stat else 100
    charging_now = bat_stat.power_plugged if bat_stat else True

    context = {
        "cpu": cpu_now,
        "battery": bat_now,
        "charging": charging_now
    }

    prepared_str = condition_str.lower()
    
    try:
        result = eval(prepared_str, {"__builtins__": None}, context)
        log_callback(f"HW CHECK: '{condition_str}' evaluated to {result} (CPU:{cpu_now}%, Bat:{bat_now}%, Charge:{charging_now})")
        return bool(result)
    except Exception as e:
        log_callback(f"❌ HW EVAL ERROR: {str(e)}")
        return False

def execute_single_command(command_str, log_callback):
    """Executes a single basic automation instruction"""
    command_str = command_str.strip()
    
    # 1. OPEN Scenario: Launch apps
    if command_str.startswith('open "') and command_str.endswith('"'):
        app_name = command_str[6:-1]
        subprocess.Popen(app_name, shell=True)
        log_callback(f"SUCCESS: Process '{app_name}' initiated.")
        return True
        
    # 2. URL Scenario: Open websites
    elif command_str.startswith('url "') and command_str.endswith('"'):
        link = command_str[5:-1]
        webbrowser.open(link)
        log_callback(f"SUCCESS: Link '{link}' opened.")
        return True
        
    # 3. CMD Scenario: Run terminal scripts
    elif command_str.startswith('cmd "') and command_str.endswith('"'):
        shell_cmd = command_str[5:-1]
        target_dir = r"D:\vscode\xtechnologies progects\LENOVO syscontrol"
        if os.path.exists(target_dir):
            final_action = f'start cmd /k "cd /d {target_dir} && {shell_cmd}"'
        else:
            final_action = f'start cmd /k "{shell_cmd}"'
        subprocess.Popen(final_action, shell=True)
        log_callback(f"SUCCESS: Terminal executed '{shell_cmd}'.")
        return True

    # 4. KILL Scenario: Terminate processes
    elif command_str.startswith('kill "') and command_str.endswith('"'):
        proc_name = command_str[6:-1]
        subprocess.Popen(f'taskkill /F /T /IM {proc_name}', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        log_callback(f"SUCCESS: Signal taskkill sent to '{proc_name}'.")
        return True

    # 5. TOAST Scenario: Native Windows 11 notifications via win11toast
    elif command_str.startswith('toast "') and command_str.endswith('"'):
        msg_text = command_str[7:-1]
        try:
            from win11toast import toast
            toast('Lenovo SYSControl', msg_text)
            log_callback(f"SUCCESS: win11toast notification sent: [{msg_text}].")
        except Exception as e:
            log_callback(f"❌ TOAST LIBRARY ERROR: {str(e)}")
        return True
        
    return False

def parse_and_execute(command_str, log_callback):
    """Main interpreter for structural IF-THEN-ELSE rules"""
    command_str = command_str.strip()
    log_callback(f"INTERRUPT: Processing rule -> {command_str}")
    
    # Hardware condition evaluation
    if command_str.lower().startswith("if battery ") or command_str.lower().startswith("if cpu "):
        match = re.match(r'^if\s+(.+?)\s+then\s+(.+?)(?:\s+else\s+(.+))?$', command_str, re.IGNORECASE)
        if match:
            condition = match.group(1)
            then_branch = match.group(2)
            else_branch = match.group(3)
            
            if check_hardware_condition(condition, log_callback):
                execute_single_command(then_branch, log_callback)
            elif else_branch:
                execute_single_command(else_branch, log_callback)
            return

    # Process condition evaluation
    if_proc_pattern = r'^if\s+process\s+"([^"]+)"\s+running\s+then\s+(.+?)(?:\s+else\s+(.+))?$'
    match_proc = re.match(if_proc_pattern, command_str, re.IGNORECASE)
    
    if match_proc:
        process_name = match_proc.group(1)
        then_branch = match_proc.group(2)
        else_branch = match_proc.group(3)
        
        if is_process_running(process_name):
            execute_single_command(then_branch, log_callback)
        elif else_branch:
            execute_single_command(else_branch, log_callback)
    else:
        status = execute_single_command(command_str, log_callback)
        if not status:
            log_callback(f"❌ SYNTAX ERROR: Unsupported instruction: {command_str}")
