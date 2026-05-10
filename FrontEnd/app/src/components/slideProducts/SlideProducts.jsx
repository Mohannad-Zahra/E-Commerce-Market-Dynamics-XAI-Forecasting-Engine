import React from 'react'
import Product from './Product'

import 'swiper/css';

import { Swiper, SwiperSlide } from 'swiper/react';
import 'swiper/css';
import 'swiper/css/navigation';
import {Autoplay , Navigation } from 'swiper/modules';

const SlideProducts = ({data ,title, subtitle}) => {
  return (
    <div className='py-[50px]'>
      <div className="container mx-auto px-4 w-[90%] max-w-[1350px]">
        <div className="mb-[30px]">
          <h2 className="text-2xl font-bold text-heading mb-2">{title}</h2>
          <p className="text-p text-[15px] opacity-70">{subtitle}</p>
        </div>
        <Swiper 
        autoplay = {{
          delay: 2500,
          disableOnInteraction: false,
        }}
        loop={true}
        breakpoints={{
          320: { slidesPerView: 1, spaceBetween: 10 },
          480: { slidesPerView: 2, spaceBetween: 20 },
          768: { slidesPerView: 3, spaceBetween: 30 },
          1024: { slidesPerView: 4, spaceBetween: 30 },
          1200: { slidesPerView: 5, spaceBetween: 30 },
        }}
         navigation={true} modules={[Navigation , Autoplay ]} className="mySwiper">
          
          {data && data.map((item) => (
            <SwiperSlide key={item.id}>
              <Product item={item} />
            </SwiperSlide>
          ))}
          
          
          
          
        </Swiper>
        
      </div>
    </div>
  )
}

export default SlideProducts