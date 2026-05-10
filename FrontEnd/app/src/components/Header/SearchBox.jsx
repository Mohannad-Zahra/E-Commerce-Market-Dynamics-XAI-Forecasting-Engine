import React from 'react'
import { useState, useEffect } from 'react';
//// 
import { FaSearch } from 'react-icons/fa';
import { useNavigate, useLocation } from 'react-router-dom';



const SearchBox = () => {


    const [searchTerm, setSearchTerm] = useState("");
    const [suggestions, setSuggestions] = useState([]);
    const [showDropdown, setShowDropdown] = useState(false);


    const navigate = useNavigate();
    const location = useLocation();

    const handelSubmit = (e) => {
        e.preventDefault();
        if (searchTerm.trim()) {
            setShowDropdown(false);
            navigate(`/search?q=${encodeURIComponent(searchTerm)}`);
        }
    }


    useEffect(() => {
        const fetchSuggestions = async () => {
            if (searchTerm.trim() === "") {
                setSuggestions([]);
                return;
            }
            try {
                // Adjust the search API URL depending on your actual backend
                const res = await fetch(`http://localhost:8000/api/products/search?q=${encodeURIComponent(searchTerm)}&limit=5`);
                const data = await res.json();
                setSuggestions(data.products || []);
            } catch (error) {
                console.error("Error fetching suggestions:", error);
            }
        };

        const debounceTimer = setTimeout(() => {
            if (searchTerm.trim() !== "") {
                fetchSuggestions();
                if (location.pathname === '/search') {
                    navigate(`/search?q=${encodeURIComponent(searchTerm)}`, { replace: true });
                }
            } else {
                setSuggestions([]);
                if (location.pathname === '/search') {
                    navigate(`/search?q=`, { replace: true });
                }
            }
        }, 300);
        return () => clearTimeout(debounceTimer);
    }, [searchTerm, location.pathname, navigate]);




    return (
        <div className='w-full order-3 mt-2.5 md:w-[40%] md:order-none md:mt-0 relative'>
            <form onSubmit={handelSubmit} className='flex items-center w-full bg-[#f3f4f6] rounded-[30px] overflow-hidden px-[20px] py-[10px] md:py-[12px] border border-transparent focus-within:border-main focus-within:bg-white transition-all duration-300'>
                <input type="text" name='search' id='search' placeholder='Search For Products' aria-label='Search For Products' value={searchTerm} autoComplete='off' 
                    className='w-full bg-transparent border-none outline-none text-[#333] text-[14px] md:text-[16px]'
                    onChange={(e) => {
                        setSearchTerm(e.target.value);
                        setShowDropdown(true);
                    }} 
                    onFocus={() => setShowDropdown(true)}
                    onBlur={() => setTimeout(() => setShowDropdown(false), 200)}
                />
                <button type='submit' className='text-[#666] text-[18px] ml-[10px] cursor-pointer hover:text-main transition-colors'>
                    <FaSearch />
                </button>
            </form>
            {showDropdown && suggestions.length > 0 && (
                <ul className="absolute top-full left-0 w-full bg-white shadow-md rounded z-[1000] max-h-[300px] overflow-y-auto mt-1">
                    {suggestions.map((product) => (
                        <li key={product.id}
                            className="p-2.5 cursor-pointer border-b border-[#eee] last:border-b-0 flex items-center gap-2.5 hover:bg-[#f9f9f9]"
                            onClick={() => {
                                setSearchTerm(product.title);
                                setShowDropdown(false);
                                navigate(`/search?q=${encodeURIComponent(product.title)}`);
                            }}>
                            <img className="w-[40px] h-[40px] object-cover rounded" src={product.thumbnail} alt={product.title} />
                            <div>
                                <h4 className="m-0 text-[14px] text-[#333]">{product.title}</h4>
                                <span className="text-[12px] text-[#666]">${product.price}</span>
                            </div>
                        </li>
                    ))}
                </ul>
            )}
        </div>
    )
}

export default SearchBox