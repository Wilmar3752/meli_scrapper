import os
from typing import Union
from fastapi import FastAPI, Depends, HTTPException, Security
from fastapi.security import APIKeyHeader
from src.extraction_normal import main
from pydantic import BaseModel, Field

API_KEY = os.environ.get("API_KEY", "change-me")

api_key_header = APIKeyHeader(name="X-API-Key")

def verify_api_key(key: str = Security(api_key_header)):
    if key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")

app = FastAPI(dependencies=[Depends(verify_api_key)])

class Product(BaseModel):
    product: str = Field("Producto a buscar", example = "carros")
    pages: Union[int, str] = Field("Number of pages to scrape", example = "all")
    items: Union[int, str] = Field("all", description="Number of items to scrape per run", example = 2)

@app.post("/product")
async def get_data(product: Product):
    data = await main(product=product.product,
                            pages=product.pages,
                            items=product.items)
    return data

@app.get("/heart-beat")
async def service_health():
    return {"ok"}
