import React from 'react'
// Import Swiper React components
import { Swiper, SwiperSlide } from "swiper/react";

import { Navigation, Pagination, Scrollbar, A11y } from 'swiper/modules';
import { Autoplay } from 'swiper/modules';

// Import Swiper styles


import 'swiper/css';
import 'swiper/css/navigation';
import 'swiper/css/pagination';
import 'swiper/css/scrollbar';
import 'swiper/css/autoplay';


import bannerHero1 from "../assets/images/banner_Hero1.jpg";
import bannerHero2 from "../assets/images/banner_Hero2.jpg";  
import bannerHero3 from "../assets/images/banner_Hero3.jpg";


import { Link } from "react-router-dom";




const HeroSlider = () => {
    return (
        <>
            <div className="relative mb-[80px] pt-[20px]">
                <div className="container mx-auto px-4 w-[90%] max-w-[1350px]">
                    <Swiper
                        loop={true}
                        autoplay={{
                            delay: 3500,
                            disableOnInteraction: false,
                        }}
                        pagination={true}
                        modules={[Pagination, Autoplay]}
                        className="mySwiper"
                    >
                        <SwiperSlide>
                            <div className="absolute top-1/2 -translate-y-1/2 left-[5%] z-10">
                                <h4 className="uppercase text-[clamp(12px,2vw,18px)] italic font-normal mb-[0.4vw]">Next-Gen Gaming</h4>
                                <h3 className="text-[clamp(24px,5vw,60px)] capitalize mb-[clamp(15px,3vw,30px)] text-main font-black leading-[1.1]">
                                    Pro Gaming <br /> Laptop Series
                                </h3>
                                <p className="text-[clamp(14px,2vw,24px)] mt-[clamp(10px,1.5vw,20px)] mb-[clamp(15px,2vw,30px)]">Intel Core Ultra 9 | RTX 50 Series | 240Hz</p>
                                <Link to="/" className="bg-transparent text-heading p-0 font-semibold text-[clamp(14px,2vw,20px)] hover:text-main flex items-center gap-[10px] transition-colors duration-300">
                                    Explore Deals
                                </Link>
                            </div>
                            <img className="w-full rounded-2xl overflow-hidden shadow-2xl" src={bannerHero1} alt="gaming laptop banner" />
                        </SwiperSlide>

                        <SwiperSlide>
                            <div className="absolute top-1/2 -translate-y-1/2 left-[5%] z-10">
                                <h4 className="uppercase text-[clamp(12px,2vw,18px)] italic font-normal mb-[0.4vw]">Stay Connected</h4>
                                <h3 className="text-[clamp(24px,5vw,60px)] capitalize mb-[clamp(15px,3vw,30px)] text-main font-black leading-[1.1]">
                                    Latest Flagship <br /> Smartphones
                                </h3>
                                <p className="text-[clamp(14px,2vw,24px)] mt-[clamp(10px,1.5vw,20px)] mb-[clamp(15px,2vw,30px)]">A18 Bionic | Titanium Design | Pro Camera</p>
                                <Link to="/" className="bg-transparent text-heading p-0 font-semibold text-[clamp(14px,2vw,20px)] hover:text-main flex items-center gap-[10px] transition-colors duration-300">
                                    Shop Mobiles
                                </Link>
                            </div>
                            <img className="w-full rounded-2xl overflow-hidden shadow-2xl" src={bannerHero2} alt="smartphone banner" />
                        </SwiperSlide>

                        <SwiperSlide>
                            <div className="absolute top-1/2 -translate-y-1/2 left-[5%] z-10">
                                <h4 className="uppercase text-[clamp(12px,2vw,18px)] italic font-normal mb-[0.4vw]">Build Your Dream PC</h4>
                                <h3 className="text-[clamp(24px,5vw,60px)] capitalize mb-[clamp(15px,3vw,30px)] text-main font-black leading-[1.1]">
                                    Performance PC <br /> Components
                                </h3>
                                <p className="text-[clamp(14px,2vw,24px)] mt-[clamp(10px,1.5vw,20px)] mb-[clamp(15px,2vw,30px)]">Z790 Motherboards | DDR5 RAM | Gen5 SSD</p>
                                <Link to="/" className="bg-transparent text-heading p-0 font-semibold text-[clamp(14px,2vw,20px)] hover:text-main flex items-center gap-[10px] transition-colors duration-300">
                                    Browse Parts
                                </Link>
                            </div>
                            <img className="w-full rounded-2xl overflow-hidden shadow-2xl" src={bannerHero3} alt="pc components banner" />
                        </SwiperSlide>
                    </Swiper>
                </div>
            </div>

        </>
    )
}

export default HeroSlider