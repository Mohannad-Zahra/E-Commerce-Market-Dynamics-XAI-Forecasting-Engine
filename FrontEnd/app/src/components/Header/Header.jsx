import React, { useState, useEffect, useContext } from 'react'
import { Link, useLocation } from 'react-router-dom'
import logo from '../../assets/images/image.png'
import { FaRegHeart, FaEllipsisV } from "react-icons/fa";
import { TiShoppingCart } from "react-icons/ti";
import { IoMdMenu, IoMdClose } from "react-icons/io";
import { MdOutlineArrowDropDown } from "react-icons/md";
import { PiSignInBold } from "react-icons/pi";
import { FaUserPlus } from "react-icons/fa6";


import { CartContext } from '../../context/CartContext';
import { FavoriteContext } from '../../context/FavoriteContext';
import { AuthContext } from '../../context/AuthContext';
import SearchBox from './SearchBox';

const NavLinks = [
  {title: "Home" , link : "/"},
  { title: "About", link: "/about" },
  { title: "Accessories", link: "/category/accessories" },
  { title: "Blog", link: "/blog" },
  { title: "Contact", link: "/contact" },
]

const Header = () => {
    const {cartItems} = useContext(CartContext);
    const {favoriteItems} = useContext(FavoriteContext);
    const {isLoggedIn, logout, user} = useContext(AuthContext);
    const [isIconsOpen, setIsIconsOpen] = useState(false);

    const location = useLocation()
    const [categories, setCategories] = useState([]);
    const [isCategoryOpen, setIsCategoryOpen] = useState(false)
    const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false)

    useEffect(() => {
      setIsCategoryOpen(false)
      setIsMobileMenuOpen(false)
    },[location])

    useEffect(() => {
      fetch('/api/products/categories')
      .then((res) => res.json())
      .then((data) => setCategories(data))
    }, [])

    return (
        <header className="fixed top-0 left-0 right-0 z-[100] bg-white shadow-sm">
            <div className='w-full'>
                <div className='container mx-auto px-4 w-[90%] max-w-[1350px] flex items-center justify-between py-[15px] flex-wrap gap-x-[15px] gap-y-4'>
                    <Link className='flex justify-center items-center w-[70px] h-[70px] rounded-full border border-main overflow-hidden bg-white transition-all duration-300 hover:scale-105 hover:shadow-[0_4px_10px_rgba(0,144,240,0.3)]' to="/">
                        <img className="w-full" src={logo} alt="logo" />
                    </Link>

                    <SearchBox />
                    
                    <div className="flex items-center gap-[20px] lg:gap-[30px]">
                        <Link to="/favorites" className="relative cursor-pointer text-[26px] md:text-[30px] flex items-center justify-center text-heading hover:text-main transition-colors">
                            <FaRegHeart />
                            <span className='absolute -top-[5px] -right-[10px] bg-main text-white w-[20px] h-[20px] text-center leading-[20px] text-[11px] rounded-full'>
                                {favoriteItems?.length || 0}
                            </span>
                        </Link>
                        <div className="relative cursor-pointer text-[26px] md:text-[30px] flex items-center justify-center text-heading hover:text-main transition-colors">
                            <Link to="/cart" className="flex items-center justify-center text-heading hover:text-main transition-colors">
                                <TiShoppingCart />
                                <span className='absolute -top-[5px] -right-[10px] bg-main text-white w-[20px] h-[20px] text-center leading-[20px] text-[11px] rounded-full'>
                                    {cartItems.length}
                                </span>
                            </Link>
                        </div>
                    </div>
                </div>
            </div>

            <div className='bg-main relative'>
                <div className="container mx-auto px-4 w-[90%] max-w-[1350px] flex items-center justify-between">
                    <nav className="flex items-center justify-between h-[50px] w-full lg:w-auto flex-1">
                        <div className="w-1/2 lg:w-[220px] h-full relative" 
                             onMouseEnter={() => setIsCategoryOpen(true)} 
                             onMouseLeave={() => setIsCategoryOpen(false)}>
                            <div className="h-full w-full flex justify-between items-center bg-[#0079ca] lg:bg-main px-[15px] cursor-pointer text-white">
                                <div className="flex items-center gap-2">
                                    <IoMdMenu size={20} />
                                    <p className="block text-white text-[14px] lg:text-[15px] font-semibold">Categories</p>
                                </div>
                                <MdOutlineArrowDropDown size={24} />
                            </div>

                            <div className={`absolute top-full left-0 w-full md:w-[220px] bg-white border border-[#999] border-t-0 flex flex-col max-h-[60vh] overflow-y-auto transition-all duration-300 z-[105] origin-top shadow-lg ${isCategoryOpen ? 'scale-y-100 opacity-100' : 'scale-y-0 opacity-0'}`} >
                                {categories.map((category) => (
                                    <Link className="block p-[14px_10px] border-b border-border-custom last:border-b-0 text-[14px] hover:bg-gray-50 transition-colors capitalize" key={category} to={`/category/${category}`}>{category.replace(/-/g,' ')}</Link>
                                ))}
                            </div>
                        </div>

                        <button className="flex lg:hidden items-center justify-center gap-2 text-white cursor-pointer bg-transparent border-none px-[15px] w-1/2 h-full border-l border-white/20 hover:bg-white/10 transition-colors" onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}>
                            {isMobileMenuOpen ? <IoMdClose size={24} /> : <IoMdMenu size={24} />}
                            <span className="font-semibold text-[14px]">Menu</span>
                        </button>

                        <ul className={`lg:flex lg:flex-row lg:static lg:h-full lg:w-auto lg:bg-transparent lg:shadow-none lg:z-auto lg:ml-[180px] ${isMobileMenuOpen ? 'flex flex-col absolute top-full left-0 w-full bg-main z-[1001] h-max shadow-md' : 'hidden'}`}>
                            {NavLinks.map((item) => (
                                <li key={item.link} className="flex items-center justify-center lg:h-full relative group">
                                    <Link 
                                        className={`text-white font-bold text-[12px] uppercase tracking-[0.12em] px-[20px] h-full flex items-center transition-all duration-300 hover:text-white/80 ${location.pathname === item.link ? "opacity-100" : "opacity-70"}`} 
                                        to={item.link}
                                    >
                                        {item.title}
                                    </Link>
                                    {/* Premium Underline Indicator */}
                                    <div className={`absolute bottom-0 left-1/2 -translate-x-1/2 w-[30px] h-[3px] bg-white rounded-t-full transition-all duration-300 ${location.pathname === item.link ? "opacity-100 scale-x-100" : "opacity-0 scale-x-0 group-hover:opacity-40 group-hover:scale-x-75"}`}></div>
                                </li>
                            ))}
                        </ul>

                        {/* Distinct User Section */}
                        <div className="hidden lg:flex items-center gap-4 ml-auto border-l border-white/20 pl-6 h-[30px]">
                            {isLoggedIn ? (
                                <div className="flex items-center gap-3">
                                    <div className="w-8 h-8 rounded-full bg-white/10 flex items-center justify-center text-[12px] font-bold border border-white/20">
                                        {user?.name?.[0].toUpperCase() || 'U'}
                                    </div>
                                    <span className="text-white text-[13px] font-bold tracking-wide">Hi, {user?.name || 'User'}</span>
                                    <button onClick={logout} className="text-white/60 hover:text-white transition-colors cursor-pointer bg-transparent border-none p-1" title="Logout">
                                        <PiSignInBold size={18} className="rotate-180" />
                                    </button>
                                </div>
                            ) : (
                                <div className="flex items-center gap-5">
                                    <Link className="text-white text-[13px] font-bold tracking-wider hover:opacity-80 transition-opacity" to="/login">LOGIN</Link>
                                    <Link className="bg-white text-main text-[11px] font-extrabold tracking-widest px-5 py-2 rounded-full hover:bg-opacity-90 transition-all transform hover:scale-105" to="/signup">SIGN UP</Link>
                                </div>
                            )}
                        </div>
                    </nav>
                </div>
            </div>
        </header>
    )
}

export default Header
