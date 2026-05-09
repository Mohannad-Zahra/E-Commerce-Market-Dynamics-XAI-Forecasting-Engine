import React from 'react';
import PageTransation from '../components/PageTransation';
import blogGpu from '../assets/images/blog_gpu.png';
import blogLaptop from '../assets/images/blog_laptop.png';
import blogEconomy from '../assets/images/blog_economy.png';

const BlogPost = ({ title, date, excerpt, category, image }) => (
  <div className="bg-white border border-slate-100 rounded-[20px] overflow-hidden hover:shadow-2xl transition-all duration-500 group">
    <div className="h-[240px] overflow-hidden relative">
      <img 
        src={image} 
        alt={title} 
        className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-110" 
      />
      <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500 flex items-end p-6">
        <span className="text-white text-[12px] font-bold uppercase tracking-[0.2em]">Read Article</span>
      </div>
    </div>
    <div className="p-[30px]">
      <span className="text-main text-[11px] font-extrabold uppercase tracking-[0.15em] bg-main/5 px-3 py-1 rounded-full">{category}</span>
      <h3 className="text-[1.35rem] font-bold text-heading mt-[15px] mb-[10px] leading-tight group-hover:text-main transition-colors">{title}</h3>
      <p className="text-p text-sm mb-[20px] line-clamp-2 leading-relaxed">{excerpt}</p>
      <div className="flex justify-between items-center pt-5 border-t border-slate-50">
        <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-main animate-pulse"></div>
            <span className="text-[12px] text-p font-medium">{date}</span>
        </div>
        <button className="text-main text-[13px] font-bold hover:translate-x-1 transition-transform">Explore →</button>
      </div>
    </div>
  </div>
);

const Blog = () => {
  return (
    <PageTransation>
      <div className="py-[100px] bg-[#fdfdfe]">
        <div className="container mx-auto px-4 w-[90%] max-w-[1350px]">
          <div className="flex flex-col md:flex-row justify-between items-center gap-6 mb-[60px] text-center md:text-left">
            <div>
              <h1 className="text-[3rem] font-black text-heading tracking-tight mb-2">Market <span className="text-main">Insights</span></h1>
              <p className="text-p text-lg max-w-xl">Stay ahead of the curve with our AI-driven analysis of the global tech economy and hardware dynamics.</p>
            </div>
            <div className="h-[2px] flex-1 bg-gradient-to-r from-main/20 to-transparent hidden lg:block mx-10"></div>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-[40px]">
            <BlogPost 
              title="Understanding RTX GPU Price Volatility" 
              date="May 5, 2026" 
              category="Market Analysis"
              image={blogGpu}
              excerpt="Why have gaming laptop prices spiked this quarter? We dive into the macroeconomic factors affecting local inventory and GPU supply chains."
            />
            <BlogPost 
              title="Top 5 Laptops for Data Scientists in 2026" 
              date="April 28, 2026" 
              category="Guides"
              image={blogLaptop}
              excerpt="Looking for the best compute potential? Our AI engine ranks the top mobile workstations optimized for tensor-core performance."
            />
            <BlogPost 
              title="How Inflation Impacts Your Tech Budget" 
              date="April 20, 2026" 
              category="Economy"
              image={blogEconomy}
              excerpt="The official EGP/USD rate has stabilized, but local CPI inflation continues to create unique challenges for retail tech procurement."
            />
          </div>
        </div>
      </div>
    </PageTransation>
  );
};

export default Blog;
