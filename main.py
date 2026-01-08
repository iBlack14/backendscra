"""
FastAPI Backend for Google Maps Scraper
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import asyncio
import os
from scraper import GoogleMapsScraper

import sys

# Fix for Windows Event Loop (Proactor vs Selector)
# This is required for Playwright to work correctly with Uvicorn on Windows
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

app = FastAPI(title="Google Maps Scraper API")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global scraper instance and state
scraper: Optional[GoogleMapsScraper] = None
scraper_task: Optional[asyncio.Task] = None
active_connections: list[WebSocket] = []


class ScraperConfig(BaseModel):
    rubro: str
    departamento: str
    pais: str = "Perú"
    cantidad: Optional[int] = None  # si es None o 0, se buscará sin límite práctico
    headless: bool = True
    expanded_search: bool = True


class ScraperResponse(BaseModel):
    status: str
    message: str


async def broadcast_progress(event_type: str, data: dict):
    """Broadcast progress to all connected WebSocket clients"""
    message = {"type": event_type, "data": data}
    for connection in active_connections:
        try:
            await connection.send_json(message)
        except:
            pass


@app.get("/")
async def root():
    return {"message": "Google Maps Scraper API", "status": "running"}


@app.post("/scraper/start", response_model=ScraperResponse)
async def start_scraper(config: ScraperConfig):
    """Start the scraping process"""
    global scraper, scraper_task
    
    if scraper and scraper.is_running:
        raise HTTPException(status_code=400, detail="Scraper is already running")
    
    # Create new scraper instance with progress callback
    scraper = GoogleMapsScraper(progress_callback=broadcast_progress)
    
    # Start scraping in background task
    async def run_scraper():
        try:
            await scraper.scrape(
                rubro=config.rubro,
                departamento=config.departamento,
                pais=config.pais,
                cantidad=config.cantidad,
                headless=config.headless,
                expanded_search=config.expanded_search
            )
        except Exception as e:
            await broadcast_progress("error", {"message": str(e)})
    
    scraper_task = asyncio.create_task(run_scraper())
    
    return ScraperResponse(
        status="started",
        message=f"Scraping iniciado para '{config.rubro}' en {config.departamento}"
    )


@app.post("/scraper/pause", response_model=ScraperResponse)
async def pause_scraper():
    """Pause the scraping process"""
    global scraper
    
    if not scraper or not scraper.is_running:
        raise HTTPException(status_code=400, detail="No active scraper to pause")
    
    scraper.pause()
    
    return ScraperResponse(
        status="paused",
        message="Scraping pausado"
    )


@app.post("/scraper/resume", response_model=ScraperResponse)
async def resume_scraper():
    """Resume the scraping process"""
    global scraper
    
    if not scraper or not scraper.is_running:
        raise HTTPException(status_code=400, detail="No active scraper to resume")
    
    scraper.resume()
    
    return ScraperResponse(
        status="resumed",
        message="Scraping reanudado"
    )


@app.post("/scraper/stop", response_model=ScraperResponse)
async def stop_scraper():
    """Stop the scraping process"""
    global scraper, scraper_task
    
    if not scraper:
        raise HTTPException(status_code=400, detail="No active scraper to stop")
    
    scraper.stop()
    
    if scraper_task:
        scraper_task.cancel()
        try:
            await scraper_task
        except asyncio.CancelledError:
            pass
    
    return ScraperResponse(
        status="stopped",
        message="Scraping detenido"
    )


@app.get("/scraper/status")
async def get_status():
    """Get current scraper status"""
    global scraper
    
    if not scraper:
        return {
            "is_running": False,
            "is_paused": False,
            "results_count": 0
        }
    
    return {
        "is_running": scraper.is_running,
        "is_paused": scraper.is_paused,
        "results_count": len(scraper.results)
    }


@app.get("/scraper/results")
async def get_results():
    """Get current scraping results"""
    global scraper
    
    if not scraper:
        return {"results": []}
    
    return {"results": scraper.results}


@app.post("/scraper/export")
async def export_results(config: ScraperConfig):
    """Export results to Excel and return file"""
    global scraper
    
    if not scraper or not scraper.results:
        raise HTTPException(status_code=400, detail="No results to export")
    
    try:
        filepath = scraper.export_to_excel(config.rubro, config.departamento)
        
        if not os.path.exists(filepath):
            raise HTTPException(status_code=500, detail="Failed to create Excel file")
        
        return FileResponse(
            path=filepath,
            filename=os.path.basename(filepath),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time progress updates"""
    await websocket.accept()
    active_connections.append(websocket)
    
    try:
        # Send initial status
        await websocket.send_json({
            "type": "connected",
            "data": {"message": "WebSocket conectado"}
        })
        
        # Keep connection alive
        while True:
            # Wait for messages from client (ping/pong)
            try:
                data = await websocket.receive_text()
            except WebSocketDisconnect:
                break
    except Exception:
        pass
    finally:
        if websocket in active_connections:
            active_connections.remove(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
