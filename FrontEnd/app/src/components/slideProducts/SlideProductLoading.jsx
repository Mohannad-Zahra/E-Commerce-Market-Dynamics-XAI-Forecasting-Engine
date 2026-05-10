const SlideProductLoading = () => {
    return (
        <div className="py-[50px] w-full overflow-hidden">
            <div className="container mx-auto px-4 w-[90%] max-w-[1350px]">
                <div className="mb-[25px]">
                    <h2 className="animate-shine bg-gray-200 h-[35px] w-[250px] mb-2 rounded"> </h2>
                    <p className="animate-shine bg-gray-200 h-4 w-1/3 rounded"></p>
                </div>
                <div className="flex gap-[30px] overflow-hidden w-full">
                    {[...Array(5)].map((_, i) => (
                        <div key={i} className="flex-1 min-w-[200px] border border-border-custom p-[10px] rounded-[8px] bg-white">
                            <div className="h-[180px] bg-gray-200 animate-shine rounded mb-[10px]"></div>
                            <div className="h-[30px] bg-gray-200 animate-shine rounded mb-[10px]"></div>
                            <div className="h-[30px] bg-gray-200 animate-shine rounded mb-[10px]"></div>
                            <div className="h-[30px] bg-gray-200 animate-shine rounded mb-[10px]"></div>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
};

export default SlideProductLoading;