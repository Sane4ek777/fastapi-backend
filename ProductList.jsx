import React, { useState, useEffect } from "react";
import styles from "./ProductList.module.css"; // при необходимости подключите CSS-модуль
import Product from "./Product"; // компонент отображения одного товара

const ProductList = ({ selectedCategory, searchQuery }) => {
  const [products, setProducts] = useState([]);
  const [offset, setOffset] = useState(0);
  const [limit] = useState(20);
  const [sortOrder, setSortOrder] = useState("asc");
  const [hasMore, setHasMore] = useState(true);
  const [loading, setLoading] = useState(false);

  const fetchProducts = async () => {
    if (loading || !hasMore) return;
    setLoading(true);

    const params = new URLSearchParams();
    selectedCategory.forEach((id) => params.append("category_ids", id));
    if (searchQuery) params.append("search", searchQuery);
    params.append("sort_order", sortOrder);
    params.append("sort_by", "price");
    params.append("limit", limit);
    params.append("offset", offset);

    try {
      const res = await fetch(`${process.env.REACT_APP_API_URL}/products?${params}`);
      const data = await res.json();

      setProducts((prev) => [...prev, ...data]);
      setOffset((prev) => prev + limit);
      setHasMore(data.length === limit);
    } catch (error) {
      console.error("Ошибка загрузки продуктов:", error);
    } finally {
      setLoading(false);
    }
  };

  // сброс при смене фильтров
  useEffect(() => {
    setProducts([]);
    setOffset(0);
    setHasMore(true);
  }, [selectedCategory, searchQuery, sortOrder]);

  // загрузка новых продуктов при изменении offset
  useEffect(() => {
    fetchProducts();
  }, [offset]);

  // бесконечная прокрутка
  useEffect(() => {
    const handleScroll = () => {
      if (
        window.innerHeight + window.scrollY >= document.body.offsetHeight - 100 &&
        hasMore &&
        !loading
      ) {
        fetchProducts();
      }
    };
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, [hasMore, loading]);

  return (
    <div>
      <div className={styles.sortContainer}>
        <label>Сортировка: </label>
        <select value={sortOrder} onChange={(e) => setSortOrder(e.target.value)}>
          <option value="asc">По возрастанию цены</option>
          <option value="desc">По убыванию цены</option>
        </select>
      </div>

      <div className={styles.productContainer}>
        {products.map((p) => (
          <div key={p.slug} className={styles.productCard}>
            <Product {...p} />
          </div>
        ))}
      </div>

      {loading && <p>Загрузка...</p>}
      {!hasMore && !loading && <p>Больше товаров нет.</p>}
    </div>
  );
};

export default ProductList;
