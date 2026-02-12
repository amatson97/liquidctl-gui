"""
System sensors monitoring via lm-sensors, nvidia-smi, and sysfs.

Provides unified interface for CPU, motherboard, and GPU temperature/status monitoring.
"""

import subprocess
import re
import glob
import logging
from pathlib import Path
from typing import Optional


logger = logging.getLogger(__name__)


def get_lm_sensors() -> Optional[str]:
    """
    Query lm-sensors for CPU/motherboard temperatures.
    Returns formatted string with temperature readings or None if unavailable.
    """
    try:
        result = subprocess.run(
            ['sensors', '-A'],  # -A: no adapters, cleaner output
            capture_output=True,
            text=True,
            timeout=2
        )
        
        if result.returncode != 0:
            return None
        
        # Get CPU model name for better context
        cpu_model = get_cpu_model()
        
        # Parse sensors output to extract key temperatures
        lines = []
        if cpu_model:
            lines.append(f"CPU: {cpu_model}")
            lines.append("")  # Blank line for separation
        
        current_chip = None
        
        for line in result.stdout.split('\n'):
            line = line.strip()
            if not line or line.startswith('Adapter:'):
                continue
            
            # Detect chip headers (e.g., "coretemp-isa-0000", "k10temp-pci-00c3")
            if not line.startswith(' ') and ':' not in line:
                current_chip = line
                continue
            
            # Filter for important temperature readings
            if ':' in line and '°C' in line:
                # Extract label and temperature
                match = re.match(r'([^:]+):\s*([+-]?\d+\.\d+)°C', line)
                if match:
                    label, temp = match.groups()
                    temp_val = float(temp)
                    
                    # Format to 1 decimal place
                    formatted_temp = f"{temp_val:.1f}"
                    
                    # Include CPU package, core temps, and edge temps
                    if any(keyword in label.lower() for keyword in 
                           ['package', 'tctl', 'tdie', 'core', 'cpu', 'edge']):
                        # Clean up label (remove "temp" prefix if redundant)
                        clean_label = label.strip()
                        lines.append(f"{clean_label}: {formatted_temp}°C")
        
        return '\n'.join(lines) if lines else None
        
    except FileNotFoundError:
        # sensors command not available
        logger.debug("lm-sensors not installed (install 'lm-sensors' package for system monitoring)")
        return None
    except subprocess.TimeoutExpired:
        logger.warning("lm-sensors query timed out")
        return None
    except Exception as e:
        logger.debug("Failed to query lm-sensors: %s", e)
        return None


def get_cpu_model() -> Optional[str]:
    """
    Get CPU model name from /proc/cpuinfo.
    Returns cleaned CPU model string or None if unavailable.
    """
    try:
        with open('/proc/cpuinfo', 'r') as f:
            for line in f:
                if line.startswith('model name'):
                    # Extract model name after the colon
                    model = line.split(':', 1)[1].strip()
                    # Clean up common suffixes and extra whitespace
                    model = re.sub(r'\s+', ' ', model)  # Normalize whitespace
                    model = re.sub(r'\s*@.*$', '', model)  # Remove clock speed
                    # Shorten common long names
                    model = model.replace('(R)', '').replace('(TM)', '')
                    model = re.sub(r'\s+', ' ', model).strip()  # Clean again
                    return model
    except Exception as e:
        logger.debug("Failed to read CPU model: %s", e)
    return None


