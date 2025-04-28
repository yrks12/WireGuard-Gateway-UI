import subprocess
import logging

logger = logging.getLogger(__name__)

class RebootService:
    @staticmethod
    def reboot():
        try:
            result = subprocess.run([
                'sudo', '/sbin/reboot'
            ], capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"Reboot failed: {result.stderr}")
                return False, result.stderr
            return True, None
        except Exception as e:
            logger.error(f"Exception during reboot: {e}")
            return False, str(e) 