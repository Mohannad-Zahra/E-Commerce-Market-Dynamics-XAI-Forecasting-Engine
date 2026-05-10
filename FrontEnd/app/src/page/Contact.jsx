import React from 'react';
import PageTransation from '../components/PageTransation';

const Contact = () => {
  return (
    <PageTransation>
      <div className="py-[80px] bg-white">
        <div className="container mx-auto px-4 w-[90%] max-w-[1350px]">
          <div className="grid md:grid-cols-2 gap-[80px]">
            <div>
              <h1 className="text-[3rem] font-bold text-heading mb-[20px]">Get in Touch</h1>
              <p className="text-p text-lg mb-[40px]">
                Have questions about our forecasting models or need help finding the right product? 
                Our team is here to assist you.
              </p>
              
              <div className="space-y-[30px]">
                <div>
                  <h4 className="text-[1.1rem] font-bold text-heading mb-[5px]">Our Office</h4>
                  <p className="text-p">Cairo Digital District, Smart Village, Egypt</p>
                </div>
                <div>
                  <h4 className="text-[1.1rem] font-bold text-heading mb-[5px]">Email Us</h4>
                  <p className="text-p">support@xai-forecast.eg</p>
                </div>
                <div>
                  <h4 className="text-[1.1rem] font-bold text-heading mb-[5px]">Call Us</h4>
                  <p className="text-p">+20 (0) 123 456 789</p>
                </div>
              </div>
            </div>

            <div className="bg-slate-50 p-[40px] rounded-[20px] border border-slate-100 shadow-sm">
              <form className="space-y-[20px]">
                <div className="grid sm:grid-cols-2 gap-[20px]">
                  <div className="flex flex-col gap-[8px]">
                    <label className="text-sm font-bold text-heading">Full Name</label>
                    <input type="text" className="p-[12px] border border-slate-200 rounded-[10px] outline-none focus:border-main transition-colors" placeholder="John Doe" />
                  </div>
                  <div className="flex flex-col gap-[8px]">
                    <label className="text-sm font-bold text-heading">Email Address</label>
                    <input type="email" className="p-[12px] border border-slate-200 rounded-[10px] outline-none focus:border-main transition-colors" placeholder="john@example.com" />
                  </div>
                </div>
                <div className="flex flex-col gap-[8px]">
                  <label className="text-sm font-bold text-heading">Subject</label>
                  <input type="text" className="p-[12px] border border-slate-200 rounded-[10px] outline-none focus:border-main transition-colors" placeholder="How can we help?" />
                </div>
                <div className="flex flex-col gap-[8px]">
                  <label className="text-sm font-bold text-heading">Message</label>
                  <textarea className="p-[12px] border border-slate-200 rounded-[10px] outline-none focus:border-main transition-colors min-h-[150px]" placeholder="Your message here..."></textarea>
                </div>
                <button type="submit" className="w-full bg-main text-white font-bold py-[15px] rounded-[10px] hover:bg-main/90 transition-all">Send Message</button>
              </form>
            </div>
          </div>
        </div>
      </div>
    </PageTransation>
  );
};

export default Contact;
