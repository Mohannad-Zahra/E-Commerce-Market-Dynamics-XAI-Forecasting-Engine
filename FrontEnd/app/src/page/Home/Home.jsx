import React, { useEffect } from 'react'
import HeroSlider from '../../components/HeroSlider'
import SlideProducts from '../../components/slideProducts/SlideProducts'
import SlideProductLoading from '../../components/slideProducts/SlideProductLoading'
import PageTransation from '../../components/PageTransation'
import StatsBar from '../../components/StatsBar'
import { apiFetch } from '../../api'

const Home = () => {
  const [products, setProducts] = React.useState({});
  const [categories, setCategories] = React.useState([]);
  const [loading, setLoading] = React.useState(true);

  useEffect(() => {
    const fetchAllData = async () => {
      try {
        // Categories are plain strings from our backend
        const catData = await apiFetch('/api/products/categories');
        setCategories(catData);

        // Fetch products for each category in parallel
        const results = await Promise.all(
          catData.map(async (category) => {
            const data = await apiFetch(`/api/products/category/${category}`);
            return { [category]: data.products };
          })
        );

        const productsData = Object.assign({}, ...results);
        setProducts(productsData);
      } catch (error) {
        console.error("Error fetching products:", error);
      } finally {
        setLoading(false);
      }
    };

    fetchAllData();
  }, []);

  // Premium category titles for marketing appeal
  const getSectionTitle = (cat) => {
    const titles = {
      'laptops': 'Premium Workstations & Laptops',
      'mobiles': 'Latest Smartphones & Devices',
      'pc-components': 'High-Performance PC Components',
      'accessories': 'Essential Tech Accessories',
      'monitors': 'Ultra-Wide & Gaming Monitors',
      'gaming-consoles': 'Next-Gen Gaming Consoles',
      'tablets': 'Professional Tablets & iPads',
      'electronics': 'Featured Electronics'
    };
    return titles[cat] || cat.replace(/-/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  };

  return (
    <PageTransation>
      <div className="flex flex-col gap-20 pb-20">
        <HeroSlider />
        <StatsBar />

        <div className="flex flex-col gap-24">
          {loading ? (
            <div style={{ textAlign: "center", fontSize: "24px", width: "100%" }}>
              <SlideProductLoading />
            </div>
          ) : (
            categories.map((category) => (
              <div key={category} className="mb-10 last:mb-0">
                <SlideProducts
                  data={products[category]}
                  title={getSectionTitle(category)}
                />
              </div>
            ))
          )}
        </div>
      </div>
    </PageTransation>
  );
}

export default Home