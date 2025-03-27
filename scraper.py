import sqlite3
import requests
import openpyxl
from bs4 import BeautifulSoup
from fastapi import HTTPException, Body
from config import DB_FILE, XLSX_FILE
from logger import logger
import xml.etree.ElementTree as ET  # 👈 Добавили ET
from config import DB_FILE, XML_FILE  # 👈 Добавили XML_FILE
import re
import unicodedata

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def generate_slug(name: str) -> str:
    """Генерирует slug из названия товара."""
    # Преобразуем строку в нижний регистр и оставляем кириллицу
    name = name.lower()  # Преобразуем в нижний регистр без удаления кириллицы

    # Убираем все символы, кроме букв, цифр, пробелов и дефисов
    name = re.sub(r'[^a-zA-Z0-9\-а-яА-ЯёЁ\s]', '', name)  # Оставляем кириллицу

    # Заменяем пробелы и нижние подчеркивания на дефисы
    name = re.sub(r'[\s_-]+', '-', name).strip()

    return name


def generate_unique_slug(name, cursor):
    """Генерирует уникальный slug, добавляя суффиксы при необходимости"""
    base_slug = generate_slug(name)
    slug = base_slug
    counter = 1

    cursor.execute("SELECT COUNT(*) FROM products WHERE slug = ?", (slug,))
    while cursor.fetchone()[0] > 0:  # Пока slug уже есть, добавляем суффикс
        slug = f"{base_slug}-{counter}"
        counter += 1
        cursor.execute("SELECT COUNT(*) FROM products WHERE slug = ?", (slug,))

    return slug

def get_price_from_xlsx(row_idx: int):
    """Получает цену, РРЦ и артикул по номеру строки в XLSX"""
    logger.info(f"Getting price info from XLSX for row {row_idx}")
    wb = openpyxl.load_workbook(XLSX_FILE)
    sheet = wb.active

    row = list(sheet.iter_rows(min_row=row_idx, max_row=row_idx))[0]
    price_cell = row[9]
    price_rrc_cell = row[10]
    article = row[1].value if len(row) >= 2 else None

    price = price_cell.value if price_cell else None
    price_rrc = price_rrc_cell.value if price_rrc_cell else None

    logger.info(f"Found price {price}, price_rrc {price_rrc}, article {article} at row {row_idx}")
    return price, price_rrc, article


def scrape_product_data(url: str, row_idx: int):
    """Собирает данные о товаре, включая категории"""
    try:
        logger.info(f"Scraping product data from URL: {url}, row: {row_idx}")
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            logger.error(f"Error {response.status_code} while requesting {url}")
            raise HTTPException(status_code=400, detail=f"Ошибка {response.status_code} при запросе {url}")

        soup = BeautifulSoup(response.text, 'html.parser')

        # Название товара
        title_tag = soup.find('h2', class_='h2 hidden-tablet hidden-mobile')
        title = title_tag.get_text(strip=True) if title_tag else 'Без названия'

        # Цена и РРЦ по номеру строки
        price, price_rrc, article = get_price_from_xlsx(row_idx)

        # Изображения
        image_urls = []
        image_gallery = soup.find('div', class_='BigImagerGallery')
        if image_gallery:
            for img_tag in image_gallery.find_all('img'):
                src = img_tag.get('src')
                if src:
                    full_image_url = "https://www.diamir.su" + src if not src.startswith("http") else src
                    image_urls.append(full_image_url)

        # Описание
        description_tag = soup.find('div', class_='cover-text')
        description = description_tag.get_text(separator=' ', strip=True) if description_tag else ''

        # Категории
        categories = extract_categories(soup)
        category_id = save_categories_to_db(categories)

        # Характеристики
        attributes = scrape_attributes(soup, article)

        logger.info(f"Scraped data: {title}, Categories: {categories}, Price: {price}, Attributes: {attributes}")

        return {
            'name': title,
            'description': description,
            'price': price,
            'price_rrc': price_rrc,
            'images': image_urls,
            'category_id': category_id,
            'attributes': attributes
        }
    except HTTPException as http_error:
        logger.error(f"HTTP error occurred: {str(http_error)}")
        raise http_error
    except Exception as e:
        logger.error(f"Error occurred while scraping data from {url}: {str(e)}")
        return None


