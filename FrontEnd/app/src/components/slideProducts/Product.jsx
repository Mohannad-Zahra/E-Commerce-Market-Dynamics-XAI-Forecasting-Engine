import React from 'react'
import { FaStar, FaRegStarHalfStroke, FaBolt } from "react-icons/fa6";
import { FaCartArrowDown, FaRegHeart, FaHeart, FaShare } from "react-icons/fa";
import { Link , useNavigate} from 'react-router-dom';
import { useContext } from 'react';
import { CartContext } from '../../context/CartContext';
import { FavoriteContext } from '../../context/FavoriteContext';
import { AuthContext } from '../../context/AuthContext';
import { PiSignInBold } from "react-icons/pi";
import toast from 'react-hot-toast';

const Product = ({item}) => {
  const navigate = useNavigate();
  const {cartItems , addToCart} = useContext(CartContext);
  const {favoriteItems, toggleFavorite} = useContext(FavoriteContext);
  const {isLoggedIn} = useContext(AuthContext);
  
  const isInCart = cartItems.some((cartItem) => cartItem.id === item.id);
  const isFavorite = favoriteItems.some((favItem) => favItem.id === item.id);

   const handleAddToCart = () => {
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
          addToCart(item);
          toast.success(
              <div className='toast-wrapper'>
                  <img src={item.images[0]} alt="" className='toast-img' />
                  <div className="toast-content">
                      <strong>{item.title}</strong>
                      added to cart successfully!
                      <div>
                          <button className='btn' onClick={() => navigate('/cart')}>View Cart</button>
                      </div>
                  </div>
              </div>
              , {
                  duration: 3000,
                  position: "bottom-right",
  
              }
          )
  
  
      };

    const handleToggleFavorite = () => {
        toggleFavorite(item);
        if (!isFavorite) {
            toast.success(
                <div className='toast-wrapper'>
                    <img src={item.thumbnail} alt="" className='toast-img' />
                    <div className="toast-content">
                        <strong>{item.title}</strong>
                        added to favorites!
                    </div>
                </div>
                , { duration: 3000, position: "bottom-right" }
            );
        } else {
             toast.error(
                <div className='toast-wrapper'>
                    <img src={item.thumbnail} alt="" className='toast-img' />
                    <div className="toast-content">
                        <strong>{item.title}</strong>
                        removed from favorites.
                    </div>
                </div>
                , { duration: 3000, position: "bottom-right" }
            );
        }
    };
  return (
    <div className={`group border border-border-custom p-[10px] rounded-[8px] transition-all duration-300 cursor-pointer relative bg-white hover:shadow-md ${isInCart ? "border-main" : ""}`}>
     <Link to={`/product/${item.id}`}>
     <div className={`absolute -top-[5px] right-[5px] bg-main text-white px-[10px] py-[5px] rounded-[5px] text-[13px] flex items-center gap-[5px] z-10 transition-opacity duration-300 ${isInCart ? "opacity-100" : "opacity-0"}`}>
      <FaCartArrowDown />
      <span>in cart</span>
     </div>
      <div className="h-[180px] overflow-hidden flex items-center justify-center mb-[10px] relative">
        <img loading="lazy" className="h-full w-auto object-contain transition-transform duration-300 group-hover:scale-110" src={item.thumbnail} alt={item.title} />
      </div>
      <p className='text-[15px] font-semibold mb-[5px] text-heading line-clamp-2'>{item.title}</p>
      
      <div className="flex gap-[5px] mb-[10px] text-yellow-400">
        <FaStar />
        <FaStar />
        <FaStar />
        <FaStar />
        <FaRegStarHalfStroke />
      </div>
      {/* Volatility badge */}
      {item.volatility_score > 20 && (
        <span className="inline-flex items-center gap-[4px] text-[11px] font-semibold text-orange-500 bg-orange-50 border border-orange-200 rounded-full px-[8px] py-[2px] mb-[8px]">
          <FaBolt className="text-[10px]" /> {item.volatility_score?.toFixed(0)} vol
        </span>
      )}
      <p className='text-[16px] font-semibold text-main mb-[15px]'>EGP {Number(item.price).toLocaleString('en-EG', { maximumFractionDigits: 0 })}</p>
     </Link>
      <div className="flex items-center justify-between gap-[10px] opacity-0 translate-y-[20px] transition-all duration-300 group-hover:opacity-100 group-hover:translate-y-0">
        <span className='flex-1 h-[35px] flex items-center justify-center rounded-[5px] bg-heading text-white cursor-pointer transition-colors duration-300 hover:bg-main gap-[10px] after:content-["Add_To_Cart"] after:text-[14px]' onClick={handleAddToCart} ><FaCartArrowDown /></span>
        <span className='w-[35px] h-[35px] flex items-center justify-center rounded-[5px] bg-bg text-heading cursor-pointer transition-colors duration-300 hover:bg-main hover:text-white' onClick={handleToggleFavorite}>{isFavorite ? <FaHeart color="red" /> : <FaRegHeart />}</span>
        <span className='w-[35px] h-[35px] flex items-center justify-center rounded-[5px] bg-bg text-heading cursor-pointer transition-colors duration-300 hover:bg-main hover:text-white'><FaShare /></span>
      </div>

    </div>
  )
}

export default Product