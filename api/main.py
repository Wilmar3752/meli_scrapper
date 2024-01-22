from fastapi import FastAPI
from src.extraction import main
from pydantic import BaseModel, Field

app = FastAPI()

class Product(BaseModel):
    product: str = Field("Producto a buscar", example = "carros")
    pages: int = Field('Paginas a buscar', example= 2)

@app.post("/product")
async def get_data(product: Product):
    print(product)
    data = await main(product.product, product.pages)
    return data

@app.get("/heart-beat")
async def service_health():
    return {"ok"}
