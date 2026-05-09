import React from 'react'
import { useParams } from 'react-router-dom';
import { useEffect } from 'react';
import { useState } from 'react';
import SlideProducts from '../../components/slideProducts/SlideProducts';
import ProductDetailsLoading from './ProductDetailsLoading';
import SlideProductLoading from '../../components/slideProducts/SlideProductLoading';
import ProductImages from './ProductImages';
import { Link } from 'react-router-dom';
import { useContext } from 'react';
import toast from 'react-hot-toast';
import ProductInfo from './ProductInfo';
import { CartContext } from '../../context/CartContext';
import PriceForecast from '../../components/PriceForecast';
import PageTransation from '../../components/PageTransation'
import { apiFetch } from '../../api';
import { PiSignInBold } from "react-icons/pi";

import { AuthContext } from '../../context/AuthContext';
import { useNavigate } from 'react-router-dom';

const ProductDetails = () => {
    const { id } = useParams();
    const [product, setProduct] = useState(null);
    const [loading, setLoading] = useState(true);
    const navigate = useNavigate();

    const { addToCart } = useContext(CartContext);
    const { isLoggedIn } = useContext(AuthContext);
    const [relatedProducts, setRelatedProducts] = useState([]);
    const [loadingRelatedProducts, setLoadingRelatedProducts] = useState(true);

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
        addToCart(product);
        toast.success(
            <div className='toast-wrapper'>
                <img src={product.images && product.images[0]} alt="" className='toast-img' />
                <div className="toast-content">
                    <strong>{product.title}</strong>
                    added to cart successfully!
                    <div>
                        <Link to='/cart' className='btn'>View Cart </Link>
                    </div>
                </div>
            </div>
            , {
                position: "top-right",
                duration: 5000,
            }
        )
    };
    useEffect(() => {
        const fetchProduct = async () => {
            try {
                const data = await apiFetch(`/api/products/${id}`);
                setProduct(data);
                setLoading(false);
            } catch (error) {
                console.log(error);
            }
        }


        fetchProduct();
    }, [id]);
    useEffect(() => {
        if (product && product.category) {
            apiFetch(`/api/products/category/${product.category}`)
                .then((data) => {
                setRelatedProducts(data.products);
            })
            .catch((error) => console.error(error))
            .finally(() => setLoadingRelatedProducts(false));
        }
    }, [product?.category]);
    if (!product) {
        return <div>Product not found</div>
    }
    return (
        <PageTransation key={id}>
            <div>
                {loading ? (
                    <ProductDetailsLoading />
                ) : (
                    <div className='py-[50px]'>
                        <div className='container mx-auto px-4 w-[90%] max-w-[1350px] flex flex-col md:flex-row justify-between items-center gap-[30px] md:gap-0'>
                            <ProductImages product={product} />
                            <ProductInfo product={product} handleAddToCart={handleAddToCart} />
                        </div>
                    </div>
                )}
                
                {/* <div className="mt-12">
                    <PriceForecast product={product} />
                </div> */}

                {loadingRelatedProducts ? (
                    <SlideProductLoading />
                ) : (
                    <SlideProducts key={product.category} title={product.category.replace(/-/g, " ").replace(/\b\w/g, c => c.toUpperCase())} data={relatedProducts} />
                )}

            </div>
        </PageTransation>
    )
}

export default ProductDetails