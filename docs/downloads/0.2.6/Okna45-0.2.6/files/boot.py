"""Stable recovery hook. Keep this and ok45_boot.py outside regular updates."""
from ok45_boot import recover, mark_boot
recover()
recover('/system/pkg', '/system/pkg/installed.json')
mark_boot()
