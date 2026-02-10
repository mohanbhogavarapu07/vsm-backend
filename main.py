"""
Application entry point. Run: python main.py
"""
import os
from app import create_app
from app.config import Config

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", Config.PORT))
    print("Starting AI-Powered Virtual Scrum Master API on port", port, flush=True)
    if Config.supabase_configured():
        print("Supabase configured.", flush=True)
    else:
        print("WARNING: Supabase not configured (SUPABASE_URL / SUPABASE_KEY).", flush=True)
    app.run(host="0.0.0.0", port=port, debug=Config.DEBUG)
