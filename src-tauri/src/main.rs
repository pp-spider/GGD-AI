// GGD-AI Tauri Application Entry Point

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    ggd_ai_lib::run();
}