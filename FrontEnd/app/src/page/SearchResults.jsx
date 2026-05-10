import React, { useEffect, useState } from 'react'
import { useLocation } from 'react-router-dom';
import PageTransation from './../components/PageTransation';
import SlideProductLoading from './../components/slideProducts/SlideProductLoading';
import Product from './../components/slideProducts/Product';
import { apiFetch } from '../api';

const SearchResults = () => {
    const query = new URLSearchParams(useLocation().search).get('q');
    const [loading, setLoading] = useState(true);
    const [results, setResults] = useState([]);
    console.log(results);
    useEffect(() => {
        const fetchResults = async () => {
            try {
                const data = await apiFetch(`/api/products/search?q=${query}`);
                setResults(data.products || []);
            } catch (error) {
                console.error('Error fetching search results:', error);
            }
            finally {
                setLoading(false);
            }
        }
        if (query && query.trim() !== "") {
            fetchResults();
        } else {
            setLoading(false);
            setResults([]);
        }
    }, [query]);




    return (
        <PageTransation heading={`Search Results for "${query}"`}>

            <div className="py-[60px] min-h-[calc(100vh-150px)] bg-[#f9fafb]">
                {loading ? <SlideProductLoading key={query} /> :
                    results.length > 0 ? (
                        <div className="container mx-auto px-4 w-[90%] max-w-[1350px]">
                            <div className="mb-[30px] border-b border-gray-200 pb-[15px]">
                                <h2 className="text-[2rem] font-bold text-heading">Search Results for "{query}"</h2>
                            </div>
                            <div className="grid gap-[20px] grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 pb-[50px]">
                                {results.map((item, index) => (
                                    <Product key={index} item={item} />
                                ))}
                            </div>
                        </div>
                    ) : (
                        <div className="container mx-auto px-4 w-[90%] max-w-[1350px]">
                            <p className="text-center text-p text-[1.2rem] mt-[50px]">No results found for "{query}".</p>
                        </div>
                    )
                }
            </div>



        </PageTransation>
    )
}

export default SearchResults