def get_gpu_info() -> Optional[str]:
    """
    Query GPU temperatures and info (NVIDIA via nvidia-smi, AMD via sysfs).
    Returns formatted string with GPU metrics or None if no GPUs detected.
    """
    lines = []
    
    # Try NVIDIA GPUs via nvidia-smi
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=index,name,temperature.gpu,utilization.gpu,fan.speed,power.draw',
             '--format=csv,noheader,nounits'],
            capture_output=True,
            text=True,
            timeout=2
        )
        
        if result.returncode == 0 and result.stdout.strip():
            for line in result.stdout.strip().split('\n'):
                parts = [p.strip() for p in line.split(',')]
                if len(parts) >= 3:
                    gpu_idx, gpu_name, temp = parts[0], parts[1], parts[2]
                    gpu_util = parts[3] if len(parts) > 3 else 'N/A'
                    fan_speed = parts[4] if len(parts) > 4 else 'N/A'
                    power = parts[5] if len(parts) > 5 else 'N/A'
                    
                    lines.append(f"{gpu_name}: {temp}°C")
                    if gpu_util != 'N/A' and gpu_util != '[N/A]':
                        lines.append(f"  Utilization: {gpu_util}%")
                    if fan_speed != 'N/A' and fan_speed != '[N/A]':
                        lines.append(f"  Fan: {fan_speed}%")
                    if power != 'N/A' and power != '[N/A]':
                        lines.append(f"  Power: {power}W")
    except FileNotFoundError:
        # nvidia-smi not available, skip NVIDIA detection
        pass
    except Exception as e:
        logger.debug("Failed to query nvidia-smi: %s", e)
    
    # Try AMD GPUs via sysfs (amdgpu driver)
    try:
        # Find AMD GPU hwmon interfaces
        for card_path in glob.glob('/sys/class/drm/card*/device/hwmon/hwmon*'):
            try:
                # Read GPU name (name file is INSIDE hwmon directory)
                name_file = Path(card_path) / 'name'
                if name_file.exists():
                    gpu_name = name_file.read_text().strip()
                    if 'amdgpu' not in gpu_name:
                        continue  # Skip non-AMD devices
                else:
                    continue
                
                # Get better GPU name from lspci using PCI bus ID
                gpu_model = get_gpu_name_from_pci(card_path)
                
                # Read temperature (in millidegrees Celsius)
                temp_file = Path(card_path) / 'temp1_input'
                if temp_file.exists():
                    temp_millidegrees = int(temp_file.read_text().strip())
                    temp_celsius = temp_millidegrees / 1000.0
                    
                    lines.append(f"{gpu_model}: {temp_celsius:.1f}°C")
                    
                    # Try to read power draw if available
                    power_file = Path(card_path) / 'power1_average'
                    if power_file.exists():
                        power_microwatts = int(power_file.read_text().strip())
                        power_watts = power_microwatts / 1000000.0
                        lines.append(f"  Power: {power_watts:.1f}W")
            except Exception as e:
                logger.debug("Failed to read AMD GPU sensor from %s: %s", card_path, e)
                continue
    except Exception as e:
        logger.debug("Failed to query AMD GPU sensors: %s", e)
    
    return '\n'.join(lines) if lines else None


def get_gpu_name_from_pci(hwmon_path: str) -> str:
    """
    Extract GPU model name from PCI device using lspci.
    Returns GPU model name or generic fallback.
    """
    try:
        # Get PCI device path from hwmon path
        # e.g., /sys/class/drm/card1/device/hwmon/hwmon7 -> /sys/class/drm/card1/device
        device_path = Path(hwmon_path).parent.parent
        
        # Read PCI address from device path
        # The device path is a symlink to the actual PCI device
        real_device_path = device_path.resolve()
        # Extract PCI bus ID from path (e.g., 0000:0c:00.0)
        pci_id = real_device_path.name
        
        # Use lspci to get device info
        result = subprocess.run(
            ['lspci', '-s', pci_id],
            capture_output=True,
            text=True,
            timeout=1
        )
        
        if result.returncode == 0 and result.stdout.strip():
            # Parse lspci output: "0c:00.0 VGA compatible controller: Advanced Micro Devices, Inc. [AMD/ATI] Navi 33 [Radeon RX 7700S/7600/7600S/7600M XT/PRO W7600] (rev c0)"
            line = result.stdout.strip()
            
            # Extract the GPU model from brackets or after vendor name
            # Look for pattern: [Radeon ...] or similar
            bracket_match = re.search(r'\[([^\]]*(?:Radeon|RX|Vega|Navi|RDNA|Pro|XT|FirePro)[^\]]*)\]', line, re.IGNORECASE)
            if bracket_match:
                model = bracket_match.group(1)
                # Clean up model name - extract first variant before slashes
                # e.g., "Radeon RX 7700S/7600/7600S/7600M XT" -> "Radeon RX 7700S"
                if '/' in model:
                    # Keep everything before the first slash
                    model = model.split('/')[0].strip()
                return f"AMD {model}"
            
            # Fallback: extract everything after the vendor name
            if 'AMD' in line or 'ATI' in line:
                # Split on ":" and get the part after vendor
                parts = line.split(':')
                if len(parts) > 1:
                    desc = parts[1].strip()
                    # Remove vendor prefix
                    desc = re.sub(r'^Advanced Micro Devices, Inc\.\s*\[AMD/ATI\]\s*', '', desc)
                    # Clean up revision info
                    desc = re.sub(r'\s*\(rev [^)]+\)\s*$', '', desc)
                    return f"AMD {desc[:50]}"  # Limit length
        
    except FileNotFoundError:
        logger.debug("lspci not available")
    except Exception as e:
        logger.debug("Failed to get GPU name from lspci: %s", e)
    
    # Fallback to generic name
    return "AMD GPU"
