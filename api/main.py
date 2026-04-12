import os
from typing import Union
from fastapi import FastAPI, Depends, HTTPException, Security
from fastapi.security import APIKeyHeader
from src.extraction_normal import main as meli_main
from src.extraction_carroya import main as carroya_main
from src.extraction_usados_renting import main as usados_renting_main
from src.extraction_vendetunave import main as vendetunave_main
from pydantic import BaseModel, Field

API_KEY = os.environ.get("API_KEY", "change-me")

api_key_header = APIKeyHeader(name="X-API-Key")

def verify_api_key(key: str = Security(api_key_header)):
    if key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")

app = FastAPI(dependencies=[Depends(verify_api_key)])

class MeliProduct(BaseModel):
    product: str = Field("Producto a buscar", example="carros")
    pages: Union[int, str] = Field("Number of pages to scrape", example="all")
    items: Union[int, str] = Field("all", description="Number of items to scrape per run", example=2)

class CarroyaProduct(BaseModel):
    pages: Union[int, str] = Field("Number of pages to scrape", example="all")
    items: Union[int, str] = Field("all", description="Number of items to scrape per run", example=2)
    start_page: int = Field(1, description="Page number to start scraping from", example=1)

class UsadosRentingProduct(BaseModel):
    pages: Union[int, str] = Field("Number of pages to scrape", example="all")
    items: Union[int, str] = Field("all", description="Number of items to scrape per run", example=2)
    start_page: int = Field(1, description="Page number to start scraping from", example=1)

@app.post("/meli/product")
async def get_meli_data(product: MeliProduct):
    data = await meli_main(product=product.product,
                           pages=product.pages,
                           items=product.items)
    return data

@app.post("/carroya/vehiculos")
async def get_carroya_data(product: CarroyaProduct):
    data = await carroya_main(pages=product.pages,
                              items=product.items,
                              start_page=product.start_page)
    return data

@app.post("/usados-renting/vehiculos")
async def get_usados_renting_data(product: UsadosRentingProduct):
    data = await usados_renting_main(pages=product.pages,
                                     items=product.items,
                                     start_page=product.start_page)
    return data

class VendeTuNaveProduct(BaseModel):
    pages: Union[int, str] = Field("Number of pages to scrape", example="all")
    items: Union[int, str] = Field("all", description="Number of items to scrape per run", example=2)
    start_page: int = Field(1, description="Page number to start scraping from", example=1)

@app.post("/vendetunave/vehiculos")
async def get_vendetunave_data(product: VendeTuNaveProduct):
    data = await vendetunave_main(pages=product.pages,
                                  items=product.items,
                                  start_page=product.start_page)
    return data

# Keep old endpoint for backwards compatibility
@app.post("/product")
async def get_data(product: MeliProduct):
    data = await meli_main(product=product.product,
                           pages=product.pages,
                           items=product.items)
    return data

@app.get("/heart-beat")
async def service_health():
    return {"ok"}
