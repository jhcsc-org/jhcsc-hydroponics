import threading
import logging

logger = logging.getLogger(__name__)

class RelayHandler:
    """Manages relay states with thread-safe operations."""
    
    def __init__(self, number_of_relays=5):
        """Initialize relay handler.
        
        Args:
            number_of_relays: Number of relays to manage (default: 5)
        """
        # all relays start in OFF state
        self.relay_states = [False] * number_of_relays
        self.lock = threading.Lock()  # ensures thread-safe state changes
        self.number_of_relays = number_of_relays
        logger.info(f"Initialized RelayHandler with {self.number_of_relays} relays.")

    def get_relay_states(self):
        """Get current states of all relays thread-safely.
        
        Returns:
            List of boolean states
        """
        with self.lock:
            # return copy to prevent external modifications
            return self.relay_states.copy()

    def set_relay_state(self, index, state):
        """Set specific relay to desired state.
        
        Args:
            index: Relay index to modify
            state: Desired state (True=ON, False=OFF)
            
        Raises:
            IndexError: If relay index is invalid
        """
        with self.lock:
            if 0 <= index < self.number_of_relays:
                self.relay_states[index] = state
                logger.debug(f"Set relay {index} to {'ON' if state else 'OFF'}.")
            else:
                logger.error(f"Relay index {index} out of range.")
                raise IndexError("Relay index out of range.")

    def toggle_relay(self, index):
        with self.lock:
            if 0 <= index < self.number_of_relays:
                self.relay_states[index] = not self.relay_states[index]
                logger.debug(f"Toggled relay {index} to {'ON' if self.relay_states[index] else 'OFF'}.")
            else:
                logger.error(f"Relay index {index} out of range.")
                raise IndexError("Relay index out of range.")

    def set_all_relays(self, state):
        with self.lock:
            self.relay_states = [state] * self.number_of_relays
            logger.debug(f"Set all relays to {'ON' if state else 'OFF'}.")

    def get_relay_state(self, index):
        """Get state of a specific relay thread-safely.
        
        Args:
            index: Relay index to query
            
        Returns:
            bool: Current state of the relay (True=ON, False=OFF)
            
        Raises:
            IndexError: If relay index is invalid
        """
        with self.lock:
            if 0 <= index < self.number_of_relays:
                return self.relay_states[index]
            else:
                logger.error(f"Relay index {index} out of range.")
                raise IndexError("Relay index out of range.")
