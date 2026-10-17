import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({plugins:[react()],server:{proxy:{'/resume':'http://localhost:8000','/interview':'http://localhost:8000'}},build:{outDir:'dist',emptyOutDir:true},test:{environment:'jsdom',setupFiles:'./src/test/setup.js'}});
