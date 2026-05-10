import React from 'react';
import { Link } from 'react-router-dom';
import { FiHome, FiAlertCircle } from 'react-icons/fi';
import PageTransation from '../components/PageTransation';

const NotFound = () => {
    return (
        <PageTransation>
            <div className="min-h-[60vh] flex flex-col items-center justify-center text-center px-4 py-20">
                <div className="relative mb-8">
                    <h1 className="text-[120px] md:text-[180px] font-black text-main/10 leading-none select-none">404</h1>
                    <div className="absolute inset-0 flex items-center justify-center">
                        <FiAlertCircle className="text-main text-6xl md:text-8xl animate-bounce" />
                    </div>
                </div>
                
                <h2 className="text-3xl md:text-4xl font-bold text-heading mb-4">Page Not Found</h2>
                <p className="text-p max-w-md mb-10 text-lg">
                    Oops! The page you're looking for doesn't exist or has been moved to another market orbit.
                </p>
                
                <Link to="/" className="btn shadow-lg hover:shadow-main/30">
                    <FiHome />
                    Back to Home
                </Link>
            </div>
        </PageTransation>
    );
};

export default NotFound;
