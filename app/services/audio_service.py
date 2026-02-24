import acoustid
import os
import tempfile
from pathlib import Path
import logging
from fastapi import UploadFile

logger = logging.getLogger(__name__)


class AudioService:
    
    # Supported audio formats
    SUPPORTED_FORMATS = {'.mp3', '.flac', '.ogg', '.m4a', '.wav', '.wma', '.aiff','.aac'}
    
    # Match score thresholds
    HIGH_CONFIDENCE = 0.8
    MEDIUM_CONFIDENCE = 0.5
    
    def __init__(self):
        self.api_key = os.getenv("ACOUSTID_API_KEY")
        if not self.api_key:
            logger.warning("ACOUSTID_API_KEY not set in environment variables")
        
        self.temp_dir = tempfile.gettempdir()
    
    def api_key_configured(self) -> bool:
        return bool(self.api_key)
    
    def is_valid_audio_format(self, filename: str) -> bool:
        file_ext = Path(filename).suffix.lower()
        return file_ext in self.SUPPORTED_FORMATS
    
    async def save_upload(self, file: UploadFile) -> str:
        try:
            # Create temp file with original extension
            file_ext = Path(file.filename).suffix
            temp_path = os.path.join(self.temp_dir, f"audio_{os.urandom(8).hex()}{file_ext}")
            
            # Save file
            with open(temp_path, "wb") as buffer:
                contents = await file.read()
                buffer.write(contents)
            
            logger.info(f"File saved to: {temp_path}")
            return temp_path
            
        except Exception as e:
            logger.error(f"Failed to save upload: {str(e)}")
            raise
    
    def identify_audio(self, file_path: str) -> dict:
        try:
            if not self.api_key:
                return {
                    "status": "error",
                    "error": "AcoustID API key not configured"
                }
            
            logger.info(f"Identifying audio: {file_path}")
            
            # Query AcoustID
            results =list(acoustid.match(self.api_key, file_path))
            print("RAW RESULTS:\n", results)       
            if not results:
                return {
                    "status": "not_found",
                    "message": "No match found in AcoustID database",
                    "file": Path(file_path).name
                }
            # Process results
            matches = []
            for score, recording_id, title, artist in results:
                confidence = self._get_confidence_level(score)
                matches.append({
                    "title": title,
                    "artist": artist,
                    "recording_id": recording_id,
                    "match_score": round(score, 2),
                    "confidence": confidence
                })
            valid_matches = [m for m in matches if m["title"] and m["artist"]]

            top_match = valid_matches[0] if valid_matches else (matches[0] if matches else None)
            return {
                "status": "found",
                "file": Path(file_path).name,
                "matches": matches,
                "top_match": top_match
            }
            
        except Exception as e:
            logger.error(f"Identification error: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "file": Path(file_path).name
            }
        
        finally:
            #  Only delete files created in system temp directory
            try:
                abs_file = os.path.abspath(file_path)
                abs_temp = os.path.abspath(self.temp_dir)

                if abs_file.startswith(abs_temp):
                    self._cleanup_file(file_path)
            except Exception as e:
                logger.error(f"Cleanup check failed: {e}")  
    
    def _get_confidence_level(self, score: float) -> str:
        if score >= self.HIGH_CONFIDENCE:
            return "high"
        elif score >= self.MEDIUM_CONFIDENCE:
            return "medium"
        else:
            return "low"
    
    def _cleanup_file(self, file_path: str) -> None:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Cleaned up temp file: {file_path}")
        except Exception as e:
            logger.error(f"Failed to cleanup file {file_path}: {str(e)}")