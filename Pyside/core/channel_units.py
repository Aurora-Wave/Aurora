"""
Centralized channel units configuration for all Aurora Wave components.
This module provides consistent unit labels across all tabs and visualizations.
"""

# Channel units mapping
CHANNEL_UNITS = {
    "ECG": "mV",
    "HR_gen": "BPM",
    "FBP": "mmHg",
    "Valsalva": "mmHg",
    "SBP": "mmHg",
    "DBP": "mmHg",
    "MAP": "mmHg",
    "CO": "L/min",
    "TPR": "mmHg·s/mL",
    "SV": "mL",
}


def get_channel_unit(channel_name: str) -> str:
    """
    Get the unit for a given channel name.

    Args:
        channel_name: Name of the channel

    Returns:
        Unit string, or empty string if not found
    """
    return CHANNEL_UNITS.get(channel_name, "")


def get_channel_label_with_unit(channel_name: str) -> str:
    """
    Get the channel name with unit in parentheses.

    Args:
        channel_name: Name of the channel

    Returns:
        Formatted label like "ECG (mV)" or just "ECG" if no unit
    """
    unit = get_channel_unit(channel_name)
    return f"{channel_name} ({unit})" if unit else channel_name
