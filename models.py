from pydantic import BaseModel

class UserLogin(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    user_id: str
    status: str
    message: str

class LibroSincro(BaseModel):
    user_id: str  # ID de sesión retornado por /login (REQUERIDO para multi-usuario)
    titulo: str
    autor: str
    isbn: str = ""
    pagina_actual: int
    total_paginas: int
    dispositivo: str = "KOReader"
