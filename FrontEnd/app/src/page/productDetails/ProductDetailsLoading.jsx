import React from 'react'

const ProductDetailsLoading = () => {
    return (
        <div className="py-[50px]">
            <div className='container mx-auto px-4 w-[90%] max-w-[1350px] flex flex-col md:flex-row justify-between items-center gap-[30px] md:gap-0'>
                <div className="w-full md:w-[40%] h-[600px] bg-gray-200 animate-shine rounded"></div>

                <div className="w-full md:w-[58%] h-[600px] pt-[10px] md:pt-[100px]">
                    <h5 className='mb-[50px] h-[30px] bg-gray-200 animate-shine rounded'></h5>
                    <h5 className='mb-[50px] h-[30px] bg-gray-200 animate-shine rounded'></h5>
                    <h5 className='mb-[50px] h-[30px] bg-gray-200 animate-shine rounded'></h5>
                    <h5 className='mb-[50px] h-[30px] bg-gray-200 animate-shine rounded'></h5>
                    <h5 className='mb-[50px] h-[30px] bg-gray-200 animate-shine rounded'></h5>
                </div>
            </div>
        </div>
    )
}

export default ProductDetailsLoading