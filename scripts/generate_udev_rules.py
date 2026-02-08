#!/usr/bin/env python3
"""
Generate udev rules dynamically by scanning for liquidctl devices
and extracting their vendor IDs.
"""
import sys
import os

def get_liquidctl_vendor_ids():
    """Get vendor IDs from connected liquidctl devices and common known vendors."""
    vendor_ids = set()
    
    # Try to use liquidctl API to find devices
    try:
        from liquidctl.driver import find_liquidctl_devices
        
        for device in find_liquidctl_devices():
            # Extract vendor ID from device
            if hasattr(device, 'vendor_id'):
                vendor_ids.add(device.vendor_id)
            elif hasattr(device, 'device') and hasattr(device.device, 'idVendor'):
                vendor_ids.add(device.device.idVendor)
            # For USB HID devices
            elif hasattr(device, '_vendor_id'):
                vendor_ids.add(device._vendor_id)
    except ImportError:
        print("Warning: liquidctl not available, using fallback vendor list", file=sys.stderr)
    except Exception as e:
        print(f"Warning: Could not enumerate devices: {e}", file=sys.stderr)
    
    # Fallback: Include common liquidctl-supported vendors
    # This ensures rules work even if devices aren't currently connected
    common_vendors = {
        0x1e71: 'NZXT',
        0x1b1c: 'Corsair', 
        0x0b05: 'ASUS',
        0x3842: 'EVGA',
        0x1044: 'Gigabyte',
        0x2516: 'Cooler Master',
        0x0c70: 'Aquacomputer',
    }
    
    # Optionally scan current USB devices
    try:
        import usb.core
        for dev in usb.core.find(find_all=True):
            if dev.idVendor in common_vendors:
                vendor_ids.add(dev.idVendor)
    except:
        pass
    
    # Always include common vendors even if not detected
    vendor_ids.update(common_vendors.keys())
    
    return sorted(vendor_ids), common_vendors


def generate_udev_rules():
    """Generate udev rules for all liquidctl vendors."""
    vendor_ids, vendor_names = get_liquidctl_vendor_ids()
    
    rules = []
    rules.append("# Grant access to hidraw nodes for liquidctl-supported devices")
    rules.append("# Auto-generated from liquidctl device database\n")
    
    for vid in vendor_ids:
        vendor_name = vendor_names.get(vid, f"Unknown (0x{vid:04x})")
        rules.append(f'# {vendor_name}')
        rules.append(f'SUBSYSTEM=="hidraw", ATTRS{{idVendor}}=="{vid:04x}", MODE:="0660", GROUP:="liquidctl"')
    
    rules.append("")
    rules.append("# Fix hwmon permissions when devices are added (works for ALL devices)")
    rules.append('SUBSYSTEM=="hwmon", ACTION=="add", RUN+="/usr/local/bin/fix-hwmon-permissions /sys%p"')
    
    return '\n'.join(rules)


if __name__ == '__main__':
    print(generate_udev_rules())
