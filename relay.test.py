import serial
import time
import logging
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RelayTester:
    def __init__(self, port: str = '/dev/ttyUSB0', baud_rate: int = 9600):
        """Initialize relay tester with serial connection.
        
        Args:
            port: Serial port name
            baud_rate: Serial baud rate
        """
        self.port = port
        self.baud_rate = baud_rate
        self.serial_conn: Optional[serial.Serial] = None
        
    def connect(self) -> bool:
        """Establish serial connection.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baud_rate,
                timeout=1
            )
            time.sleep(2)  # Wait for Arduino to reset
            logger.info(f"Connected to {self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            return False
            
    def toggle_relay(self, relay_number: int) -> bool:
        """Toggle specific relay on/off.
        
        Args:
            relay_number: Relay number (1-8)
            
        Returns:
            bool: True if command sent successfully
        """
        if not self.serial_conn:
            logger.error("Not connected")
            return False
            
        try:
            # Simple command format: 'Rn' where n is relay number
            command = f'R{relay_number}'.encode()
            self.serial_conn.write(command)
            logger.info(f"Toggled relay {relay_number}")
            return True
        except Exception as e:
            logger.error(f"Failed to toggle relay: {e}")
            return False
            
    def set_relay(self, relay_number: int, state: bool) -> bool:
        """Set specific relay to on or off.
        
        Args:
            relay_number: Relay number (1-8)
            state: True for ON, False for OFF
            
        Returns:
            bool: True if command sent successfully
        """
        if not self.serial_conn:
            logger.error("Not connected")
            return False
            
        try:
            # Command format: 'RnS1' or 'RnS0' where n is relay number
            command = f'R{relay_number}S{1 if state else 0}'.encode()
            self.serial_conn.write(command)
            logger.info(f"Set relay {relay_number} {'ON' if state else 'OFF'}")
            return True
        except Exception as e:
            logger.error(f"Failed to set relay: {e}")
            return False
            
    def test_all_relays(self):
        """Test all relays by turning them on and off in sequence."""
        logger.info("Testing all relays...")
        
        for relay in range(1, 9):  # Test relays 1-8
            logger.info(f"Testing relay {relay}")
            
            # Turn relay ON
            self.set_relay(relay, True)
            time.sleep(1)
            
            # Turn relay OFF
            self.set_relay(relay, False)
            time.sleep(1)
            
    def close(self):
        """Close serial connection."""
        if self.serial_conn:
            self.serial_conn.close()
            logger.info("Connection closed")

def main():
    # Create tester instance
    tester = RelayTester()
    
    # Try to connect
    if not tester.connect():
        logger.error("Failed to connect. Exiting.")
        return
    
    try:
        while True:
            print("\nRelay Tester Menu:")
            print("1. Toggle specific relay")
            print("2. Set relay state")
            print("3. Test all relays")
            print("4. Exit")
            
            choice = input("Enter choice (1-4): ")
            
            if choice == '1':
                relay_num = int(input("Enter relay number (1-8): "))
                tester.toggle_relay(relay_num)
                
            elif choice == '2':
                relay_num = int(input("Enter relay number (1-8): "))
                state = input("Enter state (on/off): ").lower() == 'on'
                tester.set_relay(relay_num, state)
                
            elif choice == '3':
                tester.test_all_relays()
                
            elif choice == '4':
                break
                
            time.sleep(0.5)  # Short delay between commands
            
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        tester.close()

if __name__ == "__main__":
    main() 