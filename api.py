from fastapi import APIRouter, HTTPException, Query
from database import database
from logger import logger
import os

router = APIRouter()

IMAGE_STORAGE_DIR = os.path.join(os.getcwd(), "optimized_images")
os.makedirs(IMAGE_STORAGE_DIR, exist_ok=True)

@router.get("/products")
async def get_products(
    category_ids: list[int] = Query(None),
    min_price: float = Query(0.0),
    max_price: float = Query(999999.0),
    search: str = Query("", alias="search"),
    limit: int = Query(20),
    offset: int = Query(0),
    sort_order: str = Query("asc")
):
    logger.info(f"Fetching products offset={offset}, limit={limit}, sort={sort_order}")

    if sort_order not in ("asc", "desc"):
        sort_order = "asc"

    # Запрос для подсчёта всех товаров, соответствующих фильтрам
    count_query = """
        SELECT COUNT(*) 
        FROM products
        WHERE (COALESCE(price_rrc, price * 1.3)) BETWEEN :min_price AND :max_price
    """
    values = {"min_price": min_price, "max_price": max_price}

    if category_ids:
        count_query += " AND category_id = ANY(:category_ids)"
        values["category_ids"] = category_ids

    if search:
        count_query += " AND LOWER(name) LIKE :search"
        values["search"] = f"%{search.lower()}%"

    # Получаем количество товаров, которые соответствуют фильтрам
    count_result = await database.fetch_one(count_query, values)
    total_items = count_result[0]

    # Запрос для получения товаров с пагинацией
    query = """
        SELECT id, name, slug, price, price_rrc, description, image, category_id, available
        FROM products
        WHERE (COALESCE(price_rrc, price * 1.3)) BETWEEN :min_price AND :max_price
    """
    if category_ids:
        query += " AND category_id = ANY(:category_ids)"
    if search:
        query += " AND LOWER(name) LIKE :search"

    query += f" ORDER BY COALESCE(price_rrc, price * 1.3) {sort_order.upper()} LIMIT :limit OFFSET :offset"
    values["limit"] = limit
    values["offset"] = offset

    products = await database.fetch_all(query=query, values=values)
    product_ids = [product["id"] for product in products]

    if not product_ids:
        return {"total_items": total_items, "products": []}

    attributes_data = await database.fetch_all(
        "SELECT product_id, attribute_name, attribute_value FROM product_attributes WHERE product_id = ANY(:ids)",
        {"ids": product_ids}
    )

    attr_map = {}
    for attr in attributes_data:
        attr_map.setdefault(attr["product_id"], []).append({
            "name": attr["attribute_name"],
            "value": attr["attribute_value"]
        })

    result = []
    for product in products:
        price_rrc = product["price_rrc"] if product["price_rrc"] is not None else product["price"] * 1.3
        result.append({
            "id": product["id"],
            "name": product["name"],
            "slug": product["slug"],
            "price": price_rrc,
            "description": product["description"],
            "images": product["image"].split(",") if product["image"] else [],
            "category_id": product["category_id"],
            "available": bool(product["available"]),
            "attributes": attr_map.get(product["id"], [])
        })

    return {"total_items": total_items, "products": result}

@router.get("/product/{slug}")
async def get_product(slug: str):
    """Получает один товар по его slug"""
    logger.info(f"Fetching product with slug: {slug}")
    product = await database.fetch_one(
        "SELECT id, name, slug, price, price_rrc, description, image, category_id, available FROM products WHERE slug = :slug",
        {"slug": slug}
    )

    if not product:
        logger.error(f"Product with slug {slug} not found.")
        raise HTTPException(status_code=404, detail="Product not found")

    attributes = await database.fetch_all(
        "SELECT attribute_name, attribute_value FROM product_attributes WHERE product_id = :id",
        {"id": product["id"]}
    )

    return {
        "id": product["id"],
        "name": product["name"],
        "slug": product["slug"],
        "price": product["price_rrc"] if product["price_rrc"] is not None else product["price"] * 1.3,
        "description": product["description"],
        "images": product["image"].split(",") if product["image"] else [],
        "category_id": product["category_id"],
        "available": bool(product["available"]),
        "attributes": [{"name": attr["attribute_name"], "value": attr["attribute_value"]} for attr in attributes]
    }

@router.post("/update-prices")
async def bulk_update_price_rrc():
    """Массовое обновление price_rrc на основе правила от цены"""
    logger.info("Starting bulk price_rrc update")

    products = await database.fetch_all(
        "SELECT id, price, price_rrc FROM products"
    )

    updates = []
    for product in products:
        price = product["price"]
        price_rrc = product["price_rrc"]

        if price_rrc is None or price_rrc < price * 1.3:
            if price < 100:
                new_rrc = price * 1.8
            elif price < 1000:
                new_rrc = price * 1.6
            elif price < 2000:
                new_rrc = price * 1.4
            else:
                new_rrc = price * 1.3

            updates.append({
                "id": product["id"],
                "price_rrc": round(new_rrc, 2)
            })

    if updates:
        await database.execute_many(
            "UPDATE products SET price_rrc = :price_rrc WHERE id = :id",
            updates
        )
        logger.info(f"Updated price_rrc for {len(updates)} products.")
    else:
        logger.info("No price_rrc updates needed.")

    return {"updated": len(updates)}