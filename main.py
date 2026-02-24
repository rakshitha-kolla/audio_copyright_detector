from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import logging
from app.services.audio_service import AudioService
import os
from dotenv import load_dotenv
load_dotenv()
import json
from pathlib import Path
from fastapi.middleware.cors import CORSMiddleware

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Audio Copyright Detector",
    description="Detect copyrighted music using Chromaprint + AcoustID",
    version="1.0.0"
)

# Add CORS middleware for web interface
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize service
audio_service = AudioService()

INPUT_PATH = "app/data/inputs/"
OUTPUT_PATH = "app/data/outputs/"
os.makedirs(OUTPUT_PATH, exist_ok=True)

# Serve static files (web interface)
# Create static folder if it doesn't exist
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.on_event("startup")
async def startup():
    """Initialize services on startup"""
    logger.info("Audio Copyright Detector API started")

    try:
        filename = "test16.wav"
        file_path = os.path.join(INPUT_PATH, filename)

        if os.path.isfile(file_path):
            logger.info(f"Auto testing file: {file_path}")
            result = audio_service.identify_audio(file_path)

            #  SAVE JSON (missing currently)
            output_file = os.path.join(
                OUTPUT_PATH,
                f"{Path(filename).stem}_copyright.json"
            )

            with open(output_file, "w") as f:
                json.dump(result, f, indent=2)

            logger.info(f"Startup result saved to: {output_file}")

            print("\n Startup test result:")
            print(result)
        else:
            logger.warning(f"Test file not found: {file_path}")

    except Exception as e:
        logger.error(f"Startup test failed: {e}")

@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown"""
    logger.info("Audio Copyright Detector API shutting down")


@app.get("/")
async def root():
    """Root endpoint - serve web interface"""
    try:
        # Try to serve index.html from current directory
        if os.path.exists("index.html"):
            return FileResponse("index.html")
        else:
            return {
                "status": "running",
                "service": "Audio Copyright Detector",
                "version": "1.0.0",
                "message": "Web interface not found. Place index.html in project root."
            }
    except:
        return {
            "status": "running",
            "service": "Audio Copyright Detector",
            "version": "1.0.0"
        }

@app.post("/detect/{filename}")
async def detect_copyright(filename: str):
    try:
        file_path = os.path.join(INPUT_PATH, filename)

        #  check file exists
        if not os.path.isfile(file_path):
            raise HTTPException(
                status_code=404,
                detail=f"File not found: {filename}"
            )

        #  validate format
        if not audio_service.is_valid_audio_format(filename):
            raise HTTPException(
                status_code=400,
                detail="Invalid audio format"
            )

        logger.info(f"Processing file: {file_path}")

        #  run detection
        result = audio_service.identify_audio(file_path)

        #  save JSON output
        output_file = os.path.join(
            OUTPUT_PATH,
            f"{Path(filename).stem}_copyright.json"
        )

        with open(output_file, "w") as f:
            json.dump(result, f, indent=2)

        logger.info(f"Saved result to: {output_file}")

        # optional: include path in response
        result["saved_to"] = output_file

        return result

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Detection error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/detect-upload")
async def detect_upload(file: UploadFile = File(...)):
    """Upload file and detect copyright"""
    try:
        # Validate format
        if not audio_service.is_valid_audio_format(file.filename):
            raise HTTPException(
                status_code=400,
                detail="Invalid audio format. Supported: mp3, wav, flac, ogg, m4a, aac, aiff, wma"
            )
        
        # Save uploaded file temporarily
        file_path = await audio_service.save_upload(file)
        
        # Run detection
        result = audio_service.identify_audio(file_path)
        
        # Save result to output folder
        output_file = os.path.join(
            OUTPUT_PATH,
            f"{Path(file.filename).stem}_copyright.json"
        )
        
        with open(output_file, "w") as f:
            json.dump(result, f, indent=2)
        
        result["saved_to"] = output_file
        logger.info(f"Upload detection saved to: {output_file}")
        
        return result
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Upload detection error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Detection failed: {str(e)}"
        )
        
@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "api_key_configured": audio_service.api_key_configured(),
        "service": "Audio Copyright Detector",
        "version": "1.0.0"
    }

@app.get("/api/files")
async def list_input_files():
    """List audio files in input folder"""
    try:
        files = []
        if os.path.exists(INPUT_PATH):
            for file in os.listdir(INPUT_PATH):
                if audio_service.is_valid_audio_format(file):
                    file_path = os.path.join(INPUT_PATH, file)
                    files.append({
                        "name": file,
                        "size": os.path.getsize(file_path),
                        "path": file_path
                    })
        return {"files": files, "count": len(files)}
    except Exception as e:
        logger.error(f"Error listing files: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/results")
async def list_results():
    """List generated results"""
    try:
        results = []
        if os.path.exists(OUTPUT_PATH):
            for file in os.listdir(OUTPUT_PATH):
                if file.endswith('.json'):
                    result_path = os.path.join(OUTPUT_PATH, file)
                    with open(result_path, 'r') as f:
                        result_data = json.load(f)
                        results.append({
                            "filename": file,
                            "status": result_data.get("status"),
                            "file": result_data.get("file"),
                            "title": result_data.get("top_match", {}).get("title") if result_data.get("status") == "found" else None
                        })
        return {"results": results, "count": len(results)}
    except Exception as e:
        logger.error(f"Error listing results: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)