def scrape_all_products(urls_with_rows):
    """
    Обрабатывает все товары из списка URL и номеров строк
    urls_with_rows - список кортежей (url, row_idx)
    """
    for url, row_idx in urls_with_rows:
        product_data = scrape_product_data(url, row_idx)
        if product_data:
            try:
                insert_scraped_product(product_data)
                logger.info(f"Successfully added product from URL: {url}")
            except Exception as e:
                logger.error(f"Error inserting product data from URL {url}: {str(e)}")
        else:
            logger.warning(f"Skipping product due to scraping error: {url}")


def scrape_attributes(soup, article: str):
    """Собирает характеристики товара с веб-страницы"""
    logger.info(f"Scraping attributes for article: {article}")
    attributes = []

    # Убедимся, что артикул всегда строковый
    article = str(article).strip().zfill(6)  # Преобразуем артикул в строку и добавляем ведущие нули

    table_section = soup.find('section', class_='info__table table js-table')
    if not table_section:
        logger.warning("Attributes table not found!")
        return attributes

    coll_blocks = table_section.find_all('div', class_='table__coll coll')

    article_position = None
    for block in coll_blocks:
        name_tag = block.find('div', class_='coll__name')
        if not name_tag:
            continue
        name_text = name_tag.get_text(strip=True)
        if "Артикул для заказа" in name_text:
            container = block.find('div', class_='coll__container')
            values = container.find_all('div')
            for idx, val_div in enumerate(values):
                val_text = val_div.get_text(strip=True)
                if val_text.zfill(6) == article:  # Сравниваем артикул с ведущими нулями
                    article_position = idx
                    logger.info(f"Found article {article} at position {article_position}")
                    break
            break

    if article_position is None:
        logger.warning(f"Article {article} not found in attributes table.")
        return attributes

    for block in coll_blocks:
        name_tag = block.find('div', class_='coll__name')
        if not name_tag:
            continue
        name_text = name_tag.get_text(strip=True)

        if "Артикул для заказа" in name_text:
            continue

        container = block.find('div', class_='coll__container')
        values = container.find_all('div')
        if len(values) > article_position:
            value_text = values[article_position].get_text(strip=True)
            attributes.append({'name': name_text, 'value': value_text})
            logger.info(f"Attribute parsed: {name_text} = {value_text}")

    return attributes

def generate_unique_product_id():
    """Генерирует уникальный ID для товара без префикса."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    try:
        while True:
            # Извлекаем максимальный ID для товаров
            cursor.execute("SELECT MAX(id) FROM products")
            max_id = cursor.fetchone()[0]
            
            if max_id is None:
                new_id = 1  # Начинаем с 1 без префикса
            else:
                new_id = max_id + 1  # Следующий ID

            # Проверяем, существует ли товар с таким ID
            cursor.execute("SELECT 1 FROM products WHERE id = ?", (new_id,))
            if cursor.fetchone() is None:
                # Если товар с таким ID не существует, возвращаем ID
                conn.close()
                logger.info(f"Generated new product ID: {new_id}")
                return new_id

    except sqlite3.Error as e:
        logger.error(f"SQLite error: {str(e)}")
        conn.close()
        raise

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        conn.close()
        raise

def insert_scraped_product(data):
    """Добавляет товар в БД с учетом категории"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    try:
        new_id = generate_unique_product_id()
        
        # Генерируем уникальный slug
        slug = generate_unique_slug(data['name'], cursor)

        cursor.execute(
            "INSERT INTO products (id, name, slug, price, price_rrc, description, image, category_id, available) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (new_id, data['name'], slug, data['price'], data['price_rrc'], data['description'], ",".join(data['images']), data['category_id'], True)
        )

        if data.get('attributes'):
            for attr in data['attributes']:
                cursor.execute(
                    "INSERT INTO product_attributes (product_id, attribute_name, attribute_value) VALUES (?, ?, ?)",
                    (new_id, attr['name'], attr['value'])
                )

        conn.commit()
        logger.info(f"Товар '{data['name']}' (slug: {slug}) с ID {new_id} успешно добавлен в базу данных.")
    except sqlite3.IntegrityError:
        logger.error(f"Ошибка: уникальный slug уже существует. Проблема с товаром '{data['name']}'")
    except sqlite3.Error as e:
        logger.error(f"Ошибка SQLite: {str(e)} при добавлении товара.")
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {str(e)} при добавлении товара.")
    finally:
        conn.close()


