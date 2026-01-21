from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
import traceback

from starlette.concurrency import run_in_threadpool

app = FastAPI()


class CreateMapRequest(BaseModel):
    city: str = Field(..., description="City name, e.g. 'Paris'")
    country: str = Field(..., description="Country name, e.g. 'France'")
    theme: Optional[str] = Field("feature_based", description="Theme name (must exist in themes/)")
    distance: Optional[int] = Field(29000, description="Map radius in meters")
    format: Optional[str] = Field("png", description="Output format: png, svg or pdf")


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.post("/create-map")
async def create_map(req: CreateMapRequest):
    """Generate a map poster and return the created file path.

    This endpoint mirrors the CLI in `create_map_poster.py`.
    It will load the requested theme, geocode the city, generate the poster
    (running the blocking work in a threadpool) and return the output path.
    """
    # Lazy import the poster module so the FastAPI app can be imported even if
    # heavy optional dependencies (osmnx, geopandas, etc.) are not installed.
    try:
        import create_map_poster as poster
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to import poster module: {e}")

    # Validate theme
    available = poster.get_available_themes()
    if req.theme not in available:
        raise HTTPException(status_code=400, detail=f"Theme '{req.theme}' not found. Available: {', '.join(available)}")

    try:
        # Load theme into the poster module global
        poster.THEME = poster.load_theme(req.theme)

        # Resolve coordinates (may use cache)
        point = poster.get_coordinates(req.city, req.country)

        # Create output filename
        out_path = poster.generate_output_filename(req.city, req.theme, req.format)

        # Run the blocking poster generation in a threadpool so we don't block the event loop
        await run_in_threadpool(poster.create_poster, req.city, req.country, point, req.distance, out_path, req.format)

        return {"output_file": out_path}

    except Exception as e:
        tb = traceback.format_exc()
        raise HTTPException(status_code=500, detail={"error": str(e), "traceback": tb})
