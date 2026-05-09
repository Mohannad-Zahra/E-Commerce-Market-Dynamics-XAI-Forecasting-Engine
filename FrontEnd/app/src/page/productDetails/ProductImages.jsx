
import Product from './../../components/slideProducts/Product';
import { FaCartArrowDown } from "react-icons/fa";
import { useState } from 'react';

const ProductImages = ({ product }) => {
    const [selectedImg, setSelectedImg] = useState(product.images && product.images[0]);

    if (!product.images || product.images.length === 0) return null;

    return (
        <div className="w-full md:w-[40%]">
            <div className="flex items-center justify-center mb-[20px] bg-white rounded-xl p-4 border border-slate-200 shadow-sm overflow-hidden min-h-[300px]">
                <img 
                    className="max-h-[400px] w-auto transition-all duration-300 transform hover:scale-105" 
                    src={selectedImg || product.images[0]} 
                    alt={product.title} 
                />
            </div>
            <div className="flex flex-wrap gap-3 cursor-pointer" >
                {product.images.map((img, index) => (
                    <div 
                        key={index}
                        onClick={() => setSelectedImg(img)}
                        className={`p-2 rounded-lg border-2 transition-all duration-200 ${
                            (selectedImg === img || (!selectedImg && index === 0)) 
                            ? 'border-indigo-500 bg-indigo-50' 
                            : 'border-slate-200 bg-white hover:border-slate-300 shadow-sm'
                        }`}
                    >
                        <img 
                            className="w-16 h-16 object-contain" 
                            src={img} 
                            alt={`${product.title} ${index + 1}`} 
                        />
                    </div>
                ))}
            </div>
        </div>
    )
}

export default ProductImages;