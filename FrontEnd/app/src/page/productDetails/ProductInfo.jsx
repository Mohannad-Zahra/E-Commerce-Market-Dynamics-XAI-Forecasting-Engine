import React from 'react'
import { FaCartArrowDown, FaRegHeart, FaHeart, FaRegStarHalfStroke, FaShare, FaStar, FaBolt, FaTag, FaShop, FaMicrochip, FaMemory } from 'react-icons/fa6';
import { CartContext } from './../../context/CartContext';
import { FavoriteContext } from './../../context/FavoriteContext';
import toast from 'react-hot-toast';
import { useContext } from 'react';
import { useNavigate } from 'react-router-dom';


const SpecBadge = ({ icon, label, value }) =>
  value ? (
    <span className="inline-flex items-center gap-[5px] bg-[#f3f4f6] text-[#374151] text-[12px] font-medium px-[10px] py-[5px] rounded-[6px]">
      {icon}
      <span className="text-[#6b7280]">{label}:</span> {value}
    </span>
  ) : null;

const ProductInfo = ({ product }) => {

    const { cartItems , addToCart } = useContext(CartContext);
    const { favoriteItems, toggleFavorite } = useContext(FavoriteContext);
    
    const isInCart = cartItems.some((cartItem) => cartItem.id === product.id);
    const isFavorite = favoriteItems.some((favItem) => favItem.id === product.id);
    
    const navigate = useNavigate();

    const handleAddToCart = () => {
        addToCart(product);
        toast.success(
            <div className='toast-wrapper'>
                <img src={product.images[0]} alt="" className='toast-img' />
                <div className="toast-content">
                    <strong>{product.title}</strong>
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
        );
    };

    const handleToggleFavorite = () => {
        toggleFavorite(product);
        if (!isFavorite) {
            toast.success(
                <div className='toast-wrapper'>
                    <img src={product.images[0]} alt="" className='toast-img' />
                    <div className="toast-content">
                        <strong>{product.title}</strong>
                        added to favorites!
                    </div>
                </div>
                , { duration: 3000, position: "bottom-right" }
            );
        } else {
             toast.error(
                <div className='toast-wrapper'>
                    <img src={product.images[0]} alt="" className='toast-img' />
                    <div className="toast-content">
                        <strong>{product.title}</strong>
                        removed from favorites.
                    </div>
                </div>
                , { duration: 3000, position: "bottom-right" }
            );
        }
    };

    const egpPrice   = Number(product.price).toLocaleString('en-EG', { maximumFractionDigits: 0 });
    const origPrice  = product.originalPrice
        ? Number(product.originalPrice).toLocaleString('en-EG', { maximumFractionDigits: 0 })
        : null;

    return (
        <div className="w-full md:w-[58%] pt-[10px] md:pt-0">
            <h2 className="mb-[20px] text-main text-2xl md:text-3xl font-bold leading-tight">{product.title}</h2>

            {/* Star rating */}
            <div className="my-[12px] flex gap-[5px] text-[#f8d941] text-[18px]">
                {Array.from({ length: Math.floor(product.rating) }, (_, i) => <FaStar key={i} />)}
                {product.rating % 1 !== 0 && <FaRegStarHalfStroke />}
                <span className="text-p text-[13px] ml-[5px] self-center">({product.rating})</span>
            </div>

            {/* Price row */}
            <div className="flex items-baseline gap-[12px] my-[18px]">
                <p className="text-[26px] font-bold text-main">
                    EGP {egpPrice}
                </p>
                {origPrice && origPrice !== egpPrice && (
                    <p className="text-[16px] text-[#9ca3af] line-through">EGP {origPrice}</p>
                )}
                {product.discountPercentage > 0 && (
                    <span className="bg-red-100 text-red-600 text-[12px] font-bold px-[8px] py-[3px] rounded-[5px]">
                        -{product.discountPercentage}%
                    </span>
                )}
            </div>

            {/* Volatility indicator */}
            {product.volatility_score > 0 && (
                <div className={`flex items-center gap-[8px] text-[13px] font-semibold mb-[15px] px-[12px] py-[8px] rounded-[8px] w-max ${
                    product.volatility_score > 40 ? 'bg-red-50 text-red-600 border border-red-200' :
                    product.volatility_score > 20 ? 'bg-orange-50 text-orange-600 border border-orange-200' :
                    'bg-green-50 text-green-600 border border-green-200'
                }`}>
                    <FaBolt />
                    Price Volatility: {product.volatility_score.toFixed(1)} / 100
                    <span className="font-normal text-[11px]">
                        ({product.volatility_score > 40 ? 'High — check often' : product.volatility_score > 20 ? 'Medium' : 'Stable'})
                    </span>
                </div>
            )}

            {/* Retailer & Brand */}
            <div className="flex flex-wrap gap-[8px] mb-[15px]">
                <SpecBadge icon={<FaShop />}    label="Retailer" value={product.retailer_id?.replace(/_/g, ' ')} />
                <SpecBadge icon={<FaTag />}      label="Brand"    value={product.brand} />
                <SpecBadge icon={<FaMicrochip />} label="CPU"     value={product.cpu_tier} />
                <SpecBadge icon={<FaMemory />}   label="RAM"      value={product.ram_gb ? `${product.ram_gb} GB` : null} />
                {product.storage_capacity_gb > 0 && (
                    <SpecBadge icon={null} label="Storage" value={`${product.storage_capacity_gb} GB`} />
                )}
                {product.gpu_tier && (
                    <SpecBadge icon={null} label="GPU" value={product.gpu_tier} />
                )}
            </div>

            {/* Description */}
            <p className='leading-relaxed text-[14px] text-p mb-[20px]'>{product.description}</p>

            {/* Stock */}
            <h5 className="font-medium mb-[20px] text-[14px] text-red-500">
                <span>⚡ Hurry Up! Only {product.stock} products left in stock.</span>
            </h5>

            {/* Add to Cart */}
            <button
                className={`text-[15px] rounded-[6px] py-[12px] px-[20px] border border-main transition-all duration-300 flex items-center gap-[10px] ${
                    isInCart
                        ? "bg-transparent text-main pointer-events-none"
                        : "bg-main text-white hover:bg-transparent hover:text-main"
                }`}
                onClick={handleAddToCart}
            >
                <FaCartArrowDown className="text-[18px]" />
                {isInCart ? "In Cart" : "Add to Cart"}
            </button>

            {/* Wish / Share */}
            <div className="flex gap-[10px] transition-all duration-300 my-[20px]">
                <span
                    className="w-[40px] h-[40px] bg-bg flex justify-center items-center rounded-full cursor-pointer transition-all duration-300 hover:bg-main group"
                    onClick={handleToggleFavorite}
                >
                    {isFavorite ? <FaHeart color="red" /> : <FaRegHeart className="group-hover:fill-white transition-colors" />}
                </span>
                <span className="w-[40px] h-[40px] bg-bg flex justify-center items-center rounded-full cursor-pointer transition-all duration-300 hover:bg-main group">
                    <FaShare className="group-hover:fill-white transition-colors" />
                </span>
            </div>

            {/* Product URL link */}
            {product.product_url && (
                <a
                    href={product.product_url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-[12px] text-main underline opacity-70 hover:opacity-100 break-all"
                >
                    View on retailer site ↗
                </a>
            )}
        </div>
    )
}

export default ProductInfo