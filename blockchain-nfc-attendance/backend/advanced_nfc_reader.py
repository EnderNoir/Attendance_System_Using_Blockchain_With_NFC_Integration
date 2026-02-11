"""
Advanced NFC Reader with simulated mode for testing
Supports both real NFC hardware and simulated NFC tags
"""

import logging
from typing import Optional, Dict, List
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AdvancedNFCReader:
    """
    Advanced NFC Reader with hardware and simulation modes
    """
    
    def __init__(self, use_simulation=True):
        """
        Initialize NFC Reader
        
        Args:
            use_simulation: If True, use simulation mode instead of hardware
        """
        self.use_simulation = use_simulation
        self.nfc_id = None
        self.last_read = None
        self.read_history: List[Dict] = []
        self.clf = None
        
        if not use_simulation:
            self.initialize_hardware()
        else:
            logger.info("NFC Reader initialized in SIMULATION mode")
    
    def initialize_hardware(self):
        """Initialize actual NFC hardware"""
        try:
            import nfc.clf
            self.clf = nfc.clf.ContactlessFrontend('usb')
            logger.info("✓ NFC hardware initialized successfully")
        except ImportError:
            logger.warning("⚠ pynfc not installed. Use pip install pynfc")
            self.use_simulation = True
        except Exception as e:
            logger.warning(f"⚠ NFC hardware not available: {e}")
            logger.info("Switching to simulation mode")
            self.use_simulation = True
    
    def read_tag(self, timeout: int = 10) -> Optional[str]:
        """
        Read an NFC tag
        
        Args:
            timeout: Timeout in seconds
            
        Returns:
            NFC ID if successful, None otherwise
        """
        if self.use_simulation:
            return self._simulate_read()
        else:
            return self._read_hardware(timeout)
    
    def _simulate_read(self) -> Optional[str]:
        """Simulate NFC tag read"""
        logger.info("📱 Simulated: Place NFC tag near reader...")
        # In real implementation, this would wait for user input
        # For now, return a sample NFC ID
        return None
    
    def _read_hardware(self, timeout: int) -> Optional[str]:
        """Read from actual NFC hardware"""
        if self.clf is None:
            logger.error("NFC Reader not initialized")
            return None
        
        try:
            logger.info(f"📱 Waiting for NFC tag ({timeout}s timeout)...")
            import nfc.clf
            target = self.clf.sense(nfc.clf.RemoteTarget, timeout=timeout)
            
            if target:
                # Extract NFC ID from target
                nfc_id = self._extract_nfc_id(target)
                self._record_read(nfc_id)
                logger.info(f"✓ NFC tag read: {nfc_id}")
                return nfc_id
            else:
                logger.warning("No NFC tag detected")
                return None
                
        except Exception as e:
            logger.error(f"Error reading NFC tag: {e}")
            return None
    
    def _extract_nfc_id(self, target) -> str:
        """Extract NFC ID from target"""
        try:
            if hasattr(target, 'sensf_res'):
                return target.sensf_res[1:].decode()
            elif hasattr(target, 'identifier'):
                return target.identifier.hex()
            else:
                return str(target)[:16]
        except:
            return str(target)[:16]
    
    def _record_read(self, nfc_id: str):
        """Record a successful read"""
        self.nfc_id = nfc_id
        self.last_read = datetime.now()
        self.read_history.append({
            'nfc_id': nfc_id,
            'timestamp': self.last_read.isoformat(),
            'success': True
        })
    
    def simulate_tag(self, nfc_id: str) -> str:
        """
        Simulate reading a specific NFC tag
        
        Args:
            nfc_id: NFC ID to simulate
            
        Returns:
            The simulated NFC ID
        """
        logger.info(f"📱 Simulating NFC tag read: {nfc_id}")
        self._record_read(nfc_id)
        return nfc_id
    
    def get_last_nfc_id(self) -> Optional[str]:
        """Get the last read NFC ID"""
        return self.nfc_id
    
    def get_read_history(self) -> List[Dict]:
        """Get history of all reads"""
        return self.read_history
    
    def close(self):
        """Close NFC reader"""
        if self.clf:
            self.clf.close()
            logger.info("NFC Reader closed")
    
    def __enter__(self):
        """Context manager support"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager cleanup"""
        self.close()


# Usage examples
if __name__ == "__main__":
    # Simulation mode (default)
    reader = AdvancedNFCReader(use_simulation=True)
    
    # Simulate reading tags
    nfc_id_1 = reader.simulate_tag("NFC001")
    nfc_id_2 = reader.simulate_tag("NFC002")
    
    print(f"\nLast read: {reader.get_last_nfc_id()}")
    print(f"Read history: {reader.get_read_history()}")
    
    reader.close()
