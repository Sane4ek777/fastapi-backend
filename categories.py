import sqlite3
from fastapi import APIRouter
from config import DB_FILE
from logger import logger

router = APIRouter()

@router.get("/categories")
def get_categories():
    """Возвращает категории товаров в виде иерархической структуры"""
    logger.info("Fetching product categories from the database...")

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Получаем количество товаров на каждую категорию
    cursor.execute("""
        SELECT category_id, COUNT(*) as count
        FROM products
        GROUP BY category_id
    """)
    product_counts_raw = cursor.fetchall()
    product_counts = {cat_id: count for cat_id, count in product_counts_raw}

    # Чтение всех категорий из базы данных
    cursor.execute("SELECT id, name, slug, parent_id FROM categories")
    rows = cursor.fetchall()

    categories = {}

    # Строим словарь categories с id в качестве ключа
    for row in rows:
        cat_id, name, slug, parent_id = row
        categories[cat_id] = {
            "id": cat_id,
            "name": name,
            "slug": slug,
            "parent_id": parent_id,
            "product_count": product_counts.get(cat_id, 0),  # 👈 добавили
            "subcategories": {}
        }

    # Создаем иерархическую структуру
    structured_categories = {}

    for cat_id, data in categories.items():
        parent_id = data["parent_id"]
        if parent_id is None:
            structured_categories[cat_id] = data  # Это корневой элемент
        else:
            if parent_id in categories:
                categories[parent_id]["subcategories"][cat_id] = data

    conn.close()
    logger.info(f"Fetched {len(structured_categories)} main categories with product counts.")
    return structured_categories



def move_subcategory():
    """Переносит подкатегорию 'Вибротрамбовки' из 'Вибротехника' в 'Строительное оборудование'"""
    logger.info("Moving subcategory 'Вибротрамбовки' to 'Строительное оборудование'...")

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    try:
        # Получаем ID подкатегории "Вибротрамбовки" по slug
        cursor.execute("SELECT id FROM categories WHERE slug = ?", ("Вибротрамбовки",))
        subcategory = cursor.fetchone()
        if not subcategory:
            logger.warning("Subcategory 'Вибротрамбовки' not found!")
            return

        subcategory_id = subcategory[0]

        # Получаем ID новой родительской категории "Строительное оборудование" по slug
        cursor.execute("SELECT id FROM categories WHERE slug = ?", ("Строительное оборудование",))
        new_parent = cursor.fetchone()
        if not new_parent:
            logger.warning("Category 'Строительное оборудование' not found!")
            return

        new_parent_id = new_parent[0]

        # Обновляем родительскую категорию у "Вибротрамбовки"
        cursor.execute("UPDATE categories SET parent_id = ? WHERE id = ?", (new_parent_id, subcategory_id))
        conn.commit()

        logger.info(f"Successfully moved 'Вибротрамбовки' under 'Строительное оборудование'.")

    except sqlite3.Error as e:
        logger.error(f"SQLite error while moving subcategory: {str(e)}")
    finally:
        conn.close()


@router.post("/move_subcategory")
def move_subcategory_endpoint():
    """Эндпоинт для переноса подкатегории"""
    move_subcategory()
    return {"message": "Подкатегория 'Вибротрамбовки' перенесена в 'Строительное оборудование'!"}
