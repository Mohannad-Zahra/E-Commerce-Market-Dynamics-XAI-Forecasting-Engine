import React, { createContext, useState, useEffect } from 'react';

export const FavoriteContext = createContext();

const FavoriteProvider = ({ children }) => {
    const [favoriteItems, setFavoriteItems] = useState(() => {
        const savedFavorites = localStorage.getItem('favoriteItems');
        return savedFavorites ? JSON.parse(savedFavorites) : [];
    });

    const toggleFavorite = (item) => {
        setFavoriteItems((prevItems) => {
            const isFavorite = prevItems.some((favItem) => favItem.id === item.id);
            if (isFavorite) {
                return prevItems.filter((favItem) => favItem.id !== item.id);
            }
            return [...prevItems, item];
        });
    };

    useEffect(() => {
        localStorage.setItem('favoriteItems', JSON.stringify(favoriteItems));
    }, [favoriteItems]);

    return (
        <FavoriteContext.Provider value={{ favoriteItems, toggleFavorite }}>
            {children}
        </FavoriteContext.Provider>
    );
};

export default FavoriteProvider;
