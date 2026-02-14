from typing import Union
from fastapi import FastAPI
from src.extraction_normal import main
from pydantic import BaseModel, Field

app = FastAPI()

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
