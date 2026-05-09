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
                            delay: 2500,
                            disableOnInteraction: false,
                        }}
                        pagination={true}
                        modules={[Pagination, Autoplay]}
                        className="mySwiper"
                    >
                        <SwiperSlide>
                            <div className="absolute top-1/2 -translate-y-1/2 left-[5%] z-10">
                                <h4 className="uppercase text-[clamp(12px,2vw,18px)] italic font-normal mb-[0.4vw]">Introducing the new</h4>
                                <h3 className="text-[clamp(24px,5vw,60px)] capitalize mb-[clamp(15px,3vw,30px)] text-main font-black leading-[1.1]">
                                    Microsoft Xbox <br /> 360 Controller{" "}
                                </h3>
                                <p className="text-[clamp(14px,2vw,24px)] mt-[clamp(10px,1.5vw,20px)] mb-[clamp(15px,2vw,30px)]">Windows Xp/10/7/8 Ps3, Tv Box</p>
                                <Link to="/" className="bg-transparent text-heading p-0 font-semibold text-[clamp(14px,2vw,20px)] hover:text-main flex items-center gap-[10px] transition-colors duration-300">
                                    Shop Now
                                </Link>
                            </div>
                            <img className="w-full" src={bannerHero1} alt="slider hero 1" />
                        </SwiperSlide>

                        <SwiperSlide>
                            <div className="absolute top-1/2 -translate-y-1/2 left-[5%] z-10">
                                <h4 className="uppercase text-[clamp(12px,2vw,18px)] italic font-normal mb-[0.4vw]">Introducing the new</h4>
                                <h3 className="text-[clamp(24px,5vw,60px)] capitalize mb-[clamp(15px,3vw,30px)] text-main font-black leading-[1.1]">
                                    Microsoft Xbox <br /> 360 Controller{" "}
                                </h3>
                                <p className="text-[clamp(14px,2vw,24px)] mt-[clamp(10px,1.5vw,20px)] mb-[clamp(15px,2vw,30px)]">Windows Xp/10/7/8 Ps3, Tv Box</p>
                                <Link to="/" className="bg-transparent text-heading p-0 font-semibold text-[clamp(14px,2vw,20px)] hover:text-main flex items-center gap-[10px] transition-colors duration-300">
                                    Shop Now
                                </Link>
                            </div>
                            <img className="w-full" src={bannerHero2} alt="slider hero 1" />
                        </SwiperSlide>

                        <SwiperSlide>
                            <div className="absolute top-1/2 -translate-y-1/2 left-[5%] z-10">
                                <h4 className="uppercase text-[clamp(12px,2vw,18px)] italic font-normal mb-[0.4vw]">Introducing the new</h4>
                                <h3 className="text-[clamp(24px,5vw,60px)] capitalize mb-[clamp(15px,3vw,30px)] text-main font-black leading-[1.1]">
                                    Microsoft Xbox <br /> 360 Controller{" "}
                                </h3>
                                <p className="text-[clamp(14px,2vw,24px)] mt-[clamp(10px,1.5vw,20px)] mb-[clamp(15px,2vw,30px)]">Windows Xp/10/7/8 Ps3, Tv Box</p>
                                <Link to="/" className="bg-transparent text-heading p-0 font-semibold text-[clamp(14px,2vw,20px)] hover:text-main flex items-center gap-[10px] transition-colors duration-300">
                                    Shop Now
                                </Link>
                            </div>
                            <img className="w-full" src={bannerHero3} alt="slider hero 1" />
                        </SwiperSlide>
                    </Swiper>
                </div>
            </div>

        </>
    )
}

export default HeroSlider