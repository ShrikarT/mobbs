import React from 'react';
import { createRoot } from 'react-dom/client';
import { Site } from './Site';
import './style.css';
import '@fontsource/space-mono/latin-400.css';
import '@fontsource/space-mono/latin-700.css';
import '@fontsource/patrick-hand/latin-400.css';
import './theme.css';

const rootEl = document.getElementById('root');
if (rootEl) {
  createRoot(rootEl).render(<Site />);
}
