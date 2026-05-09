import React from 'react';
import { Link } from 'react-router-dom';
import logo from '../../assets/images/image.png';
import { FaFacebookF, FaTwitter, FaInstagram, FaLinkedinIn, FaEnvelope, FaPhoneAlt, FaMapMarkerAlt } from 'react-icons/fa';

const Footer = () => {
    const currentYear = new Date().getFullYear();

    return (
        <footer className="bg-heading text-white pt-20 pb-10">
            <div className="container mx-auto px-4 w-[90%] max-w-[1350px]">
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-12 mb-16">
                    {/* Brand Section */}
                    <div className="flex flex-col gap-6">
                        <Link to="/" className="w-[80px] h-[80px] rounded-full border-2 border-main overflow-hidden bg-white p-1">
                            <img src={logo} alt="Logo" className="w-full h-full object-contain" />
                        </Link>
                        <p className="text-gray-400 text-sm leading-relaxed">
                            Advanced AI-powered E-Commerce Market Dynamics & XAI Forecasting Engine. Empowering your retail decisions with predictive intelligence.
                        </p>
                        <div className="flex gap-4">
                            {[FaFacebookF, FaTwitter, FaInstagram, FaLinkedinIn].map((Icon, idx) => (
                                <a key={idx} href="#" className="w-9 h-9 rounded-full bg-white/5 flex items-center justify-center hover:bg-main transition-all duration-300">
                                    <Icon size={16} />
                                </a>
                            ))}
                        </div>
                    </div>

                    {/* Quick Links */}
                    <div>
                        <h4 className="text-lg font-bold mb-8 relative after:content-[''] after:absolute after:-bottom-2 after:left-0 after:w-12 after:h-1 after:bg-main">Quick Links</h4>
                        <ul className="flex flex-col gap-4 text-gray-400 text-sm">
                            <li><Link to="/" className="hover:text-main transition-colors">Market Home</Link></li>
                            <li><Link to="/about" className="hover:text-main transition-colors">About Intelligence</Link></li>
                            <li><Link to="/blog" className="hover:text-main transition-colors">Forecasting Blog</Link></li>
                            <li><Link to="/contact" className="hover:text-main transition-colors">Contact Expert</Link></li>
                        </ul>
                    </div>

                    {/* Legal & Support */}
                    <div>
                        <h4 className="text-lg font-bold mb-8 relative after:content-[''] after:absolute after:-bottom-2 after:left-0 after:w-12 after:h-1 after:bg-main">Compliance</h4>
                        <ul className="flex flex-col gap-4 text-gray-400 text-sm">
                            <li><Link to="/privacy-policy" className="hover:text-main transition-colors">Privacy Policy</Link></li>
                            <li><Link to="/terms-of-service" className="hover:text-main transition-colors">Terms of Service</Link></li>
                            <li><Link to="/faq" className="hover:text-main transition-colors">F.A.Q</Link></li>
                            <li><Link to="/sitemap" className="hover:text-main transition-colors">Sitemap</Link></li>
                        </ul>
                    </div>

                    {/* Contact Info */}
                    <div>
                        <h4 className="text-lg font-bold mb-8 relative after:content-[''] after:absolute after:-bottom-2 after:left-0 after:w-12 after:h-1 after:bg-main">Get in Touch</h4>
                        <ul className="flex flex-col gap-5 text-gray-400 text-sm">
                            <li className="flex gap-3">
                                <FaMapMarkerAlt className="text-main mt-1 shrink-0" />
                                <span>123 Market Insight Plaza, XAI District, AI City</span>
                            </li>
                            <li className="flex gap-3">
                                <FaPhoneAlt className="text-main mt-1 shrink-0" />
                                <span>+1 (555) MARKET-AI</span>
                            </li>
                            <li className="flex gap-3">
                                <FaEnvelope className="text-main mt-1 shrink-0" />
                                <span>support@market-xai.com</span>
                            </li>
                        </ul>
                    </div>
                </div>

                {/* Bottom Bar */}
                <div className="pt-8 border-t border-white/5 flex flex-col md:flex-row justify-between items-center gap-4 text-gray-500 text-[13px]">
                    <p>© {currentYear} Market XAI Forecasting Engine. All rights reserved.</p>
                    <div className="flex gap-6">
                        <Link to="/privacy-policy" className="hover:text-gray-300">Privacy</Link>
                        <Link to="/terms-of-service" className="hover:text-gray-300">Terms</Link>
                        <Link to="/cookies" className="hover:text-gray-300">Cookies</Link>
                    </div>
                </div>
            </div>
        </footer>
    );
};

export default Footer;
