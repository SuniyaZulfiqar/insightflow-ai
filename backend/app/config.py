from pydantic_settings import BaseSettings, SettingsConfigDict
 
 
class Settings(BaseSettings):
 
    DATABASE_URL: str
 
    SECRET_KEY: str
 
    GROQ_API_KEY: str = ""
 
    CORS_ORIGINS: str = "http://localhost:5173"
 
    # Gmail SMTP credentials used to send verification codes on signup.
    # Leave blank during local development: the app will print the code to
    # the server console instead of sending a real email.
    GMAIL_ADDRESS: str = ""
    GMAIL_APP_PASSWORD: str = ""
 
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )
 
 
settings = Settings()
 