# 🌐 Frenzo Frontend — Vue 3 + Vite

This is the **frontend** for the Frenzo modern social media platform, built with **Vue 3**, **Pinia**, **Tailwind CSS**, and **Vite**. It communicates with the Django REST Framework backend to provide a fast, responsive, and interactive user experience.

---

## ⚙️ Tech Stack

- ⚡ **Vue 3** — Progressive JavaScript framework
- 🌿 **Pinia** — State management
- 🎨 **Tailwind CSS** — Utility-first CSS framework
- 🚀 **Vite** — Fast development server and build tool
- 🌐 **Vue Router** — Client-side routing
- 🔗 **Axios** — HTTP client for communicating with the backend API

---

## 🚀 Getting Started

### 📦 Install Dependencies

```bash
npm install
```

### ▶️ Start Development Server

```bash
npm run dev
```

The application will be available at:

```
http://localhost:5173
```

### 🛠 Available Scripts

| Script | Description |
|---------|-------------|
| `npm run dev` | Start the development server |
| `npm run build` | Build the project for production |
| `npm run preview` | Preview the production build locally |

---

## 🔗 Backend API

Ensure the Django backend is running at:

```
http://127.0.0.1:8000
```

Authentication is handled using **JWT**, and **Axios** is used for all API requests.

---

## 📁 Project Structure

```text
frontend/
├── public/                 # Static assets
├── src/
│   ├── assets/             # Images and styles
│   ├── components/         # Reusable Vue components
│   ├── pages/              # Page components
│   ├── router/             # Vue Router configuration
│   ├── store/              # Pinia stores
│   └── main.js             # Application entry point
├── index.html
├── package.json
├── tailwind.config.js
└── vite.config.js
```

---

## 🧪 Environment Variables

Create a `.env` file if you want to configure the backend URL.

```env
VITE_API_URL=http://127.0.0.1:8000
```

Access it inside the application using:

```javascript
import.meta.env.VITE_API_URL
```

---

## 📦 Dependencies

```json
{
  "dependencies": {
    "axios": "^1.3.5",
    "pinia": "^2.0.32",
    "resend": "^4.6.0",
    "vue": "^3.2.47",
    "vue-router": "^4.1.6"
  },
  "devDependencies": {
    "@tailwindcss/forms": "^0.5.10",
    "@vitejs/plugin-vue": "^4.0.0",
    "autoprefixer": "^10.4.14",
    "postcss": "^8.4.21",
    "tailwindcss": "^3.3.1",
    "vite": "^4.1.4"
  }
}
```

---

## 🎨 Styling

The frontend is styled using **Tailwind CSS** along with the **@tailwindcss/forms** plugin.

All custom styles are located in the `src/assets/` directory.

---

## 🔐 Security

- ✅ No sensitive information is committed to the repository.
- ✅ Safe to publish publicly on GitHub.

---

## 📌 Future Improvements

- [ ] Implement role-based routing
- [ ] Add unit tests with Vitest
- [ ] Set up CI/CD using GitHub Actions
- [ ] Add a global error boundary

---

## 👨‍💻 Author

Made with ❤️ by **Sahil Sonekar**

**GitHub:** [https://github.com/SahilSonekar](https://github.com/SahilSonekar)

**LinkedIn:** [https://www.linkedin.com/in/sahil-sonekar-837a7725b/](https://www.linkedin.com/in/sahil-sonekar-837a7725b/)