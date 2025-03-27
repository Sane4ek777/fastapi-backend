from fastapi.middleware.cors import CORSMiddleware

def setup_middleware(app):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["https://instrumentdar.ru"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
