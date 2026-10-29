import React from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './App';
import './style.css';

const rootEl = document.getElementById('root');
if (rootEl) {
  createRoot(rootEl).render(<App />);
}
