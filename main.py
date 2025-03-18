from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3
import xml.etree.ElementTree as ET
from fastapi.responses import FileResponse

app = FastAPI()
DB_FILE = "store.db"
XML_FILE = "products.xml"

# Разрешаем CORS
app.add_middleware(
    CORSMiddleware,
     allow_origins=["https://instrumentdar.ru"],  # Разрешаем запросы с фронта
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Product(BaseModel):
    id: int
    name: str
    price: float
    description: str
    image: str
    category_id: int  # Добавили поле category_id
    available: bool  # Добавили поле available

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS products (
                      id INTEGER PRIMARY KEY,
                      name TEXT,
                      price REAL,
                      price_rrc REAL,
                      description TEXT,
                      image TEXT,
                      category_id INTEGER,
                      available BOOLEAN)''')  # Добавили поле price_rrc
    conn.commit()
    conn.close()

def load_xml_to_db():
    tree = ET.parse(XML_FILE)
    root = tree.getroot()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM products")  # Очистка перед загрузкой
    
    for item in root.findall(".//offer"):
        product_id = int(item.get("id", 0))
        name = item.findtext("name", "")
        price = float(item.findtext("price", 0.0))
        price_rrc_text = item.findtext("price_rrc", "")
        price_rrc = float(price_rrc_text) if price_rrc_text else None
        description = item.findtext("description", "")
        
        # Сбор всех картинок товара
        pictures = item.findall("picture")
        images = [pic.text for pic in pictures if pic.text]
        images_str = ",".join(images)  # сохраняем как строку через запятую
        
        category_id = int(item.findtext("categoryId", 0))  # Извлекаем ID категории
        available = item.get("available", "false").lower() == "true"  # Проверяем наличие товара
        
        cursor.execute("INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                       (product_id, name, price, price_rrc, description, images_str, category_id, available))
    
    conn.commit()
    conn.close()

@app.on_event("startup")
def startup_event():
    init_db()
    load_xml_to_db()

@app.get("/products")
def get_products(category_id: int = Query(None), min_price: float = Query(0.0), max_price: float = Query(999999.0)):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    query = "SELECT id, name, price, price_rrc, description, image, category_id, available FROM products WHERE (COALESCE(price_rrc, price * 1.3)) BETWEEN ? AND ?"
    params = [min_price, max_price]
    
    if category_id is not None:
        query += " AND category_id = ?"
        params.append(category_id)
    
    cursor.execute(query, params)
    products = cursor.fetchall()
    conn.close()

    return [{
        "id": p[0],
        "name": p[1],
        "price": p[3] if p[3] is not None else p[2] * 1.3,
        "description": p[4],
        "images": p[5].split(",") if p[5] else [],
        "category_id": p[6],
        "available": bool(p[7])
    } for p in products]

@app.get("/product/{product_id}")
def get_product(product_id: int):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, price, price_rrc, description, image, category_id, available FROM products WHERE id = ?", (product_id,))
    product = cursor.fetchone()
    conn.close()

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    return {
        "id": product[0],
        "name": product[1],
        "price": product[3] if product[3] is not None else product[2] * 1.3,
        "description": product[4],
        "images": product[5].split(",") if product[5] else [],
        "category_id": product[6],
        "available": bool(product[7])
    }

@app.get("/download-db")
def download_db():
    return FileResponse(DB_FILE, filename="store.db", media_type="application/octet-stream")

@app.get("/categories")
def get_categories():
    tree = ET.parse(XML_FILE)
    root = tree.getroot()
    categories = {}

    # Сбор данных о категориях
    for category in root.findall(".//category"):
        cat_id = category.get("id")
        parent_id = category.get("parentId")
        name = category.text.strip() if category.text else ""

        categories[cat_id] = {
            "name": name,
            "parent_id": parent_id,
            "subcategories": {}
        }

    # Рекурсивная функция для добавления субкатегорий
    def add_subcategories(parent_id, cat_id):
        category_data = categories[cat_id]

        # Если категория имеет родителя, добавляем её в subcategories
        if parent_id in categories:
            parent_data = categories[parent_id]
            parent_data["subcategories"][cat_id] = {
                "name": category_data["name"],
                "subcategories": {}
            }

            # Проверяем, есть ли субкатегории 2 уровня
            for subcat_id, subcategory in categories.items():
                if subcategory["parent_id"] == cat_id:
                    add_subcategories(cat_id, subcat_id)

    # Стартуем с корневых категорий
    structured_categories = {}

    for cat_id, data in categories.items():
        parent_id = data["parent_id"]

        if parent_id:
            # Если категория имеет родителя, добавляем её как подкатегорию к родителю
            add_subcategories(parent_id, cat_id)
        else:
            # Если родителя нет, значит это корневая категория
            structured_categories[cat_id] = data

    # Второй проход: проверяем подкатегории первого уровня, чтобы добавить субкатегории 2 уровня
    for cat_id, category_data in structured_categories.items():
        subcategories = category_data["subcategories"]
        
        # Для каждой подкатегории 1 уровня добавляем её субкатегории 2 уровня
        for subcat_id, subcategory_data in subcategories.items():
            for subcat2_id, subcategory2_data in categories.items():
                if subcategory2_data["parent_id"] == subcat_id:
                    subcategory_data["subcategories"][subcat2_id] = {
                        "name": subcategory2_data["name"],
                        "subcategories": {}
                    }

    # Убираем пустые категории, которые не имеют подкатегорий
    structured_categories = {k: v for k, v in structured_categories.items() if v["subcategories"]}

    return structured_categories
