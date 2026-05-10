import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';


const Signup = () => {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const navigate = useNavigate();

  const handleSignup = (e) => {
    e.preventDefault();
    // Simulate signup and redirect to login
    navigate('/login');
  };

  return (
    <motion.div 
      className="min-h-[calc(100vh-150px)] flex items-center justify-center bg-gradient-to-br from-[#f6f8fb] to-[#e5ebee] py-[40px] px-[20px] relative overflow-hidden"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      transition={{ duration: 0.5 }}
    >
      <div className="absolute w-[400px] h-[400px] rounded-full top-[-100px] left-[-100px] bg-[radial-gradient(circle,rgba(0,144,240,0.15)_0%,transparent_70%)] z-0"></div>
      <div className="absolute w-[300px] h-[300px] rounded-full bottom-[-50px] right-[-50px] bg-[radial-gradient(circle,rgba(142,45,226,0.1)_0%,transparent_70%)] z-0"></div>
      <div className="bg-white/60 backdrop-blur-[16px] border border-white/40 rounded-[24px] px-[20px] py-[40px] md:px-[40px] md:py-[50px] w-full max-w-[480px] shadow-[0_20px_40px_rgba(0,0,0,0.05)] text-center transition-all duration-300 hover:-translate-y-[5px] hover:shadow-[0_25px_50px_rgba(0,0,0,0.1)] z-10 relative">
        <h2 className="text-[2.2rem] text-heading mb-[10px] font-bold tracking-[-0.5px]">Create Account</h2>
        <p className="text-p mb-[35px] text-[1.05rem]">Join us and start shopping!</p>
        
        <form onSubmit={handleSignup} className="flex flex-col gap-[24px] text-left">
          <div className="flex flex-col gap-[10px]">
            <label className="text-[0.95rem] text-heading font-semibold">Full Name</label>
            <input 
              type="text" 
              placeholder="Enter your name" 
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="p-[16px] rounded-[14px] border-2 border-transparent bg-white/90 text-[1rem] transition-all duration-300 shadow-[0_4px_6px_rgba(0,0,0,0.02)] focus:border-main focus:shadow-[0_0_0_4px_rgba(0,144,240,0.15)] focus:bg-white focus:outline-none"
              required 
            />
          </div>
          <div className="flex flex-col gap-[10px]">
            <label className="text-[0.95rem] text-heading font-semibold">Email</label>
            <input 
              type="email" 
              placeholder="Enter your email" 
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="p-[16px] rounded-[14px] border-2 border-transparent bg-white/90 text-[1rem] transition-all duration-300 shadow-[0_4px_6px_rgba(0,0,0,0.02)] focus:border-main focus:shadow-[0_0_0_4px_rgba(0,144,240,0.15)] focus:bg-white focus:outline-none"
              required 
            />
          </div>
          <div className="flex flex-col gap-[10px]">
            <label className="text-[0.95rem] text-heading font-semibold">Password</label>
            <input 
              type="password" 
              placeholder="Create a password" 
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="p-[16px] rounded-[14px] border-2 border-transparent bg-white/90 text-[1rem] transition-all duration-300 shadow-[0_4px_6px_rgba(0,0,0,0.02)] focus:border-main focus:shadow-[0_0_0_4px_rgba(0,144,240,0.15)] focus:bg-white focus:outline-none"
              required 
            />
          </div>

          <button type="submit" className="bg-gradient-to-br from-main to-[#007bb5] text-white p-[18px] rounded-[14px] text-[1.1rem] font-semibold mt-[10px] cursor-pointer transition-all duration-300 shadow-[0_10px_20px_rgba(0,144,240,0.25)] border-none hover:-translate-y-[2px] hover:shadow-[0_15px_25px_rgba(0,144,240,0.35)] hover:from-[#007bb5] hover:to-main">Sign Up</button>
        </form>
        
        <p className="mt-[30px] text-[0.95rem] text-p">
          Already have an account? <Link className="text-main font-bold transition-colors duration-300 ml-[5px] hover:text-[#007bb5] hover:underline" to="/login">Log in</Link>
        </p>
      </div>
    </motion.div>
  );
};

export default Signup;
