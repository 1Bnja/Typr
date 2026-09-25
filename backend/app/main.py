from fastapi import FastAPI, HTTPException
from database import supabase

app = FastAPI()

@app.get("/")
async def read_root():
    return {"message": "Welcome to the Typr API!"}