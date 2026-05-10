import React from 'react';
import PageTransation from '../components/PageTransation';

const About = () => {
  return (
    <PageTransation>
      <div className="py-[80px] bg-white">
        <div className="container mx-auto px-4 w-[90%] max-w-[1350px]">
          <div className="max-w-[800px] mx-auto text-center mb-[60px]">
            <h1 className="text-[3rem] font-bold text-heading mb-[20px]">About Our Forecasting Engine</h1>
            <p className="text-p text-lg leading-relaxed">
              We are a next-generation e-commerce platform that leverages Explainable AI (XAI) 
              to provide deep market insights and price forecasting for the electronics industry.
            </p>
          </div>

          <div className="grid md:grid-cols-2 gap-[50px] items-center">
            <div>
              <h2 className="text-[2rem] font-bold text-heading mb-[20px]">Our Mission</h2>
              <p className="text-p mb-[20px] leading-relaxed">
                Our mission is to empower consumers with data-driven transparency. In a market characterized 
                by high volatility and rapid price changes, we provide the tools needed to make informed 
                purchasing decisions.
              </p>
              <div className="space-y-[15px]">
                <div className="flex items-center gap-[15px]">
                  <div className="w-[40px] h-[40px] bg-main/10 text-main flex items-center justify-center rounded-full font-bold">1</div>
                  <p className="text-heading font-medium">Real-time Price Tracking</p>
                </div>
                <div className="flex items-center gap-[15px]">
                  <div className="w-[40px] h-[40px] bg-main/10 text-main flex items-center justify-center rounded-full font-bold">2</div>
                  <p className="text-heading font-medium">AI-Powered Market Dynamics</p>
                </div>
                <div className="flex items-center gap-[15px]">
                  <div className="w-[40px] h-[40px] bg-main/10 text-main flex items-center justify-center rounded-full font-bold">3</div>
                  <p className="text-heading font-medium">Predictive Analytics</p>
                </div>
              </div>
            </div>
            <div className="bg-slate-50 p-[40px] rounded-[20px] border border-slate-100">
              <h3 className="text-[1.5rem] font-bold text-heading mb-[15px]">The Technology</h3>
              <p className="text-p mb-[20px] text-sm">
                Our backend uses high-dimensional ONNX models trained on over 600,000 data points 
                scraped from major electronics retailers. We consider factors like CPI inflation, 
                EGP/USD exchange rates, and competitor scarcity to predict future price movements.
              </p>
              <div className="p-[20px] bg-main text-white rounded-[15px]">
                <p className="font-bold text-xl mb-[5px]">89% Accuracy</p>
                <p className="text-xs opacity-80">On 14-day price forecasting across laptops and mobile segments.</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </PageTransation>
  );
};

export default About;
