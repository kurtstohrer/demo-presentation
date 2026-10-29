import '@fontsource/inter/latin-400.css'
import '@fontsource/inter/latin-600.css'
import '@fontsource/jetbrains-mono/latin-400.css'
import './tokens.css'
import './base.css'
import './app.css'
import { createApp } from 'vue'
import { initTheme } from './theme'
import App from './App.vue'

createApp(App, { theme: initTheme() }).mount('#app')
