import React, { useContext, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { CartContext } from '../../context/CartContext';
import { FaCreditCard, FaPaypal, FaApplePay } from 'react-icons/fa';
import toast from 'react-hot-toast';
import PageTransation from '../../components/PageTransation';

const Payment = () => {
  const { cartItems } = useContext(CartContext);
  const total = cartItems.reduce((acc, item) => acc + item.price * item.quantity, 0);
  const navigate = useNavigate();
  const [paymentMethod, setPaymentMethod] = useState('card');

  const handlePayment = (e) => {
    e.preventDefault();
    toast.success('Payment successful! Your order has been placed.');
    setTimeout(() => {
      navigate('/');
    }, 2000);
  };

  if (cartItems.length === 0) {
    return (
      <PageTransation>
        <div className="min-h-[calc(100vh-150px)] py-[60px] px-[20px] flex justify-center items-center bg-gradient-to-br from-[#f6f8fb] to-[#e5ebee] relative overflow-hidden flex-col gap-[20px] text-center">
          <div className="absolute w-[500px] h-[500px] rounded-full top-[-150px] left-[-150px] bg-[radial-gradient(circle,rgba(0,144,240,0.1)_0%,transparent_70%)] z-0"></div>
          <h2 className="z-10 relative text-2xl font-bold">Your cart is empty</h2>
          <button className="z-10 relative bg-gradient-to-br from-main to-[#007bb5] text-white p-[18px] rounded-[14px] text-[1.1rem] font-semibold cursor-pointer transition-all duration-300 border-none text-center shadow-[0_10px_20px_rgba(0,144,240,0.25)] hover:-translate-y-[2px] hover:shadow-[0_15px_25px_rgba(0,144,240,0.35)]" onClick={() => navigate('/')}>Continue Shopping</button>
        </div>
      </PageTransation>
    );
  }

  return (
    <PageTransation>
      <div className="min-h-[calc(100vh-150px)] py-[60px] px-[20px] flex justify-center items-center bg-gradient-to-br from-[#f6f8fb] to-[#e5ebee] relative overflow-hidden">
        <div className="absolute w-[500px] h-[500px] rounded-full top-[-150px] left-[-150px] bg-[radial-gradient(circle,rgba(0,144,240,0.1)_0%,transparent_70%)] z-0"></div>
        <div className="flex flex-col md:flex-row bg-white/70 backdrop-blur-xl border border-white/50 rounded-[24px] w-full max-w-[1000px] shadow-[0_25px_50px_rgba(0,0,0,0.08)] overflow-hidden z-10 relative">
          <div className="flex-[3] p-[30px] md:p-[50px] bg-white rounded-t-[24px] md:rounded-l-[24px] md:rounded-tr-none">
            <h2 className="text-2xl md:text-[2rem] mb-[5px] text-heading font-bold">Payment Details</h2>
            <p className="text-p mb-[30px]">Complete your purchase securely</p>

            <div className="flex flex-col sm:flex-row gap-[15px] mb-[30px]">
              <label className={`flex-1 flex flex-col items-center justify-center gap-[10px] py-[20px] px-[10px] border-2 rounded-[16px] cursor-pointer transition-all duration-300 relative ${paymentMethod === 'card' ? 'border-main bg-[#0090f0]/5' : 'border-[#e5e7eb]'}`}>
                <input type="radio" name="method" value="card" checked={paymentMethod === 'card'} onChange={() => setPaymentMethod('card')} className="absolute opacity-0" />
                <FaCreditCard className={`text-[24px] transition-colors duration-300 ${paymentMethod === 'card' ? 'text-main' : 'text-[#6b7280]'}`} />
                <span className="font-semibold text-[0.9rem] text-heading">Credit Card</span>
              </label>
              <label className={`flex-1 flex flex-col items-center justify-center gap-[10px] py-[20px] px-[10px] border-2 rounded-[16px] cursor-pointer transition-all duration-300 relative ${paymentMethod === 'paypal' ? 'border-main bg-[#0090f0]/5' : 'border-[#e5e7eb]'}`}>
                <input type="radio" name="method" value="paypal" checked={paymentMethod === 'paypal'} onChange={() => setPaymentMethod('paypal')} className="absolute opacity-0" />
                <FaPaypal className={`text-[24px] transition-colors duration-300 ${paymentMethod === 'paypal' ? 'text-main' : 'text-[#6b7280]'}`} />
                <span className="font-semibold text-[0.9rem] text-heading">PayPal</span>
              </label>
              <label className={`flex-1 flex flex-col items-center justify-center gap-[10px] py-[20px] px-[10px] border-2 rounded-[16px] cursor-pointer transition-all duration-300 relative ${paymentMethod === 'apple' ? 'border-main bg-[#0090f0]/5' : 'border-[#e5e7eb]'}`}>
                <input type="radio" name="method" value="apple" checked={paymentMethod === 'apple'} onChange={() => setPaymentMethod('apple')} className="absolute opacity-0" />
                <FaApplePay className={`text-[24px] transition-colors duration-300 ${paymentMethod === 'apple' ? 'text-main' : 'text-[#6b7280]'}`} />
                <span className="font-semibold text-[0.9rem] text-heading">Apple Pay</span>
              </label>
            </div>

            {paymentMethod === 'card' && (
              <form onSubmit={handlePayment} className="flex flex-col gap-[20px]">
                <div className="flex flex-col gap-[8px]">
                  <label className="text-[0.95rem] text-heading font-semibold">Cardholder Name</label>
                  <input className="p-[16px] rounded-[14px] border-2 border-transparent bg-[#f3f4f6] text-[1rem] transition-all duration-300 focus:border-main focus:bg-white focus:outline-none" type="text" placeholder="John Doe" required />
                </div>
                <div className="flex flex-col gap-[8px]">
                  <label className="text-[0.95rem] text-heading font-semibold">Card Number</label>
                  <input className="p-[16px] rounded-[14px] border-2 border-transparent bg-[#f3f4f6] text-[1rem] transition-all duration-300 focus:border-main focus:bg-white focus:outline-none" type="text" placeholder="0000 0000 0000 0000" maxLength="19" required />
                </div>
                <div className="flex flex-col sm:flex-row gap-[20px]">
                  <div className="flex flex-col gap-[8px] flex-1">
                    <label className="text-[0.95rem] text-heading font-semibold">Expiry Date</label>
                    <input className="p-[16px] rounded-[14px] border-2 border-transparent bg-[#f3f4f6] text-[1rem] transition-all duration-300 focus:border-main focus:bg-white focus:outline-none" type="text" placeholder="MM/YY" maxLength="5" required />
                  </div>
                  <div className="flex flex-col gap-[8px] flex-1">
                    <label className="text-[0.95rem] text-heading font-semibold">CVC</label>
                    <input className="p-[16px] rounded-[14px] border-2 border-transparent bg-[#f3f4f6] text-[1rem] transition-all duration-300 focus:border-main focus:bg-white focus:outline-none" type="password" placeholder="123" maxLength="3" required />
                  </div>
                </div>
                <button type="submit" className="mt-[20px] bg-gradient-to-br from-main to-[#007bb5] text-white p-[18px] rounded-[14px] text-[1.1rem] font-semibold cursor-pointer transition-all duration-300 border-none text-center shadow-[0_10px_20px_rgba(0,144,240,0.25)] hover:-translate-y-[2px] hover:shadow-[0_15px_25px_rgba(0,144,240,0.35)]">
                  Pay ${total.toFixed(2)}
                </button>
              </form>
            )}

            {paymentMethod !== 'card' && (
              <div className="flex flex-col items-center gap-[20px] py-[40px] text-center text-p">
                <p>You will be redirected to complete your purchase securely.</p>
                <button onClick={handlePayment} className="w-full bg-gradient-to-br from-main to-[#007bb5] text-white p-[18px] rounded-[14px] text-[1.1rem] font-semibold cursor-pointer transition-all duration-300 border-none text-center shadow-[0_10px_20px_rgba(0,144,240,0.25)] hover:-translate-y-[2px] hover:shadow-[0_15px_25px_rgba(0,144,240,0.35)]">
                  Continue with {paymentMethod === 'paypal' ? 'PayPal' : 'Apple Pay'}
                </button>
              </div>
            )}

          </div>
          
          <div className="flex-[2] p-[30px] md:p-[50px] bg-[#f9fafb]/80 border-t md:border-t-0 md:border-l border-black/5">
            <h3 className="text-[1.5rem] mb-[25px] text-heading font-bold">Order Summary</h3>
            <div className="flex flex-col gap-[20px] mb-[30px] max-h-[300px] overflow-y-auto pr-[10px]">
              {cartItems.map((item, idx) => (
                <div className="flex items-center gap-[15px]" key={idx}>
                  <img className="w-[60px] h-[60px] object-cover rounded-[12px] border border-[#e5e7eb]" src={item.images[0]} alt={item.title} />
                  <div className="flex-1">
                    <h4 className="text-[0.95rem] mb-[4px] leading-tight text-heading font-semibold">{item.title}</h4>
                    <p className="text-[0.85rem] text-p">Qty: {item.quantity}</p>
                  </div>
                  <span className="font-bold text-[1rem] text-heading">${(item.price * item.quantity).toFixed(2)}</span>
                </div>
              ))}
            </div>
            
            <div className="border-t-2 border-dashed border-[#e5e7eb] pt-[20px] flex flex-col gap-[12px]">
              <div className="flex justify-between text-p text-[0.95rem]">
                <span>Subtotal</span>
                <span>${total.toFixed(2)}</span>
              </div>
              <div className="flex justify-between text-p text-[0.95rem]">
                <span>Shipping</span>
                <span>Free</span>
              </div>
              <div className="flex justify-between text-p text-[0.95rem] text-[1.25rem] font-bold text-heading mt-[10px] pt-[10px] border-t border-[#e5e7eb]">
                <span>Total</span>
                <span>${total.toFixed(2)}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </PageTransation>
  );
};

export default Payment;
