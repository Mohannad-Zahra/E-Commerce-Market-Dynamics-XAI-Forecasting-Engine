import React from 'react'
import { useContext } from 'react';
import { CartContext } from '../../context/CartContext';
import { FaTrashAlt } from "react-icons/fa";
import { Link } from 'react-router-dom';
import PageTransation from '../../components/PageTransation'



const Cart = () => {

    const { cartItems, increaseQuantity, decreaseQuantity, removeFromCart } = useContext(CartContext)
    const total = cartItems.reduce((acc, item) => acc + item.price * item.quantity, 0)
    return (
        <PageTransation>
            <div className='my-[50px]'>
                <div className="w-[95%] md:w-[45%] px-[20px] border border-border-custom shadow-[0_8px_10px_#c0bfbf44] rounded-[5px] mx-auto">
                    <h1 className="border-b border-border-custom py-[20px] mb-[20px] text-main text-2xl font-bold">Order Summary</h1>

                    <div className="h-[350px] overflow-y-auto">
                        {cartItems.length === 0 ? (
                            <p>Your Cart is empty.</p>
                        ) : (
                            cartItems.map((item, index) => (
                                <div className="flex gap-[20px] items-center justify-between h-auto md:h-[125px] border-b border-border-custom py-[15px] md:py-0 md:pr-[20px] last:border-0" key={index}>
                                    <div className="flex items-center gap-[20px]">
                                        <div className="w-[100px] flex justify-center items-center">
                                            <img className="w-auto h-[80px]" src={item.images[0]} alt="" />
                                        </div>

                                        <div className="content">
                                            <h4 className="mb-[10px] font-medium text-[16px] line-clamp-2">{item.title}</h4>
                                            <p className='price_item'>${item.price}</p>

                                            <div className="flex items-center mt-[5px] gap-[5px]">
                                                <button className="w-[40px] h-[40px] text-[22px] md:w-[27px] md:h-[27px] flex items-center justify-center cursor-pointer md:text-[20px] rounded-[2px] border border-border-custom" onClick={() => decreaseQuantity(item.id)}>-</button>
                                                <span className='text-[18px] min-w-[45px] h-[40px] md:min-w-[40px] md:h-auto flex justify-center items-center bg-bg border border-border-custom'>{item.quantity}</span>
                                                <button className="w-[40px] h-[40px] text-[22px] md:w-[27px] md:h-[27px] flex items-center justify-center cursor-pointer md:text-[20px] rounded-[2px] border border-border-custom" onClick={() => increaseQuantity(item.id)}>+</button>
                                            </div>
                                        </div>

                                    </div>
                                    <button onClick={() => removeFromCart(item.id)} className='outline-none border-none bg-transparent group'><FaTrashAlt className="text-[25px] cursor-pointer text-[#e51a1a] transition-transform duration-300 group-hover:scale-125" /></button>
                                </div>
                            ))
                        )}
                    </div>


                    <div className="border-t border-border-custom pt-[25px]">
                        <div className="flex items-center justify-between mb-[20px]">
                            <p className="text-[20px] text-heading capitalize">Total:</p>
                            <span className='text-[20px] font-bold'>${total.toFixed(2)}</span>
                        </div>

                        <div className="border-t border-border-custom py-[30px]">
                            <Link className="block w-full" to="/payment">
                                <button className="w-full bg-main text-white border-2 border-main py-[15px] outline-none rounded-[2px] text-[20px] font-bold cursor-pointer transition-colors duration-300 hover:bg-transparent hover:text-main" type='button'>Proceed to Payment</button>
                            </Link>
                        </div>
                    </div>
                </div>
            </div>
        </PageTransation>
    )
}

export default Cart