def extract_categories(soup):
    """Извлекает категории товара из хлебных крошек"""
    breadcrumb_section = soup.find('section', class_='section breadcrumbs')
    if not breadcrumb_section:
        logger.warning("Breadcrumbs not found!")
        return [], []

    # Извлекаем все ссылки в хлебных крошках
    breadcrumb_links = breadcrumb_section.find_all('a', class_='breadcrumbs__item')

    # Пропускаем "Главная" и "Каталог"
    if len(breadcrumb_links) < 4:
        logger.warning("Breadcrumbs structure is not as expected!")
        return breadcrumb_links[2:], []  # Используем только 3-ю позицию как категорию

    # 3-я позиция - категория
    category = breadcrumb_links[2].get_text(strip=True)

    # Если есть 4-й элемент, это подкатегория
    if len(breadcrumb_links) >= 5:
        subcategory = breadcrumb_links[3].get_text(strip=True)
    else:
        subcategory = None  # Подкатегория отсутствует

    return category, subcategory

def save_categories_to_db(categories):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Загружаем категории из XML для сравнения
    tree = ET.parse(XML_FILE)
    root = tree.getroot()
    xml_categories = {}

    for category in root.findall(".//category"):
        cat_id = int(category.get("id"))
        name = category.text.strip() if category.text else ""
        xml_categories[name] = cat_id  # Словарь {имя_категории: id}

    parent_id = None  # ID родительской категории

    for category in categories:
        category_slug = generate_slug(category)  # Генерируем slug для категории

        # Проверяем, есть ли уже такая категория в XML
        if category in xml_categories:
            category_id = xml_categories[category]
        else:
            # Проверяем, есть ли такая категория в БД
            cursor.execute("SELECT id FROM categories WHERE name = ?", (category,))
            result = cursor.fetchone()

            if result:
                category_id = result[0]
            else:
                # Проверяем уникальность slug
                cursor.execute("SELECT COUNT(*) FROM categories WHERE slug = ?", (category_slug,))
                if cursor.fetchone()[0] > 0:
                    base_slug = category_slug
                    counter = 1
                    while True:
                        new_slug = f"{base_slug}-{counter}"
                        cursor.execute("SELECT COUNT(*) FROM categories WHERE slug = ?", (new_slug,))
                        if cursor.fetchone()[0] == 0:
                            category_slug = new_slug
                            break
                        counter += 1

                # Вставляем новую категорию с уникальным slug
                try:
                    cursor.execute("INSERT INTO categories (name, slug, parent_id) VALUES (?, ?, ?)", 
                                   (category, category_slug, parent_id))
                    conn.commit()
                    category_id = cursor.lastrowid
                except sqlite3.IntegrityError:
                    logger.warning(f"Категория {category} уже существует в БД.")
                    cursor.execute("SELECT id FROM categories WHERE name = ?", (category,))
                    category_id = cursor.fetchone()[0]

        parent_id = category_id  # Обновляем parent_id для вложенной категории

    conn.close()
    return parent_id  # Возвращаем ID последней подкатегории

def is_url_valid(url: str) -> bool:
    """
    Проверяет, доступна ли страница по URL (код ответа не 404).
    """
    try:
        response = requests.head(url, allow_redirects=True, timeout=5)
        if response.status_code == 404:
            logger.warning(f"URL возвращает 404: {url}")
            return False
        logger.info(f"URL доступен: {url} (Status: {response.status_code})")
        return True
    except requests.RequestException as e:
        logger.error(f"Ошибка при проверке URL {url}: {str(e)}")
        return False

def parse_diamir_xlsx():
    """
    Извлекает ссылки на товары из XLSX-файла, проверяет их доступность и вызывает парсинг,
    передавая номер строки, в которой найдена гиперссылка
    """
    logger.info("Parsing Diamir XLSX file with hyperlink extraction and inline scraping...")
    wb = openpyxl.load_workbook(XLSX_FILE)
    sheet = wb.active
    found_any_links = False  # Флаг, который отслеживает, были ли найдены ссылки

    for row_idx, row in enumerate(sheet.iter_rows(min_row=2), start=2):
        for cell in row:
            if cell.value == "Ссылка на сайт" and cell.hyperlink:
                url = cell.hyperlink.target
                logger.info(f"Found hyperlink: {url} at row {row_idx}")
                found_any_links = True

                # Проверяем доступность URL перед парсингом
                if is_url_valid(url):
                    scrape_all_products([(url, row_idx)])
                else:
                    logger.warning(f"Пропуск недоступной ссылки: {url}")

    if not found_any_links:
        logger.warning("No links found in XLSX file.")

    logger.info("Finished parsing and scraping XLSX file.")