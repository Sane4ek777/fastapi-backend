import React, { useEffect, useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import Product from "./Product";
import styles from "./Product.module.scss";

const ProductList = ({ selectedCategory, searchQuery }) => {
  const [allProducts, setAllProducts] = useState([]);
  const [visibleCount, setVisibleCount] = useState(0);
  const [sortOrder, setSortOrder] = useState("asc");
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  // Функция для расчета количества товаров на экране
  const calculateVisibleCount = () => {
    const screenWidth = window.innerWidth;
    const screenHeight = window.innerHeight;

    // Количество товаров в одном ряду в зависимости от ширины экрана
    const itemsPerRow = screenWidth <= 200 ? 1 :
    screenWidth <= 400 ? 2 :
    screenWidth <= 800 ? 3 :
    screenWidth <= 1600 ? 4 : 5;


    // Высота одного товара (примерно) + отступы
    const itemHeight = 300;

    // Количество рядов на экране
    const rowsPerPage = Math.ceil(screenHeight / itemHeight);

    // Общее количество видимых товаров
    return itemsPerRow * rowsPerPage;
  };

  // Обновляем количество видимых товаров при изменении размера окна
  useEffect(() => {
    const updateVisibleCount = () => setVisibleCount(calculateVisibleCount());
    updateVisibleCount();
    window.addEventListener("resize", updateVisibleCount);
    return () => window.removeEventListener("resize", updateVisibleCount);
  }, []);

  // Загрузка товаров
  useEffect(() => {
    const url = `${process.env.REACT_APP_API_URL}/products`;
    fetch(url)
      .then((res) => res.json())
      .then((data) => setAllProducts(data))
      .catch((err) => {
        console.error("Ошибка загрузки товаров:", err);
        setError("Не удалось загрузить товары. Попробуйте позже.");
      });
  }, []);

  // Фильтрация и сортировка товаров
  const filteredAndSortedProducts = useMemo(() => {
    const filteredProducts = selectedCategory.length > 0
      ? allProducts.filter((product) =>
          selectedCategory.includes(String(product.category_id))
        )
      : allProducts;

    if (!searchQuery) {
      return [...filteredProducts].sort((a, b) =>
        sortOrder === "asc" ? a.price - b.price : b.price - a.price
      );
    }

    return filteredProducts
      .filter((product) =>
        product.name.toLowerCase().includes(searchQuery.toLowerCase())
      )
      .sort((a, b) => (sortOrder === "asc" ? a.price - b.price : b.price - a.price));
  }, [allProducts, selectedCategory, searchQuery, sortOrder]);

  // Обработчик скролла для подгрузки товаров
  useEffect(() => {
    const handleScroll = () => {
      if (window.innerHeight + window.scrollY >= document.body.offsetHeight - 100) {
        setVisibleCount((prevCount) => prevCount + calculateVisibleCount());
      }
    };
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const handleSortChange = (e) => {
    setSortOrder(e.target.value);
  };

  const handleCardClick = (productSlug) => {
    navigate(`/product/${productSlug}`);
  };

  const handleAddToCart = (e, productName) => {
    e.stopPropagation();
    console.log(`Добавлен в корзину: ${productName}`);
  };

  return (
    <div>
      {error && <p className={styles.error}>{error}</p>}

      <div className={styles.sortContainer}>
        <label>Сортировать по цене:</label>
        <select value={sortOrder} onChange={handleSortChange}>
          <option value="asc">По возрастанию</option>
          <option value="desc">По убыванию</option>
        </select>
      </div>

      <div className={styles.productContainer}>
        {filteredAndSortedProducts.slice(0, visibleCount).map((product) => (
          <div
            key={product.slug}
            className={styles.productCard}
            onClick={() => handleCardClick(product.slug)}
          >
            <Product
              images={product.images}
              name={product.name}
              price={product.price}
              description={product.description}
              available={product.available}
              onAddToCart={(e) => handleAddToCart(e, product.name)}
            />
          </div>
        ))}
      </div>
    </div>
  );
};

export default ProductList;
