from fastapi import FastAPI
from config import DB_FILE, XML_FILE, XLSX_FILE
from logger import logger
from models import Product
from fastapi.middleware.cors import CORSMiddleware
from api import router as api_router
from middleware import setup_middleware
from fastapi import Body
from typing import List
from api import router as products_router
from database import init_db, load_xml_to_db
from scraper import parse_diamir_xlsx, scrape_product_data, insert_scraped_product
from categories import router as categories_router
from fastapi import FastAPI
from api import router as api_router
from categories import router as categories_router


app = FastAPI()
setup_middleware(app)

@app.on_event("startup")
def startup_event():
    logger.info("Startup event triggered.")
    try:
        init_db()
        load_xml_to_db()

        # Запуск парсинга в XLSX
        parse_diamir_xlsx()  # Теперь эта функция обрабатывает ссылки и вызывает парсинг товаров внутри себя
        logger.info("XLSX parsing completed.")
    except Exception as e:
        logger.error(f"Error during XLSX parsing: {str(e)}")

@app.post("/scrape-product")
def scrape_product(url: str = Body(..., embed=True)):
    logger.info(f"Scraping product from URL: {url}")
    data = scrape_product_data(url)
    insert_scraped_product(data)
    return data

@app.post("/scrape-products")
def scrape_products(urls: List[str] = Body(...)):
    logger.info("Scraping multiple products...")
    return [scrape_product_data(url) for url in urls]

@app.post("/scrape-from-diamir-xlsx")
def scrape_from_diamir_xlsx():
    logger.info("Scraping products from Diamir XLSX...")
    try:
        parse_diamir_xlsx()  # Эта функция теперь вызывает парсинг внутри себя
        return {"message": "Successfully scraped products from Diamir XLSX"}
    except Exception as e:
        logger.error(f"Error scraping from Diamir XLSX: {str(e)}")
        return {"error": str(e)}

# Подключаем маршруты API
app.include_router(api_router)
logger.info("FastAPI server started.")
app.include_router(categories_router)
app.include_router(products_router)
