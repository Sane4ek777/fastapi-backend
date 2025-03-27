import sqlite3
from fastapi import APIRouter, HTTPException, Query
from config import DB_FILE
from logger import logger

router = APIRouter()

@router.get("/products")
def get_products(category_id: int = Query(None), min_price: float = Query(0.0), max_price: float = Query(999999.0)):
    """Получает список товаров с фильтрацией по категории и диапазону цен"""
    logger.info(f"Fetching products with category_id={category_id}, price range=({min_price}, {max_price})")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    query = """
        SELECT id, name, slug, price, price_rrc, description, image, category_id, available
        FROM products
        WHERE (COALESCE(price_rrc, price * 1.3)) BETWEEN ? AND ?
    """
    params = [min_price, max_price]

    if category_id is not None:
        query += " AND category_id = ?"
        params.append(category_id)

    cursor.execute(query, params)
    products = cursor.fetchall()

    result = []
    for p in products:
        product_id, name, slug, price, price_rrc, description, images, category_id, available = p

        # Коррекция `price_rrc`, если оно не задано или меньше допустимого значения
        if price_rrc is None or price_rrc < price * 1.3:
            if price < 100:
                price_rrc = price * 1.8
            elif price < 1000:
                price_rrc = price * 1.6
            elif price < 2000:
                price_rrc = price * 1.4
            else:
                price_rrc = price * 1.3

            # Обновляем `price_rrc` в БД
            cursor.execute("UPDATE products SET price_rrc = ? WHERE id = ?", (price_rrc, product_id))
            conn.commit()

        # Получаем характеристики товара
        cursor.execute("SELECT attribute_name, attribute_value FROM product_attributes WHERE product_id = ?", (product_id,))
        attributes = cursor.fetchall()

        result.append({
            "id": product_id,
            "name": name,
            "slug": slug,  # Добавляем `slug` в выдачу
            "price": price_rrc,  # Используем скорректированное `price_rrc`
            "description": description,
            "images": images.split(",") if images else [],
            "category_id": category_id,
            "available": bool(available),
            "attributes": [{"name": attr[0], "value": attr[1]} for attr in attributes]
        })

    conn.close()
    logger.info(f"Fetched {len(result)} products with corrected price_rrc.")
    return result

@router.get("/product/{slug}")
def get_product(slug: str):
    """Получает один товар по его slug"""
    logger.info(f"Fetching product with slug: {slug}")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, name, slug, price, price_rrc, description, image, category_id, available FROM products WHERE slug = ?", (slug,))
    product = cursor.fetchone()

    if not product:
        logger.error(f"Product with slug {slug} not found.")
        raise HTTPException(status_code=404, detail="Product not found")

    cursor.execute("SELECT attribute_name, attribute_value FROM product_attributes WHERE product_id = ?", (product[0],))
    attributes = cursor.fetchall()

    conn.close()

    return {
        "id": product[0],
        "name": product[1],
        "slug": product[2],  # Возвращаем `slug`
        "price": product[4] if product[4] is not None else product[3] * 1.3,
        "description": product[5],
        "images": product[6].split(",") if product[6] else [],
        "category_id": product[7],
        "available": bool(product[8]),
        "attributes": [{"name": attr[0], "value": attr[1]} for attr in attributes]
    }
