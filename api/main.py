from fastapi import FastAPI
from src.extraction import main

app = FastAPI()

@app.get("/{product}")
async def get_data(product):
    data = await main(product)
    return data
