from fastapi import FastAPI
from app.api.routes import podcast, scraping, store_topic

app = FastAPI(title="EchoPod API")

# Include API routes
# app.include_router(podcast.router, prefix="/podcast", tags=["Podcast"])
# app.include_router(scraping.router, prefix="/scraping", tags=["Scraping"])
app.include_router(store_topic.router, prefix="/api", tags=["Topics"])

@app.get("/")
async def root():
    return {"message": "Welcome to EchoPod API"}