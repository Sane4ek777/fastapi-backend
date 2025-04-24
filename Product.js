import React, { useState, useEffect } from "react";
import { useInView } from "react-intersection-observer";
import Button from "../Button/Button";
import styles from "./Product.module.scss";

const Product = ({ name, price, description, available, images, onAddToCart }) => {
  const [hovered, setHovered] = useState(false);
  const [secondImageLoaded, setSecondImageLoaded] = useState(false);
  const { ref, inView } = useInView({ triggerOnce: true });

  // Безопасная проверка массива изображений
  const validImages = Array.isArray(images) ? images : [];

  const hasMultipleImages = validImages.length > 1;

  const BASE_IMAGE_URL = process.env.REACT_APP_API_URL || "";

  const buildImageUrl = (path) => {
    return `${BASE_IMAGE_URL.replace(/\/+$/, "")}/${(path || "").replace(/^\/+/, "")}`;
  };

  const firstImage = validImages.length > 0 ? buildImageUrl(validImages[0]) : "/placeholder.jpg";
  const secondImage = hasMultipleImages ? buildImageUrl(validImages[1]) : null;

  const roundedPrice = Math.ceil(price);

  useEffect(() => {
    if (inView && secondImage && !secondImageLoaded) {
      const img = new Image();
      img.src = secondImage;
      img.onload = () => setSecondImageLoaded(true);
    }
  }, [inView, secondImage, secondImageLoaded]);

  return (
    <div
      className={styles.product}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      ref={ref}
    >
      {inView && (
        <img
          src={hovered && hasMultipleImages && secondImageLoaded ? secondImage : firstImage}
          alt={name}
          className={styles["product-image"]}
          loading="lazy"
        />
      )}
      <div className={styles["product-details"]}>
        <h3 className={styles["product-name"]}>{name}</h3>
        <p className={styles["product-price"]}>Цена: {roundedPrice} ₽</p>
        <p className={styles["product-description"]}>{description}</p>
        {!available && <p className={styles["product-stock"]}>Нет в наличии</p>}
        <Button variant="primary" size="medium" onClick={onAddToCart} disabled={!available}>
          Добавить в корзину
        </Button>
      </div>
    </div>
  );
};

export default Product;
