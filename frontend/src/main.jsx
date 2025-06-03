// frontend/src/main.jsx

import React from 'react';
import ReactDOM from 'react-dom/client';
import NaviSearch from './NaviSearch.jsx'; // Import the component from the renamed file
// If you plan to use global CSS, create and import it here, e.g.:
import './index.css';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <NaviSearch />
  </React.StrictMode>
);