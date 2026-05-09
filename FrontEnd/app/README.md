# Blue E-commerce

A modern, responsive e-commerce web application built with React and Vite. This project leverages the [DummyJSON API](https://dummyjson.com/) to dynamically fetch out-of-the-box product catalogs, categories, and item details. It provides a polished online shopping prototype complete with interactive product sliders, dynamic routing, and persistent cart management.

## 🚀 Features

- **Dynamic Homepage**: Features an autoplaying Hero Slider and multiple horizontal product carousels organized by category (Smartphones, Laptops, Sunglasses, etc.).
- **Product Details Page**: Displays comprehensive information including an interactive image gallery, star ratings, pricing, brand details, stock availability, and related category products.
- **Modern Utility-First Styling**: Fully styled using **Tailwind CSS v4**, featuring glassmorphism elements, custom gradients, fluid typography, and dynamic interactive hover states.
- **Search & Filter**: Real-time search suggestions with a debounce hook and a dedicated category browsing experience.
- **Shopping Cart & Wishlist**: Fully functional cart and favorites management utilizing React Context API and `localStorage` to persist data across sessions.
- **Mobile-First Responsive Design**: Optimized navigation flows and auto-flowing grid layouts to ensure a premium experience across desktops, tablets, and mobile devices.

## 🛠️ Technology Stack

- **Frontend Framework**: [React 19](https://react.dev/)
- **Styling**: [Tailwind CSS v4](https://tailwindcss.com/)
- **Build Tool**: [Vite](https://vitejs.dev/)
- **Routing**: [React Router v7](https://reactrouter.com/)
- **Sliders/Carousels**: [Swiper](https://swiperjs.com/)
- **Icons**: [React Icons](https://react-icons.github.io/react-icons/)
- **Notifications**: [React Hot Toast](https://react-hot-toast.com/)

## 📂 Project Structure

```text
src/
├── assets/         # Static assets (images, icons)
├── components/     # Reusable UI components
│   ├── Header/     # Consolidated responsive header and search
│   └── slideProducts/ # Product card and Swiper integration
├── context/        # Global state management (CartContext, FavoriteContext)
├── page/           # Main route views
│   ├── CategoryPage/ # Dynamic category routing view
│   ├── Home/       # Landing page with categorized product sliders
│   ├── Login/      # Glassmorphism styled authentication
│   ├── Signup/     # Glassmorphism styled authentication
│   ├── cart/       # Checkout and order summary page
│   └── productDetails/ # Individual product deep-dive
├── App.jsx         # Root component and Route definitions
├── index.css       # Tailwind v4 theme tokens and global styles
└── main.jsx        # React DOM entry point
```

## ⚙️ Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/AbdelrhamanWael/Blue_E-commerce-.git
   cd "Blue_E-commerce-/Ecommerce Website/app"
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Run the development server:**
   ```bash
   npm run dev
   ```

4. **Open in Browser:**
   Navigate to `http://localhost:5174` (or the port specified by Vite) to explore the application.

## 🤝 Contributing

Contributions are welcome! If you'd like to improve the project, please fork the repository and use a feature branch. Pull requests are warmly welcomed.

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'feat: Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is open-source and available under the MIT License.
