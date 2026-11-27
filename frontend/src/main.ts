import { createApp } from "vue";
import App from "./App.vue";
import "./style.css";
import { initializeSupabaseAuth } from "./lib/supabase";

await initializeSupabaseAuth();
createApp(App).mount("#app");
