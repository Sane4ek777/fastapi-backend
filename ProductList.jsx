import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Product from "./Product";
import styles from "./Product.module.scss";

const ProductList = ({ selectedCategory, searchQuery }) => {
  const [allProducts, setAllProducts] = useState([]);
  const [visibleCount, setVisibleCount] = useState(0);
  const [sortOrder, setSortOrder] = useState("asc");
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  // Вычисляем, сколько товаров влезает на экран
  const calculateVisibleCount = () => {
    const screenWidth = window.innerWidth;
    const screenHeight = window.innerHeight;
    const itemsPerRow =
      screenWidth <= 200 ? 1 :
      screenWidth <= 400 ? 2 :
      screenWidth <= 800 ? 3 :
      screenWidth <= 1600 ? 4 : 5;
    const itemHeight = 300;
    const rowsPerPage = Math.ceil(screenHeight / itemHeight);
    return itemsPerRow * rowsPerPage;
  };

  // Загружаем первую порцию товаров
  useEffect(() => {
    const loadInitialProducts = async () => {
      const count = calculateVisibleCount();
      setVisibleCount(count);
      await fetchProducts(0, count, true);
    };

    loadInitialProducts();
  }, [selectedCategory, searchQuery, sortOrder]);

  // Подгрузка товаров с бэкенда
  const fetchProducts = async (offset, limit, isInitial = false) => {
    try {
      const params = new URLSearchParams();

      if (selectedCategory.length > 0) {
        selectedCategory.forEach((id) => params.append("category_ids", id));
      }

      if (searchQuery) {
        params.append("search", searchQuery);
      }

      params.append("sort_order", sortOrder);
      params.append("limit", limit);
      params.append("offset", offset);

      const url = `${process.env.REACT_APP_API_URL}/products?${params.toString()}`;
      const res = await fetch(url);
      const data = await res.json();

      if (isInitial) {
        setAllProducts(data);
      } else {
        setAllProducts((prev) => [...prev, ...data]);
      }
    } catch (err) {
      console.error("Ошибка загрузки товаров:", err);
      setError("Не удалось загрузить товары. Попробуйте позже.");
    }
  };

  // Скролл: загружаем новые товары
  useEffect(() => {
    const handleScroll = () => {
      if (window.innerHeight + window.scrollY >= document.body.offsetHeight - 100) {
        const nextOffset = allProducts.length;
        fetchProducts(nextOffset, visibleCount);
      }
    };

    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, [allProducts, visibleCount, selectedCategory, searchQuery, sortOrder]);

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
        {allProducts.map((product) => (
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
