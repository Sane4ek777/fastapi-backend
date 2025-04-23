import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Product from "./Product";
import styles from "./Product.module.scss";

const ProductList = ({ selectedCategory, searchQuery }) => {
  const [products, setProducts] = useState([]);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [sortOrder, setSortOrder] = useState("asc");
  const [error, setError] = useState(null);
  const navigate = useNavigate();

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

  const fetchProducts = async (initial = false) => {
    try {
      setIsLoading(true);
      const params = new URLSearchParams();

      if (selectedCategory.length > 0) {
        selectedCategory.forEach((id) => params.append("category_ids", id));
      }

      if (searchQuery) {
        params.append("search", searchQuery);
      }

      const limit = calculateVisibleCount();
      params.append("limit", limit);
      params.append("offset", initial ? 0 : offset);

      const url = `${process.env.REACT_APP_API_URL}/products?${params.toString()}`;
      const res = await fetch(url);
      const data = await res.json();

      if (initial) {
        setProducts(data);
        setOffset(limit);
      } else {
        setProducts((prev) => [...prev, ...data]);
        setOffset((prev) => prev + limit);
      }

      if (data.length < limit) {
        setHasMore(false);
      }
    } catch (err) {
      console.error("Ошибка загрузки товаров:", err);
      setError("Не удалось загрузить товары. Попробуйте позже.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchProducts(true);
  }, [selectedCategory, searchQuery]);

  useEffect(() => {
    const handleScroll = () => {
      if (
        window.innerHeight + window.scrollY >= document.body.offsetHeight - 100 &&
        !isLoading &&
        hasMore
      ) {
        fetchProducts();
      }
    };

    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, [isLoading, hasMore]);

  const handleSortChange = (e) => {
    setSortOrder(e.target.value);
  };

  const sortedProducts = [...products].sort((a, b) =>
    sortOrder === "asc" ? a.price - b.price : b.price - a.price
  );

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
        {sortedProducts.map((product) => (
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
