# Core components exports

# Import main functions from logging_config for compatibility
from .logging_config import (
    get_user_logger,
    get_current_session,
    get_logger,
    initialize_logging,
    shutdown_logging,
)

# Import config manager
from .config_manager import get_config_manager

# Import comments
from .comments import get_comment_manager, EMSComment

# Import signal classes
from .signal import (
    Signal,
    HR_Gen_Signal,
    HRAuroraSignal,
    SignalGroup,
)  # HR_Gen_Signal es alias retro
