import React, { useContext } from 'react';
import { Link } from 'react-router-dom';
import { FavoriteContext } from '../context/FavoriteContext';
import { CartContext } from '../context/CartContext';
import { AuthContext } from '../context/AuthContext';
import { TiShoppingCart } from "react-icons/ti";
import { IoMdClose } from "react-icons/io";
import { PiSignInBold } from "react-icons/pi";
import { useNavigate } from 'react-router-dom';
import { toast } from 'react-hot-toast';
import PageTransation from '../components/PageTransation';

const Favorites = () => {
    const { favoriteItems, toggleFavorite } = useContext(FavoriteContext);
    const { addToCart } = useContext(CartContext);
    const { isLoggedIn } = useContext(AuthContext);

    const navigate = useNavigate();

    const handleAddToCart = (product) => {
        if (!isLoggedIn) {
            toast.error(
                <div className="toast-wrapper">
                    <div className="w-10 h-10 bg-main/20 rounded-full flex items-center justify-center text-main">
                        <PiSignInBold size={20} />
                    </div>
                    <div className="toast-content">
                        <span className="font-bold">Authentication Required</span>
                        <span className="text-[12px] opacity-80">Login to start building your cart</span>
                        <button 
                          onClick={() => { toast.dismiss(); navigate('/login'); }}
                          className="bg-main text-white text-[11px] font-bold px-3 py-1.5 rounded-lg mt-1 w-max hover:bg-main/80 transition-all"
                        >
                          Sign In Now
                        </button>
                    </div>
                </div>,
                {
                    duration: 4000,
                    position: "top-right",
                    className: 'premium-alert'
                }
            );
            return;
        }
        addToCart(product);
        toast.success(`${product.name} added to cart!`);
    };

    return (
        <PageTransation>
            <div className="container mx-auto px-4 w-[90%] max-w-[1350px] py-20 min-h-[60vh]">
                <h1 className="text-4xl font-bold text-heading mb-10">My Wishlist</h1>
                
                {favoriteItems.length === 0 ? (
                    <div className="text-center py-20 bg-white rounded-3xl border border-black/5 shadow-sm">
                        <div className="text-6xl mb-6">❤️</div>
                        <h2 className="text-2xl font-bold text-heading mb-4">Your wishlist is empty</h2>
                        <p className="text-p mb-10">Save items you love here to find them easily later.</p>
                        <Link to="/" className="btn mx-auto">Start Shopping</Link>
                    </div>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
                        {favoriteItems.map((product) => (
                            <div key={product.id} className="bg-white rounded-3xl p-6 border border-black/5 shadow-sm group relative hover:shadow-xl transition-all duration-300">
                                <button 
                                    onClick={() => toggleFavorite(product)}
                                    className="absolute top-4 right-4 w-10 h-10 bg-red-50 text-red-500 rounded-full flex items-center justify-center hover:bg-red-500 hover:text-white transition-all z-10"
                                    title="Remove from favorites"
                                >
                                    <IoMdClose size={20} />
                                </button>
                                
                                <Link to={`/product/${product.id}`} className="block aspect-square rounded-2xl overflow-hidden mb-6 bg-gray-50">
                                    <img 
                                        src={product.image || product.thumbnail} 
                                        alt={product.name} 
                                        className="w-full h-full object-contain mix-blend-multiply group-hover:scale-110 transition-transform duration-500" 
                                    />
                                </Link>
                                
                                <div className="space-y-3">
                                    <div className="flex justify-between items-start gap-2">
                                        <h3 className="font-bold text-heading line-clamp-2 hover:text-main transition-colors text-[15px]">
                                            <Link to={`/product/${product.id}`}>{product.name}</Link>
                                        </h3>
                                        <span className="bg-main/10 text-main text-[10px] font-bold px-2 py-1 rounded-full uppercase shrink-0">
                                            {product.category}
                                        </span>
                                    </div>
                                    
                                    <div className="flex items-baseline gap-2">
                                        <span className="text-xl font-black text-main">${product.price}</span>
                                    </div>
                                    
                                    <button 
                                        onClick={() => handleAddToCart(product)}
                                        className="w-full btn !rounded-[14px] !w-full justify-center mt-4"
                                    >
                                        <TiShoppingCart size={20} />
                                        Add to Cart
                                    </button>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </PageTransation>
    );
};

export default Favorites;
