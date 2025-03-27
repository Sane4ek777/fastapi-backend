import sqlite3
import xml.etree.ElementTree as ET
import re
from config import DB_FILE, XML_FILE
from logger import logger
import unicodedata
from transliterate import translit

def generate_slug(name, existing_slugs=None, id_suffix=None, cursor=None):
    """Создает уникальный slug из названия товара, включая бренд, модель и ключевые слова, с транслитерацией кириллицы в латиницу."""
    if not name:
        return None  # Если название пустое, возвращаем None

    # Приводим к нижнему регистру, но оставляем кириллицу
    name = name.lower()  # Преобразуем в нижний регистр

    # Транслитерируем кириллицу в латиницу
    name = translit(name, 'ru', reversed=True)  # 'ru' - для русского языка, reversed=True для кириллицы в латиницу

    # Разделяем название на части (например, бренд, модель)
    name_parts = re.split(r'[\s\-]+', name)  # Разделяем по пробелам и дефисам

    # Заменяем "eurolux" на "eurolux-ll" только один раз
    name_parts = [
        part.replace("eurolux", "eurolux-ll", 1) if "eurolux" in part and "eurolux-ll" not in part else part
        for part in name_parts
    ]

    # Убираем все символы, которые не являются буквами, цифрами или дефисами
    name_parts = [re.sub(r'[^a-zA-Z0-9\-]', '', part) for part in name_parts]  # Убираем все лишние символы

    # Убираем пустые части
    name_parts = [part for part in name_parts if part]

    # Если пустое название после обработки, установим дефолтное значение
    if not name_parts:
        name_parts = [f"product-{id_suffix}" if id_suffix else "product"]

    # Собираем slug из частей, соединяя их дефисами
    slug = '-'.join(name_parts)

    # Проверяем уникальность slug
    original_slug = slug
    counter = 1

    # Проверяем в переданном множестве (если оно есть)
    if existing_slugs is not None:
        while slug in existing_slugs:
            slug = f"{original_slug}-{counter}"
            counter += 1
        existing_slugs.add(slug)

    # Проверяем в базе данных (если передан cursor)
    elif cursor is not None:
        cursor.execute("SELECT COUNT(*) FROM products WHERE slug = ?", (slug,))
        while cursor.fetchone()[0] > 0:
            slug = f"{original_slug}-{counter}"
            counter += 1
            cursor.execute("SELECT COUNT(*) FROM products WHERE slug = ?", (slug,))

    logger.info(f"Generated slug: {slug}")  # Логируем сгенерированный slug
    return slug


def init_db():
    """Создает таблицы в базе данных, если их нет"""
    logger.info("Initializing the database...")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS products (
                      id INTEGER PRIMARY KEY,
                      name TEXT,
                      slug TEXT UNIQUE,
                      price REAL,
                      price_rrc REAL,
                      description TEXT,
                      image TEXT,
                      category_id INTEGER,
                      available BOOLEAN)''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS product_attributes (
                      id INTEGER PRIMARY KEY AUTOINCREMENT,
                      product_id INTEGER,
                      attribute_name TEXT,
                      attribute_value TEXT,
                      FOREIGN KEY(product_id) REFERENCES products(id))''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS categories (
                      id INTEGER PRIMARY KEY AUTOINCREMENT,
                      name TEXT UNIQUE,
                      slug TEXT UNIQUE,
                      parent_id INTEGER,
                      FOREIGN KEY(parent_id) REFERENCES categories(id))''')

    conn.commit()
    conn.close()
    logger.info("Database initialized successfully.")

def load_xml_to_db():
    """Загружает данные о товарах и категориях из XML-файла в базу данных"""
    logger.info("Loading data from XML to database...")

    tree = ET.parse(XML_FILE)
    root = tree.getroot()

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Очищаем таблицы перед загрузкой новых данных
    cursor.execute("DELETE FROM products")
    cursor.execute("DELETE FROM categories")
    cursor.execute("DELETE FROM product_attributes")

    category_map = {}
    existing_slugs = set()

    # Загрузка категорий
    for category in root.findall(".//category"):
        cat_id = int(category.get("id"))
        name = category.text.strip() if category.text else ""
        
        # Генерируем slug для категории, передавая список существующих и ID
        slug = generate_slug(name, existing_slugs, id_suffix=cat_id, cursor=cursor)

        parent_id = category.get("parentId")
        parent_id = int(parent_id) if parent_id is not None else None

        cursor.execute("SELECT id FROM categories WHERE name = ?", (name,))
        existing_category = cursor.fetchone()

        if existing_category:
            category_map[cat_id] = existing_category[0]
            logger.warning(f"Category '{name}' already exists in the database.")
        else:
            cursor.execute("INSERT INTO categories (id, name, slug, parent_id) VALUES (?, ?, ?, ?)",
                           (cat_id, name, slug, parent_id))
            conn.commit()
            category_map[cat_id] = cat_id

    # Загрузка товаров
    for item in root.findall(".//offer"):
        product_id = int(item.get("id", 0))
        name = item.findtext("name", "").strip()
        
        # Генерируем slug для товара
        slug = generate_slug(name, existing_slugs, id_suffix=product_id, cursor=cursor)

        price = float(item.findtext("price", 0.0))
        price_rrc_text = item.findtext("price_rrc", "")
        price_rrc = float(price_rrc_text) if price_rrc_text else None
        description = item.findtext("description", "")

        pictures = item.findall("picture")
        images = [pic.text for pic in pictures if pic.text]
        images_str = ",".join(images)

        category_id = int(item.findtext("categoryId", 0))
        category_id = category_map.get(category_id, None)

        available = item.get("available", "false").lower() == "true"

        cursor.execute("INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                       (product_id, name, slug, price, price_rrc, description, images_str, category_id, available))

    conn.commit()
    conn.close()
    logger.info("Data from XML loaded into database.")
