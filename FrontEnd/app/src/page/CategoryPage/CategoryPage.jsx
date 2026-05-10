import React, { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import Product from '../../components/slideProducts/Product';
import SlideProductLoading from '../../components/slideProducts/SlideProductLoading';
import PageTransation from '../../components/PageTransation';
import { apiFetch } from '../../api';

const CategoryPage = () => {
    const { slug: category } = useParams();
    const [categoryProducts, setCategoryProducts] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    useEffect(() => {
        apiFetch(`/api/products/category/${category}`)
        .then((data) => {
            setCategoryProducts(data.products)
            setLoading(false)
        }).catch((error) => {
            setError(error.message);
            console.log(error)
            setLoading(false)
        })

        }, [category])
    return (
        <PageTransation>
        <div className="py-[60px] min-h-[calc(100vh-150px)] bg-[#f9fafb]">

            {loading ? <SlideProductLoading  key={category} /> :
             error ? <div className="container mx-auto px-4 w-[90%] max-w-[1350px]"><p className="text-red-500 text-center mt-[50px] font-bold text-xl">{error}</p></div> :
            <div className="container mx-auto px-4 w-[90%] max-w-[1350px]">
                <div className="mb-[30px] border-b border-gray-200 pb-[15px]">
                    <h2 className="text-[2rem] font-bold text-heading capitalize">{category.replace('-', ' ')}</h2>
                    <p className="text-p mt-[5px]">Explore our collection of {category.replace('-', ' ')}</p>
                </div>
                <div className="grid gap-[20px] grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 pb-[50px]">
                    {categoryProducts?.map((item, index) => (
                        <Product key={index} item={item} />
                    ))}
                </div>
            </div>
            }

            
        </div>
        </PageTransation>
    )
}

export default CategoryPage;