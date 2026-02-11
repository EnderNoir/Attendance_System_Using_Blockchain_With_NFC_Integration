import nfc
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NFCReader:
    """NFC Reader class for reading NFC tags"""
    
    def __init__(self):
        self.clf = None
        self.nfc_id = None
        self.initialize_reader()
    
    def initialize_reader(self):
        """Initialize NFC reader"""
        try:
            import nfc.clf
            self.clf = nfc.clf.ContactlessFrontend('usb')
            logger.info("NFC Reader initialized successfully")
        except Exception as e:
            logger.warning(f"NFC Reader not available or not connected: {e}")
            logger.info("Running in simulation mode")
    
    def read_nfc_tag(self):
        """Read NFC tag and return the ID"""
        if self.clf is None:
            logger.warning("NFC Reader not initialized")
            return None
        
        try:
            logger.info("Waiting for NFC tag...")
            target = self.clf.sense(nfc.clf.RemoteTarget, timeout=10)
            
            if target:
                nfc_id = target.sensf_res[1:].decode() if hasattr(target, 'sensf_res') else str(target)
                logger.info(f"NFC tag read: {nfc_id}")
                self.nfc_id = nfc_id
                return nfc_id
            else:
                logger.warning("No NFC tag detected")
                return None
        except Exception as e:
            logger.error(f"Error reading NFC tag: {e}")
            return None
    
    def simulate_nfc_read(self, nfc_id):
        """Simulate NFC tag reading (for testing without hardware)"""
        logger.info(f"Simulating NFC tag read: {nfc_id}")
        self.nfc_id = nfc_id
        return nfc_id
    
    def get_nfc_id(self):
        """Get the last read NFC ID"""
        return self.nfc_id
    
    def close(self):
        """Close the NFC reader"""
        if self.clf:
            self.clf.close()
            logger.info("NFC Reader closed")
