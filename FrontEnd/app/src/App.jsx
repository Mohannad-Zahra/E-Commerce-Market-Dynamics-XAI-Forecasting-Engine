
import Header from './components/Header/Header'
import Home from './page/Home/Home'
import { Routes, Route } from 'react-router-dom'
import ProductDetails from './page/productDetails/ProductDetails'
import Cart from './page/cart/Cart'
import { Toaster } from 'react-hot-toast';
import './index.css'
import ScrollToTop from './components/ScrollToTop'
import { AnimatePresence } from 'framer-motion'
import CategoryPage from './page/CategoryPage/CategoryPage'
import SearchResults from './page/SearchResults';
import Login from './page/Login/Login';
import Signup from './page/Signup/Signup';
import Payment from './page/Payment/Payment';
import About from './page/About';
import Blog from './page/Blog';
import Contact from './page/Contact';
import Footer from './components/Footer/Footer';
import NotFound from './page/NotFound';
import LegalPage from './page/LegalPage';
import Favorites from './page/Favorites';

function App() {

  return (
    <>
      <Header />
      <Toaster
        position="bottom-right"
        toastOptions={{
          style: {
            background: "#e9e9e9",
          }
        }}

      />
      <ScrollToTop />
      <AnimatePresence mode="wait">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/cart" element={<Cart />} />
          <Route path="/search" element={<SearchResults />} />
          <Route path="/product/:id" element={<ProductDetails />} />
          <Route path="/category/:slug" element={<CategoryPage />} />
          <Route path="/about" element={<About />} />
          <Route path="/blog" element={<Blog />} />
          <Route path="/contact" element={<Contact />} />
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Signup />} />
          <Route path="/payment" element={<Payment />} />
          <Route path="/favorites" element={<Favorites />} />
          
          {/* Legal Routes */}
          <Route path="/privacy-policy" element={<LegalPage title="Privacy Policy" />} />
          <Route path="/terms-of-service" element={<LegalPage title="Terms of Service" />} />
          
          {/* Catch-all 404 */}
          <Route path="*" element={<NotFound />} />
        </Routes>
      </AnimatePresence>
      <Footer />
    </>
  )
}

export default App
