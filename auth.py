import os
import hashlib

# Configuración
SESSIONS_DIR = "sessions"
os.makedirs(SESSIONS_DIR, exist_ok=True)

def generate_user_id(username: str) -> str:
    """Genera un user_id determinista basado en el username (email)."""
    # Usamos MD5 simple para tener un ID consistente, no es para seguridad criptográfica
    return hashlib.md5(username.lower().encode()).hexdigest()

def get_session_file(user_id: str) -> str:
    """Retorna la ruta absoluta al archivo de sesión de un usuario."""
    return os.path.join(SESSIONS_DIR, f"{user_id}.json")

def session_exists(user_id: str) -> bool:
    """Verifica si existe una sesión válida para el usuario."""
    return os.path.exists(get_session_file(user_id))
